"""ABBYY Vantage API async client.

Handles OAuth2 authentication, document upload, transaction polling,
and result download against the ABBYY Vantage public API.

Usage:
    async with AbbyyVantageClient.from_settings(settings) as client:
        result = await client.process_document(file_bytes, filename)
"""

from __future__ import annotations

import asyncio
import logging
import time
from mimetypes import guess_type
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_OAUTH_SCOPE = "openid permissions global.wildcard"


class AbbyyAuthError(Exception):
    """Raised when ABBYY OAuth2 authentication fails."""


class AbbyyProcessingError(Exception):
    """Raised when ABBYY transaction fails or times out."""


class AbbyyVantageClient:
    """Async client for the ABBYY Vantage public API.

    Manages:
    - OAuth2 password-grant token acquisition and refresh
    - Document upload and skill launch
    - Transaction status polling
    - Result file download

    Args:
        base_url:       Vantage API base URL (region-specific).
        token_url:      OAuth2 token endpoint.
        username:       Vantage account username.
        password:       Vantage account password.
        client_id:      OAuth2 client ID.
        client_secret:  OAuth2 client secret.
        skill_id:       OCR skill ID to use for processing.
        poll_interval:  Seconds between transaction status polls.
        timeout:        Max seconds to wait for a transaction.
    """

    def __init__(
        self,
        base_url: str,
        token_url: str,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
        skill_id: str,
        poll_interval: float = 1.0,
        timeout: int = 300,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_url = token_url
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._skill_id = skill_id
        self._poll_interval = poll_interval
        self._timeout = timeout

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AbbyyVantageClient:
        self._http = httpx.AsyncClient(timeout=60.0)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    @classmethod
    def from_settings(cls, settings: Any) -> AbbyyVantageClient:
        """Construct client from InferenceSettings."""
        return cls(
            base_url=settings.abbyy_base_url,
            token_url=settings.abbyy_token_url,
            username=settings.abbyy_username,
            password=settings.abbyy_password,
            client_id=settings.abbyy_client_id,
            client_secret=settings.abbyy_client_secret,
            skill_id=settings.abbyy_skill_id,
            poll_interval=settings.abbyy_poll_interval,
            timeout=settings.abbyy_timeout,
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def _get_token(self) -> str:
        """Return a valid access token, refreshing if expired."""
        if self._access_token and time.monotonic() < self._token_expires_at:
            return self._access_token

        logger.debug("Acquiring ABBYY Vantage OAuth2 token")
        response = await self._http.post(
            self._token_url,
            data={
                "grant_type": "password",
                "scope": _OAUTH_SCOPE,
                "username": self._username,
                "password": self._password,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            raise AbbyyAuthError(
                f"ABBYY authentication failed [{response.status_code}]: {response.text}"
            )

        payload = response.json()
        self._access_token = payload["access_token"]
        # expires_in is in seconds; subtract 30s buffer
        expires_in = payload.get("expires_in", 3600)
        self._token_expires_at = time.monotonic() + expires_in - 30
        logger.debug("ABBYY token acquired, expires in %ds", expires_in)
        return self._access_token

    async def _auth_headers(self) -> dict[str, str]:
        token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "accept": "application/json",
        }

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    async def _upload_document(self, file_bytes: bytes, filename: str) -> str:
        """Upload document to Vantage and launch the OCR skill.

        Returns:
            Transaction ID string.
        """
        mime_type, _ = guess_type(filename)
        mime_type = mime_type or "application/octet-stream"

        headers = await self._auth_headers()
        response = await self._http.post(
            f"{self._base_url}/transactions/launch",
            params={"skillId": self._skill_id},
            headers=headers,
            files={"Files": (filename, file_bytes, mime_type)},
            timeout=120.0,
        )

        if response.status_code not in (200, 201):
            raise AbbyyProcessingError(
                f"ABBYY upload failed [{response.status_code}]: {response.text}"
            )

        transaction_id = response.json()["transactionId"]
        logger.debug("ABBYY transaction started: %s", transaction_id)
        return transaction_id

    async def _poll_transaction(self, transaction_id: str) -> dict[str, Any]:
        """Poll transaction status until Processed, Failed, or timeout.

        Returns:
            Full transaction response dict when status is Processed.
        """
        headers = await self._auth_headers()
        deadline = time.monotonic() + self._timeout

        while True:
            if time.monotonic() > deadline:
                raise AbbyyProcessingError(
                    f"ABBYY transaction {transaction_id} timed out after {self._timeout}s"
                )

            response = await self._http.get(
                f"{self._base_url}/transactions/{transaction_id}",
                headers=headers,
            )

            if response.status_code != 200:
                raise AbbyyProcessingError(
                    f"ABBYY status poll failed [{response.status_code}]: {response.text}"
                )

            data = response.json()
            status = data.get("status", "")
            logger.debug("ABBYY transaction %s status: %s", transaction_id, status)

            if status == "Processed":
                return data
            elif status in ("Failed", "Cancelled"):
                raise AbbyyProcessingError(
                    f"ABBYY transaction {transaction_id} ended with status: {status}"
                )

            await asyncio.sleep(self._poll_interval)

    async def _download_results(
        self,
        transaction_id: str,
        file_ids: list[str],
    ) -> list[Any]:
        """Download all result files from a completed transaction.

        Returns:
            List of parsed JSON results (one per result file).
        """
        headers = await self._auth_headers()
        results = []

        for file_id in file_ids:
            response = await self._http.get(
                f"{self._base_url}/transactions/{transaction_id}/files/{file_id}/download",
                headers=headers,
                timeout=60.0,
            )
            try:
                results.append(response.json())
            except Exception:
                results.append(response.text)

        return results

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def process_document(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> list[dict[str, Any]]:
        """Run the full Vantage OCR pipeline on a document.

        Uploads the file, waits for processing, downloads and returns
        all result JSON payloads.

        Args:
            file_bytes: Raw file content.
            filename:   Original filename (used for MIME type detection).

        Returns:
            List of Vantage JSON result dicts.
            Typically one item: the OCR.Skill JSON output v1.0.

        Raises:
            AbbyyAuthError: On authentication failure.
            AbbyyProcessingError: On upload failure, timeout, or skill error.
        """
        if not self._http:
            raise RuntimeError(
                "Client not started — use 'async with AbbyyVantageClient(...) as client'"
            )

        logger.info("Sending '%s' to ABBYY Vantage (skill: %s)", filename, self._skill_id)

        transaction_id = await self._upload_document(file_bytes, filename)
        transaction_data = await self._poll_transaction(transaction_id)

        # Collect result file IDs from all documents in the transaction
        file_ids: list[str] = []
        for doc in transaction_data.get("documents", []):
            for result_file in doc.get("resultFiles", []):
                file_ids.append(result_file["fileId"])

        if not file_ids:
            raise AbbyyProcessingError(
                f"ABBYY transaction {transaction_id} completed but returned no result files"
            )

        logger.info(
            "ABBYY transaction %s complete — downloading %d result file(s)",
            transaction_id,
            len(file_ids),
        )
        return await self._download_results(transaction_id, file_ids)

    async def list_skills(self) -> list[dict[str, Any]]:
        """Return all available skills for the authenticated account."""
        headers = await self._auth_headers()
        response = await self._http.get(f"{self._base_url}/skills/", headers=headers)
        response.raise_for_status()
        return response.json()
