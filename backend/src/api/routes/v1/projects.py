"""Project management API routes."""

from __future__ import annotations

import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.deps import get_db, get_current_user
from src.models import Project, Secret, PROVIDER_SECRETS, TOOL_SECRETS


router = APIRouter(prefix="/projects", tags=["projects"])


# ========== Schemas ==========

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    provider_config: dict[str, Any] = {}


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    provider_config: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    icon: str | None
    color: str | None
    provider_config: dict[str, Any]
    settings: dict[str, Any]
    is_active: bool

    class Config:
        from_attributes = True


class SecretCreate(BaseModel):
    key: str
    value: str
    description: str | None = None
    category: str = "custom"
    used_by: str | None = None


class SecretUpdate(BaseModel):
    value: str | None = None
    description: str | None = None


class SecretResponse(BaseModel):
    id: uuid.UUID
    key: str
    description: str | None
    category: str
    used_by: str | None
    is_required: bool
    is_set: bool

    class Config:
        from_attributes = True


class RequiredSecretInfo(BaseModel):
    key: str
    description: str
    category: str
    is_set: bool
    used_by: str


# ========== Helper Functions ==========

def generate_slug(name: str) -> str:
    """Generate URL-safe slug from name."""
    import re
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def encrypt_value(value: str) -> str:
    """Encrypt a secret value. In production, use proper encryption."""
    # TODO: Implement proper encryption with Fernet or similar
    import base64
    return base64.b64encode(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt a secret value."""
    import base64
    return base64.b64decode(encrypted.encode()).decode()


# ========== Project Endpoints ==========

@router.get("")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[ProjectResponse]:
    """List all projects."""
    result = await db.execute(
        select(Project).where(
            Project.is_active == True,
        )
    )
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post("")
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProjectResponse:
    """Create a new project."""
    project = Project(
        name=data.name,
        slug=generate_slug(data.name),
        description=data.description,
        icon=data.icon,
        color=data.color,
        provider_config=data.provider_config,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Initialize required secrets based on provider config
    await _initialize_project_secrets(db, project)

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProjectResponse:
    """Get a specific project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProjectResponse:
    """Update a project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    if data.name:
        project.slug = generate_slug(data.name)

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, str]:
    """Delete a project (soft delete)."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.is_active = False
    await db.commit()
    return {"status": "deleted"}


# ========== Secrets Endpoints ==========

@router.get("/{project_id}/secrets")
async def list_secrets(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[SecretResponse]:
    """List all secrets for a project (values are not returned)."""
    # Verify project exists
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Secret).where(Secret.project_id == project_id)
    )
    secrets = result.scalars().all()
    return [SecretResponse.model_validate(s) for s in secrets]


@router.get("/{project_id}/secrets/required")
async def get_required_secrets(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[RequiredSecretInfo]:
    """Get list of required secrets based on configured providers."""
    # Verify project exists
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get existing secrets
    result = await db.execute(
        select(Secret).where(Secret.project_id == project_id)
    )
    existing_secrets = {s.key: s for s in result.scalars().all()}

    required = []

    # Check provider config for required secrets
    provider_config = project.provider_config or {}

    provider_mappings = {
        "openai": ["openai"],
        "anthropic": ["anthropic"],
        "google": ["google"],
        "azure": ["azure", "azure_region"],
        "elevenlabs": ["elevenlabs"],
        "deepgram": ["deepgram"],
        "assemblyai": ["assemblyai"],
        "cohere": ["cohere"],
        "voyage": ["voyage"],
        "qdrant": ["qdrant"],
        "playht": ["playht", "playht_user"],
    }

    for provider_type in ["llm", "stt", "tts", "embeddings", "vectorstore"]:
        if provider_type in provider_config:
            provider_name = provider_config[provider_type].get("provider", "")
            for mapping_key, secret_keys in provider_mappings.items():
                if mapping_key in provider_name.lower():
                    for secret_key in secret_keys:
                        if secret_key in PROVIDER_SECRETS:
                            secret_info = PROVIDER_SECRETS[secret_key]
                            existing = existing_secrets.get(secret_info["key"])
                            required.append(RequiredSecretInfo(
                                key=secret_info["key"],
                                description=secret_info["description"],
                                category=secret_info["category"],
                                is_set=existing.is_set if existing else False,
                                used_by=provider_type,
                            ))

    return required


@router.post("/{project_id}/secrets")
async def create_secret(
    project_id: uuid.UUID,
    data: SecretCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> SecretResponse:
    """Create or update a secret."""
    # Verify project exists
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if secret already exists
    result = await db.execute(
        select(Secret).where(
            Secret.project_id == project_id,
            Secret.key == data.key,
        )
    )
    secret = result.scalar_one_or_none()

    if secret:
        # Update existing
        secret.encrypted_value = encrypt_value(data.value)
        secret.description = data.description or secret.description
        secret.is_set = True
    else:
        # Create new
        secret = Secret(
            project_id=project_id,
            key=data.key,
            encrypted_value=encrypt_value(data.value),
            description=data.description,
            category=data.category,
            used_by=data.used_by,
            is_set=True,
        )
        db.add(secret)

    await db.commit()
    await db.refresh(secret)
    return SecretResponse.model_validate(secret)


@router.delete("/{project_id}/secrets/{secret_key}")
async def delete_secret(
    project_id: uuid.UUID,
    secret_key: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, str]:
    """Delete a secret."""
    # Verify project exists
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Secret).where(
            Secret.project_id == project_id,
            Secret.key == secret_key,
        )
    )
    secret = result.scalar_one_or_none()
    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")

    await db.delete(secret)
    await db.commit()
    return {"status": "deleted"}


# ========== All Available Secrets Reference ==========

@router.get("/reference/provider-secrets")
async def list_all_provider_secrets() -> dict[str, Any]:
    """List all available provider secrets for reference."""
    return PROVIDER_SECRETS


@router.get("/reference/tool-secrets")
async def list_all_tool_secrets() -> dict[str, Any]:
    """List all available tool secrets for reference."""
    return TOOL_SECRETS


# ========== Helper Functions ==========

async def _initialize_project_secrets(db: AsyncSession, project: Project):
    """Initialize required secrets based on provider config."""
    # This creates placeholder secrets without values
    # User will need to fill them in
    pass
