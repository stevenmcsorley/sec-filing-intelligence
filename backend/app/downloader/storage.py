"""Storage backends used by the downloader."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from minio import Minio


@dataclass(slots=True)
class StoredArtifact:
    """Represents a persisted artifact."""

    location: str
    content_type: str | None


class StorageBackend(Protocol):
    """Protocol for storing filing artifacts."""

    async def store(self, key: str, data: bytes, content_type: str | None) -> StoredArtifact:
        """Persist the artifact and return its location."""


class MinioStorageBackend:
    """Storage backend that writes artifacts to MinIO."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        region: str | None = None,
    ) -> None:
        self._bucket = bucket
        parsed = urlparse(endpoint)
        netloc = parsed.netloc or parsed.path
        self._client = Minio(
            netloc,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )

    async def ensure_bucket(self) -> None:
        exists = await asyncio.to_thread(self._client.bucket_exists, self._bucket)
        if not exists:
            await asyncio.to_thread(self._client.make_bucket, self._bucket)

    async def store(self, key: str, data: bytes, content_type: str | None) -> StoredArtifact:
        await self.ensure_bucket()
        stream = io.BytesIO(data)
        length = len(data)

        def upload() -> None:
            stream.seek(0)
            if content_type is not None:
                self._client.put_object(
                    self._bucket,
                    key,
                    stream,
                    length,
                    content_type=content_type,
                )
            else:
                self._client.put_object(
                    self._bucket,
                    key,
                    stream,
                    length,
                )

        await asyncio.to_thread(upload)
        location = f"s3://{self._bucket}/{key}"
        return StoredArtifact(location=location, content_type=content_type)


class LocalFilesystemStorageBackend:
    """Filesystem storage used primarily in tests."""

    def __init__(self, root: Path) -> None:
        self._root = root

    async def store(self, key: str, data: bytes, content_type: str | None) -> StoredArtifact:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return StoredArtifact(location=f"file://{path}", content_type=content_type)
