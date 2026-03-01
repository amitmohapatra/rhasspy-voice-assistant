"""AWS S3 storage backend."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from typing import AsyncIterator

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.core.storage.base import StorageBackend, StorageFile


class S3StorageBackend(StorageBackend):
    """
    AWS S3 storage backend.

    Supports:
    - AWS S3 (production)
    - LocalStack S3 (local development)
    - MinIO (alternative local S3-compatible storage)
    """

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        endpoint_url: str | None = None,  # For LocalStack/MinIO
        use_ssl: bool = True,
        max_pool_connections: int = 50,
    ):
        """
        Initialize S3 storage.

        Args:
            bucket: S3 bucket name
            region: AWS region
            access_key_id: AWS access key (optional, uses IAM role if not provided)
            secret_access_key: AWS secret key
            endpoint_url: Custom endpoint for LocalStack/MinIO
            use_ssl: Whether to use SSL (False for local development)
            max_pool_connections: Max connections in pool
        """
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url

        # Configure boto3 client
        config = Config(
            region_name=region,
            max_pool_connections=max_pool_connections,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        client_kwargs = {"config": config}

        if access_key_id and secret_access_key:
            client_kwargs["aws_access_key_id"] = access_key_id
            client_kwargs["aws_secret_access_key"] = secret_access_key

        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
            client_kwargs["use_ssl"] = use_ssl

        self._client = boto3.client("s3", **client_kwargs)
        self._executor = ThreadPoolExecutor(max_workers=10)

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous boto3 call in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, partial(func, *args, **kwargs)
        )

    async def save(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """Save content to S3."""
        put_kwargs = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": content,
            "ContentType": content_type,
        }

        if metadata:
            # S3 metadata keys must be strings
            put_kwargs["Metadata"] = {
                str(k): str(v) for k, v in metadata.items()
            }

        await self._run_sync(self._client.put_object, **put_kwargs)

        return f"s3://{self.bucket}/{key}"

    async def get(self, key: str) -> bytes:
        """Get file content from S3."""
        try:
            response = await self._run_sync(
                self._client.get_object,
                Bucket=self.bucket,
                Key=key,
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {key}")
            raise

    async def delete(self, key: str) -> bool:
        """Delete a file from S3."""
        try:
            await self._run_sync(
                self._client.delete_object,
                Bucket=self.bucket,
                Key=key,
            )
            return True
        except ClientError:
            return False

    async def exists(self, key: str) -> bool:
        """Check if a file exists in S3."""
        try:
            await self._run_sync(
                self._client.head_object,
                Bucket=self.bucket,
                Key=key,
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    async def list(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[StorageFile]:
        """List files in S3 bucket."""
        files = []
        continuation_token = None

        while len(files) < max_keys:
            list_kwargs = {
                "Bucket": self.bucket,
                "MaxKeys": min(1000, max_keys - len(files)),
            }

            if prefix:
                list_kwargs["Prefix"] = prefix

            if continuation_token:
                list_kwargs["ContinuationToken"] = continuation_token

            response = await self._run_sync(
                self._client.list_objects_v2,
                **list_kwargs,
            )

            for obj in response.get("Contents", []):
                files.append(
                    StorageFile(
                        key=obj["Key"],
                        size=obj["Size"],
                        content_type=self._get_content_type(obj["Key"]),
                        last_modified=obj["LastModified"],
                        etag=obj.get("ETag", "").strip('"'),
                    )
                )

            if not response.get("IsTruncated"):
                break

            continuation_token = response.get("NextContinuationToken")

        return files

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Get a presigned URL for S3 object."""
        url = await self._run_sync(
            self._client.generate_presigned_url,
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file content from S3 in chunks."""
        try:
            response = await self._run_sync(
                self._client.get_object,
                Bucket=self.bucket,
                Key=key,
            )

            body = response["Body"]

            # Read in chunks
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {key}")
            raise

    async def copy(self, source_key: str, dest_key: str) -> str:
        """Copy a file within S3 (efficient server-side copy)."""
        await self._run_sync(
            self._client.copy_object,
            Bucket=self.bucket,
            CopySource={"Bucket": self.bucket, "Key": source_key},
            Key=dest_key,
        )
        return f"s3://{self.bucket}/{dest_key}"

    async def get_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 3600,
    ) -> str:
        """Get a presigned URL for direct upload to S3."""
        url = await self._run_sync(
            self._client.generate_presigned_url,
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return url

    async def create_bucket_if_not_exists(self) -> bool:
        """Create the bucket if it doesn't exist (useful for LocalStack)."""
        try:
            await self._run_sync(
                self._client.head_bucket,
                Bucket=self.bucket,
            )
            return False  # Already exists
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                create_kwargs = {"Bucket": self.bucket}

                # LocationConstraint is required for non-us-east-1 regions
                if self.region != "us-east-1":
                    create_kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": self.region
                    }

                await self._run_sync(
                    self._client.create_bucket,
                    **create_kwargs,
                )
                return True
            raise

    def _get_content_type(self, key: str) -> str:
        """Guess content type from key extension."""
        import mimetypes

        mime_type, _ = mimetypes.guess_type(key)
        return mime_type or "application/octet-stream"
