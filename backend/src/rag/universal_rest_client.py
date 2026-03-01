"""Universal REST Client.

A flexible REST client that supports:
- Any HTTP method (GET, POST, PUT, PATCH, DELETE)
- Any content type (JSON, multipart, form-urlencoded, binary, text)
- Dynamic headers (including secrets from any source)
- Flexible request body templates with {input} placeholder
- JSON path extraction for responses
- Binary and text response handling
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any, Optional, Union
from io import BytesIO

import httpx

from src.rag.pipeline_config import (
    RestApiConfig,
    ContentType,
    InputFormat,
    ResponseType,
    HeaderConfig,
    SecretReference,
)
from src.rag.secret_resolver import SecretResolver

logger = logging.getLogger(__name__)


class UniversalRestClient:
    """Universal REST client for any API.

    Supports:
    - Multiple content types (JSON, multipart, form, binary)
    - Dynamic headers with secret resolution
    - Request body templates with {input} placeholder
    - JSON path extraction for responses
    """

    def __init__(
        self,
        config: RestApiConfig,
        secret_resolver: Optional[SecretResolver] = None,
    ):
        """Initialize the REST client.

        Args:
            config: The REST API configuration
            secret_resolver: Optional secret resolver for headers
        """
        self.config = config
        self.secret_resolver = secret_resolver or SecretResolver()

    async def call(
        self,
        input_data: Union[bytes, str],
        input_filename: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Call the REST API with input data.

        Args:
            input_data: The input data (bytes for files, str for text)
            input_filename: Optional filename for multipart uploads
            extra_headers: Optional additional headers

        Returns:
            Dictionary with:
            - success: bool
            - output: extracted response data
            - raw_response: full response body
            - status_code: HTTP status code
            - error: error message if failed
        """
        try:
            # Resolve headers
            headers = await self._resolve_headers(extra_headers)

            # Prepare request body
            body, files = await self._prepare_request(input_data, input_filename)

            # Make the request
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await self._execute_request(client, headers, body, files)

            # Parse response
            return await self._parse_response(response)

        except httpx.TimeoutException:
            return {
                "success": False,
                "output": None,
                "raw_response": None,
                "status_code": None,
                "error": f"Request timed out after {self.config.timeout_seconds}s",
            }
        except Exception as e:
            logger.exception(f"REST API call failed: {e}")
            return {
                "success": False,
                "output": None,
                "raw_response": None,
                "status_code": None,
                "error": str(e),
            }

    async def _resolve_headers(
        self,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        """Resolve all headers including secrets.

        Args:
            extra_headers: Optional additional headers

        Returns:
            Dictionary of resolved headers
        """
        headers = {}

        # Set content type (except for multipart which httpx handles)
        if self.config.content_type != ContentType.MULTIPART:
            headers["Content-Type"] = self.config.content_type.value

        # Resolve configured headers
        for header_config in self.config.headers:
            key = header_config.key

            if isinstance(header_config.value, SecretReference):
                value = await self.secret_resolver.resolve(header_config.value)
            elif isinstance(header_config.value, str):
                value = header_config.value
            else:
                value = str(header_config.value)

            if value:
                headers[key] = value

        # Add extra headers
        if extra_headers:
            headers.update(extra_headers)

        return headers

    async def _prepare_request(
        self,
        input_data: Union[bytes, str],
        input_filename: Optional[str] = None,
    ) -> tuple[Optional[Any], Optional[dict]]:
        """Prepare the request body based on content type.

        Args:
            input_data: The input data
            input_filename: Optional filename for uploads

        Returns:
            Tuple of (body, files) for the request
        """
        # Encode input based on format
        encoded_input = self._encode_input(input_data)

        match self.config.content_type:
            case ContentType.JSON:
                return self._prepare_json_body(encoded_input), None

            case ContentType.MULTIPART:
                return None, self._prepare_multipart(input_data, input_filename, encoded_input)

            case ContentType.FORM_URLENCODED:
                return self._prepare_form_body(encoded_input), None

            case ContentType.TEXT:
                return encoded_input, None

            case ContentType.BINARY:
                if isinstance(input_data, str):
                    return input_data.encode(), None
                return input_data, None

            case _:
                return self._prepare_json_body(encoded_input), None

    def _encode_input(self, input_data: Union[bytes, str]) -> str:
        """Encode input data based on configured format.

        Args:
            input_data: Raw input data

        Returns:
            Encoded string
        """
        match self.config.input_format:
            case InputFormat.BASE64:
                if isinstance(input_data, str):
                    return base64.b64encode(input_data.encode()).decode()
                return base64.b64encode(input_data).decode()

            case InputFormat.TEXT:
                if isinstance(input_data, bytes):
                    return input_data.decode('utf-8', errors='replace')
                return input_data

            case InputFormat.URL:
                # Input is already a URL
                return input_data if isinstance(input_data, str) else input_data.decode()

            case InputFormat.BINARY:
                # For binary, we return as-is (handled in body preparation)
                if isinstance(input_data, bytes):
                    return base64.b64encode(input_data).decode()
                return input_data

            case _:
                return input_data if isinstance(input_data, str) else input_data.decode()

    def _prepare_json_body(self, encoded_input: str) -> dict:
        """Prepare JSON request body from template.

        Args:
            encoded_input: The encoded input string

        Returns:
            Dictionary for JSON body
        """
        if not self.config.request_body_template:
            return {"input": encoded_input}

        try:
            # Parse template
            template = self.config.request_body_template

            # Replace {input} placeholder
            filled_template = template.replace("{input}", encoded_input)

            return json.loads(filled_template)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse request template: {e}")
            return {"input": encoded_input}

    def _prepare_multipart(
        self,
        input_data: Union[bytes, str],
        input_filename: Optional[str],
        encoded_input: str,
    ) -> dict:
        """Prepare multipart form data.

        Args:
            input_data: Raw input data
            input_filename: Optional filename
            encoded_input: Encoded input string

        Returns:
            Dictionary of files for multipart upload
        """
        files = {}

        if self.config.multipart_fields:
            for field in self.config.multipart_fields:
                if field.field_type == "file":
                    # Use actual file data
                    file_data = input_data if isinstance(input_data, bytes) else input_data.encode()
                    filename = input_filename or "file"
                    files[field.field_name] = (filename, BytesIO(file_data))
                else:
                    # Text field - replace {input} if present
                    value = field.value.replace("{input}", encoded_input)
                    files[field.field_name] = (None, value)
        else:
            # Default: single file field
            file_data = input_data if isinstance(input_data, bytes) else input_data.encode()
            files["file"] = (input_filename or "file", BytesIO(file_data))

        return files

    def _prepare_form_body(self, encoded_input: str) -> dict:
        """Prepare form-urlencoded body.

        Args:
            encoded_input: The encoded input string

        Returns:
            Dictionary for form data
        """
        if not self.config.form_fields:
            return {"input": encoded_input}

        result = {}
        for key, value in self.config.form_fields.items():
            result[key] = value.replace("{input}", encoded_input)

        return result

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        body: Optional[Any],
        files: Optional[dict],
    ) -> httpx.Response:
        """Execute the HTTP request.

        Args:
            client: The HTTP client
            headers: Request headers
            body: Request body
            files: Multipart files

        Returns:
            HTTP response
        """
        method = self.config.method.upper()
        url = self.config.endpoint_url

        # Build request kwargs
        kwargs = {"headers": headers}

        if files:
            kwargs["files"] = files
        elif isinstance(body, dict):
            if self.config.content_type == ContentType.FORM_URLENCODED:
                kwargs["data"] = body
            else:
                kwargs["json"] = body
        elif body is not None:
            kwargs["content"] = body

        # Execute with retry
        last_error = None
        for attempt in range(self.config.retry_count + 1):
            try:
                response = await client.request(method, url, **kwargs)
                return response
            except Exception as e:
                last_error = e
                if attempt < self.config.retry_count:
                    logger.warning(f"Request failed, retrying ({attempt + 1}/{self.config.retry_count}): {e}")
                    continue
                raise

        raise last_error

    async def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse the API response.

        Args:
            response: HTTP response

        Returns:
            Parsed response dictionary
        """
        status_code = response.status_code
        success = 200 <= status_code < 300

        if not success:
            return {
                "success": False,
                "output": None,
                "raw_response": response.text,
                "status_code": status_code,
                "error": f"HTTP {status_code}: {response.text[:500]}",
            }

        match self.config.response_type:
            case ResponseType.JSON:
                try:
                    raw = response.json()
                    output = self._extract_json_path(raw)
                    return {
                        "success": True,
                        "output": output,
                        "raw_response": raw,
                        "status_code": status_code,
                        "error": None,
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "output": None,
                        "raw_response": response.text,
                        "status_code": status_code,
                        "error": "Failed to parse JSON response",
                    }

            case ResponseType.TEXT:
                text = response.text
                return {
                    "success": True,
                    "output": text,
                    "raw_response": text,
                    "status_code": status_code,
                    "error": None,
                }

            case ResponseType.BINARY:
                data = response.content
                return {
                    "success": True,
                    "output": base64.b64encode(data).decode(),
                    "raw_response": f"<binary: {len(data)} bytes>",
                    "status_code": status_code,
                    "error": None,
                }

            case _:
                return {
                    "success": True,
                    "output": response.text,
                    "raw_response": response.text,
                    "status_code": status_code,
                    "error": None,
                }

    def _extract_json_path(self, data: Any) -> Any:
        """Extract value from JSON using path notation.

        Supports:
        - Dot notation: result.text
        - Array indexing: data[0].content
        - Wildcard arrays: choices[*].message.content (returns list)

        Args:
            data: The JSON data

        Returns:
            Extracted value
        """
        if not self.config.output_extraction:
            return data

        path = self.config.output_extraction
        current = data

        # Split path into parts
        parts = self._parse_json_path(path)

        for part in parts:
            if current is None:
                return None

            if part == "*":
                # Wildcard - process rest of path for each item
                if not isinstance(current, list):
                    return None
                remaining_path = ".".join(parts[parts.index(part) + 1:])
                if remaining_path:
                    return [self._extract_nested(item, remaining_path) for item in current]
                return current

            elif part.isdigit():
                # Array index
                idx = int(part)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None

            else:
                # Object key
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None

        return current

    def _parse_json_path(self, path: str) -> list[str]:
        """Parse JSON path into parts.

        Args:
            path: JSON path like "result.data[0].text"

        Returns:
            List of path parts
        """
        parts = []
        current = ""

        i = 0
        while i < len(path):
            char = path[i]

            if char == ".":
                if current:
                    parts.append(current)
                    current = ""
            elif char == "[":
                if current:
                    parts.append(current)
                    current = ""
                # Find closing bracket
                j = i + 1
                while j < len(path) and path[j] != "]":
                    j += 1
                parts.append(path[i + 1:j])
                i = j
            else:
                current += char

            i += 1

        if current:
            parts.append(current)

        return parts

    def _extract_nested(self, data: Any, path: str) -> Any:
        """Extract value from nested data using path.

        Args:
            data: The data to extract from
            path: Remaining path

        Returns:
            Extracted value
        """
        parts = self._parse_json_path(path)
        current = data

        for part in parts:
            if current is None:
                return None

            if part.isdigit():
                idx = int(part)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None

        return current


async def test_rest_api(config: RestApiConfig) -> dict[str, Any]:
    """Test a REST API configuration.

    Sends a small test request to verify:
    - Endpoint is reachable
    - Authentication works
    - Response format matches configuration

    Args:
        config: The REST API configuration to test

    Returns:
        Test result dictionary
    """
    # Create a small test input
    test_input = b"Test input for API validation"

    client = UniversalRestClient(config)

    result = await client.call(test_input, input_filename="test.txt")

    return {
        "success": result["success"],
        "message": "API test successful" if result["success"] else result.get("error", "Unknown error"),
        "status_code": result.get("status_code"),
        "output_preview": str(result.get("output", ""))[:200] if result.get("output") else None,
    }
