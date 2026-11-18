import uuid
from typing import Any

import aioboto3
import structlog
from aiobotocore.config import AioConfig

from autopark_bot.config import Settings

logger = structlog.get_logger(__name__)


class S3Storage:
    """Тонкая обёртка над приватным S3-bucket.

    Правила:
    - источник истины для файлов — S3, а не Telegram file_id;
    - ключи неугадываемые (uuid4), метаданные хранятся в таблице `files` (появится вместе
      с доменными таблицами);
    - публичных ссылок нет: файл отдаём байтами через бота или presigned URL с коротким TTL.

    Клиент создаётся на каждую операцию: для десятков фото в день этого достаточно.
    """

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._default_ttl = settings.s3_presign_ttl_seconds
        self._session = aioboto3.Session()
        self._client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "endpoint_url": settings.s3_endpoint_url,
            "region_name": settings.s3_region,
            "aws_access_key_id": settings.s3_access_key.get_secret_value(),
            "aws_secret_access_key": settings.s3_secret_key.get_secret_value(),
            "config": AioConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=30,
            ),
        }

    def _client(self) -> Any:
        return self._session.client(**self._client_kwargs)

    @staticmethod
    def new_key(purpose: str, ext: str = "") -> str:
        """Неугадываемый ключ вида `receipts/<uuid>.jpg`."""
        return f"{purpose}/{uuid.uuid4().hex}{ext}"

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        async with self._client() as s3:
            await s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    async def get(self, key: str) -> bytes:
        async with self._client() as s3:
            response = await s3.get_object(Bucket=self._bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()

    async def delete(self, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def presigned_url(self, key: str, ttl_seconds: int | None = None) -> str:
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl_seconds or self._default_ttl,
            )

    async def check(self) -> bool:
        """Проверка доступности bucket на старте (не валит приложение при ошибке)."""
        try:
            async with self._client() as s3:
                await s3.head_bucket(Bucket=self._bucket)
        except Exception:
            logger.exception("s3.check_failed", bucket=self._bucket)
            return False
        return True
