from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Protocol

from app.persona.models import PersonaProfile, default_value_foundation

logger = getLogger(__name__)


class PersonaRepository(Protocol):
    def save(self, profile: PersonaProfile) -> None: ...
    def load(self) -> PersonaProfile | None: ...


class FilePersonaRepository:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path

    def save(self, profile: PersonaProfile) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w", encoding="utf-8") as handle:
            handle.write(profile.model_dump_json(indent=2))

    def load(self) -> PersonaProfile | None:
        if not self.storage_path.exists():
            return None
        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                data = handle.read()
            return PersonaProfile.model_validate_json(data)
        except Exception as exc:
            logger.warning("Failed to load persona from %s: %s", self.storage_path, exc)
            return None


class InMemoryPersonaRepository:
    def __init__(self) -> None:
        self._profile: PersonaProfile | None = None

    def save(self, profile: PersonaProfile) -> None:
        self._profile = profile

    def load(self) -> PersonaProfile | None:
        return self._profile


def ensure_value_foundation(profile: PersonaProfile) -> PersonaProfile:
    if profile.values.core_values and profile.values.boundaries:
        return profile

    foundation = default_value_foundation()
    return profile.model_copy(
        update={
            "values": profile.values.model_copy(
                update={
                    "core_values": profile.values.core_values or foundation.core_values,
                    "boundaries": profile.values.boundaries or foundation.boundaries,
                }
            ),
            "version": profile.version + 1,
        }
    )
