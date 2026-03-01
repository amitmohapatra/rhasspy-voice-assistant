"""Seed data for vendor capability mappings.

Seeds DEFAULT_VENDOR_MAPPINGS from capability.py into the
vendor_capability_mappings table on startup. Idempotent.

Usage:
    from src.db.seeds.capability_seed import seed_capabilities
    await seed_capabilities(db_session)
"""

from sqlalchemy import select

from src.models.capability import DEFAULT_VENDOR_MAPPINGS, VendorCapabilityMapping
from src.models.ai_model import AIProvider


async def seed_vendor_capability_mappings(db_session) -> dict:
    """Seed DEFAULT_VENDOR_MAPPINGS into vendor_capability_mappings table."""
    created = []
    skipped = []
    errors = []

    for provider_name, capabilities in DEFAULT_VENDOR_MAPPINGS.items():
        # Find provider
        result = await db_session.execute(
            select(AIProvider).where(AIProvider.name == provider_name)
        )
        provider = result.scalar_one_or_none()

        if not provider:
            errors.append(f"Provider '{provider_name}' not found in database")
            continue

        for cap_type, mapping_data in capabilities.items():
            # Check if already exists
            result = await db_session.execute(
                select(VendorCapabilityMapping).where(
                    VendorCapabilityMapping.provider_id == provider.id,
                    VendorCapabilityMapping.capability_type == cap_type,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                skipped.append(f"{provider_name}/{cap_type.value}")
                continue

            try:
                mapping = VendorCapabilityMapping(
                    provider_id=provider.id,
                    capability_type=cap_type,
                    vendor_name=mapping_data["vendor_name"],
                    invocation_method=mapping_data.get("invocation_method", "parameter"),
                    api_config=mapping_data.get("api_config", {}),
                    default_params=mapping_data.get("default_params", {}),
                    supported_model_patterns=mapping_data.get("supported_model_patterns", []),
                    excluded_model_patterns=mapping_data.get("excluded_model_patterns", []),
                    is_available=True,
                    notes=mapping_data.get("notes"),
                )
                db_session.add(mapping)
                created.append(f"{provider_name}/{cap_type.value}")
            except Exception as e:
                errors.append(f"{provider_name}/{cap_type.value}: {str(e)}")

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "summary": {
            "total_created": len(created),
            "total_skipped": len(skipped),
            "total_errors": len(errors),
        },
    }


async def seed_capabilities(db_session) -> dict:
    """Seed vendor capability mappings."""
    mappings_result = await seed_vendor_capability_mappings(db_session)

    await db_session.commit()

    return {
        "definitions": {"total_created": 0, "total_skipped": 0, "total_errors": 0},
        "vendor_mappings": mappings_result["summary"],
    }
