from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from app.config import (
    get_capability_queue_storage_path,
    get_goal_admission_storage_path,
    get_goal_storage_path,
    get_mempalace_palace_path,
    get_mempalace_room,
    get_mempalace_wing,
    get_orchestrator_message_storage_path,
    get_orchestrator_storage_path,
    get_persona_storage_path,
    get_service_root,
    get_state_storage_path,
    get_world_storage_path,
)

TESTING_MODE_ENV = "XIAOYAN_TESTING_DATA_MODE"
PREVIOUS_ENV_SNAPSHOT_ENV = "XIAOYAN_TESTING_DATA_PREVIOUS_ENV"

DATA_OVERRIDE_ENV_KEYS = (
    "GOAL_STORAGE_PATH",
    "WORLD_STORAGE_PATH",
    "STATE_STORAGE_PATH",
    "PERSONA_STORAGE_PATH",
    "GOAL_ADMISSION_STORAGE_PATH",
    "CAPABILITY_QUEUE_STORAGE_PATH",
    "ORCHESTRATOR_STORAGE_PATH",
    "ORCHESTRATOR_MESSAGE_STORAGE_PATH",
    "MEMPALACE_PALACE_PATH",
    "MEMPALACE_ROOM",
)

BACKUP_MANIFEST_VERSION = 1


@dataclass(frozen=True)
class DataEnvironmentSnapshot:
    testing_mode: bool
    mempalace_palace_path: str
    mempalace_wing: str
    mempalace_room: str
    default_backup_directory: str


@dataclass(frozen=True)
class DataBackupResult:
    backup_path: str
    created_at: str
    restored_keys: list[str]


@dataclass(frozen=True)
class _DataEntry:
    key: str
    path: Path


def is_testing_data_mode_enabled() -> bool:
    return os.getenv(TESTING_MODE_ENV, "0") == "1"


def get_default_backup_directory() -> Path:
    return get_service_root() / ".data" / "backups"


def get_data_environment_snapshot() -> DataEnvironmentSnapshot:
    return DataEnvironmentSnapshot(
        testing_mode=is_testing_data_mode_enabled(),
        mempalace_palace_path=str(Path(get_mempalace_palace_path()).expanduser()),
        mempalace_wing=get_mempalace_wing(),
        mempalace_room=get_mempalace_room(),
        default_backup_directory=str(get_default_backup_directory()),
    )


def apply_testing_data_mode(enabled: bool) -> None:
    if enabled:
        if is_testing_data_mode_enabled():
            return
        _enable_testing_data_mode()
        return

    if not is_testing_data_mode_enabled():
        return
    _disable_testing_data_mode()


def create_data_backup_archive(target_path: str | None = None) -> DataBackupResult:
    destination = _resolve_backup_destination(target_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now(timezone.utc).isoformat()
    entries = _resolve_data_entries()
    manifest_entries: dict[str, dict] = {}
    included_keys: list[str] = []

    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for entry in entries:
            source = entry.path.expanduser()
            if not source.exists():
                continue
            if source.is_file():
                arcname = f"payload/{entry.key}/file"
                archive.write(source, arcname)
                included_keys.append(entry.key)
                manifest_entries[entry.key] = {
                    "kind": "file",
                    "payload_path": arcname,
                }
                continue

            if source.is_dir():
                payload_root = f"payload/{entry.key}/dir"
                wrote_any = False
                for child in sorted(source.rglob("*")):
                    if not child.is_file():
                        continue
                    relative_child = child.relative_to(source).as_posix()
                    archive.write(child, f"{payload_root}/{relative_child}")
                    wrote_any = True
                if not wrote_any:
                    archive.writestr(f"payload/{entry.key}/.empty", "")
                included_keys.append(entry.key)
                manifest_entries[entry.key] = {
                    "kind": "dir",
                    "payload_path": payload_root,
                }

        manifest = {
            "version": BACKUP_MANIFEST_VERSION,
            "created_at": created_at,
            "testing_mode": is_testing_data_mode_enabled(),
            "entries": manifest_entries,
        }
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return DataBackupResult(
        backup_path=str(destination),
        created_at=created_at,
        restored_keys=sorted(included_keys),
    )


def import_data_backup_archive(backup_path: str) -> list[str]:
    source_archive = Path(backup_path).expanduser()
    if not source_archive.exists() or not source_archive.is_file():
        raise FileNotFoundError(f"backup archive not found: {source_archive}")

    with ZipFile(source_archive, "r") as archive:
        _validate_zip_members(archive)
        with TemporaryDirectory(prefix="xiaoyan-backup-import-") as tmp_dir:
            extract_root = Path(tmp_dir)
            archive.extractall(extract_root)

            manifest_path = extract_root / "manifest.json"
            if not manifest_path.exists():
                raise ValueError("backup manifest is missing")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw_entries = manifest.get("entries") if isinstance(manifest, dict) else None
            if not isinstance(raw_entries, dict):
                raise ValueError("backup manifest entries is invalid")

            destinations = {entry.key: entry.path.expanduser() for entry in _resolve_data_entries()}
            restored_keys: list[str] = []

            for key, payload in raw_entries.items():
                if not isinstance(payload, dict):
                    continue
                destination = destinations.get(key)
                if destination is None:
                    continue

                kind = payload.get("kind")
                payload_path = payload.get("payload_path")
                if not isinstance(kind, str) or not isinstance(payload_path, str):
                    continue

                source = (extract_root / payload_path).resolve()
                if not str(source).startswith(str(extract_root.resolve())):
                    raise ValueError("backup payload path escapes extract root")

                if destination.exists():
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    else:
                        destination.unlink()

                if kind == "file":
                    if not source.exists() or not source.is_file():
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    restored_keys.append(key)
                    continue

                if kind == "dir":
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if source.exists() and source.is_dir():
                        shutil.copytree(source, destination)
                    else:
                        destination.mkdir(parents=True, exist_ok=True)
                    restored_keys.append(key)

            return sorted(restored_keys)


def _resolve_data_entries() -> list[_DataEntry]:
    state_path = get_state_storage_path().expanduser()
    service_root = get_service_root()
    return [
        _DataEntry("state", state_path),
        _DataEntry("goals", get_goal_storage_path().expanduser()),
        _DataEntry("world", get_world_storage_path().expanduser()),
        _DataEntry("persona", get_persona_storage_path().expanduser()),
        _DataEntry("goal_admission", get_goal_admission_storage_path().expanduser()),
        _DataEntry("capability_queue", get_capability_queue_storage_path().expanduser()),
        _DataEntry("orchestrator_sessions", get_orchestrator_storage_path().expanduser()),
        _DataEntry("orchestrator_messages", get_orchestrator_message_storage_path().expanduser()),
        _DataEntry("legacy_memory_jsonl", service_root / ".data" / "memory.jsonl"),
        _DataEntry("mempalace_palace", Path(get_mempalace_palace_path()).expanduser()),
    ]


def _resolve_backup_destination(target_path: str | None) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    generated_name = f"xiaoyan-backup-{timestamp}.zip"

    if target_path is None or not target_path.strip():
        return get_default_backup_directory() / generated_name

    requested = Path(target_path).expanduser()
    if requested.suffix.lower() == ".zip":
        return requested

    if requested.exists() and requested.is_file():
        return requested.with_suffix(".zip")

    if requested.exists() and requested.is_dir():
        return requested / generated_name

    # For non-existing paths without `.zip`, treat them as directories.
    return requested / generated_name


def _enable_testing_data_mode() -> None:
    previous = {key: os.environ.get(key) for key in DATA_OVERRIDE_ENV_KEYS}
    os.environ[PREVIOUS_ENV_SNAPSHOT_ENV] = json.dumps(previous, ensure_ascii=False)

    service_root = get_service_root()
    testing_root = service_root / ".data" / "testing"

    base_room = previous.get("MEMPALACE_ROOM") or get_mempalace_room()
    testing_room = f"{base_room}_testing" if not base_room.endswith("_testing") else base_room

    overrides = {
        "GOAL_STORAGE_PATH": str(testing_root / "goals.json"),
        "WORLD_STORAGE_PATH": str(testing_root / "world.json"),
        "STATE_STORAGE_PATH": str(testing_root / "state.json"),
        "PERSONA_STORAGE_PATH": str(testing_root / "persona.json"),
        "GOAL_ADMISSION_STORAGE_PATH": str(testing_root / "goal_admission.json"),
        "CAPABILITY_QUEUE_STORAGE_PATH": str(testing_root / "capability_queue.json"),
        "ORCHESTRATOR_STORAGE_PATH": str(testing_root / "orchestrator_sessions.json"),
        "ORCHESTRATOR_MESSAGE_STORAGE_PATH": str(testing_root / "orchestrator_messages.json"),
        "MEMPALACE_PALACE_PATH": str(testing_root / "mempalace" / "palace"),
        "MEMPALACE_ROOM": testing_room,
    }
    for key, value in overrides.items():
        os.environ[key] = value
    os.environ[TESTING_MODE_ENV] = "1"


def _disable_testing_data_mode() -> None:
    snapshot_raw = os.environ.get(PREVIOUS_ENV_SNAPSHOT_ENV, "")
    restored: dict[str, str | None] = {}
    if snapshot_raw:
        try:
            loaded = json.loads(snapshot_raw)
            if isinstance(loaded, dict):
                restored = {key: value for key, value in loaded.items() if key in DATA_OVERRIDE_ENV_KEYS}
        except json.JSONDecodeError:
            restored = {}

    for key in DATA_OVERRIDE_ENV_KEYS:
        value = restored.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    os.environ.pop(PREVIOUS_ENV_SNAPSHOT_ENV, None)
    os.environ.pop(TESTING_MODE_ENV, None)


def _validate_zip_members(archive: ZipFile) -> None:
    for member in archive.namelist():
        normalized = member.replace("\\", "/")
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
            raise ValueError("backup archive contains unsafe path")
