"""LLM Key Service — encrypt/decrypt/manage user vendor API keys."""

from __future__ import annotations

import base64
import hashlib
import logging
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.user_llm_key import UserLLMKey

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the app's encryption_key + salt."""
    key_material = (settings.encryption_key or settings.secret_key).encode()
    salt = (settings.encryption_salt or "llm-keys").encode()
    dk = hashlib.pbkdf2_hmac("sha256", key_material, salt, 100_000)
    return Fernet(base64.urlsafe_b64encode(dk))


def encrypt_key(plaintext: str) -> str:
    """Encrypt an API key."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    """Decrypt an API key."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def mask_key(plaintext: str) -> str:
    """Return a masked preview like 'sk-...abc'."""
    if len(plaintext) <= 6:
        return "***"
    return plaintext[:3] + "..." + plaintext[-3:]


async def save_llm_key(
    db: AsyncSession,
    user_id: UUID,
    provider: str,
    api_key: str,
    label: str | None = None,
) -> UserLLMKey:
    """Save or upsert an encrypted LLM vendor key."""
    existing = await db.execute(
        select(UserLLMKey).where(
            UserLLMKey.user_id == user_id,
            UserLLMKey.provider == provider,
        )
    )
    row = existing.scalar_one_or_none()

    encrypted = encrypt_key(api_key)

    if row:
        row.encrypted_key = encrypted
        if label is not None:
            row.label = label
    else:
        row = UserLLMKey(
            user_id=user_id,
            provider=provider,
            encrypted_key=encrypted,
            label=label,
        )
        db.add(row)

    await db.flush()
    await db.refresh(row)
    return row


async def get_user_llm_key(
    db: AsyncSession,
    user_id: UUID,
    provider: str,
) -> str | None:
    """Get a decrypted LLM key for a user+provider, or None."""
    result = await db.execute(
        select(UserLLMKey).where(
            UserLLMKey.user_id == user_id,
            UserLLMKey.provider == provider,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    try:
        return decrypt_key(row.encrypted_key)
    except Exception:
        logger.warning("Failed to decrypt LLM key for user=%s provider=%s", user_id, provider)
        return None


async def list_user_llm_keys(
    db: AsyncSession,
    user_id: UUID,
) -> list[dict]:
    """List saved vendor keys (masked, never full key)."""
    result = await db.execute(
        select(UserLLMKey).where(UserLLMKey.user_id == user_id)
    )
    rows = result.scalars().all()
    keys = []
    for row in rows:
        try:
            plain = decrypt_key(row.encrypted_key)
            preview = mask_key(plain)
        except Exception:
            preview = "***"
        keys.append({
            "provider": row.provider,
            "key_preview": preview,
            "label": row.label,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })
    return keys


async def delete_user_llm_key(
    db: AsyncSession,
    user_id: UUID,
    provider: str,
) -> bool:
    """Delete a user's LLM key for a provider."""
    result = await db.execute(
        delete(UserLLMKey).where(
            UserLLMKey.user_id == user_id,
            UserLLMKey.provider == provider,
        )
    )
    await db.flush()
    return result.rowcount > 0
