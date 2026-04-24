from __future__ import annotations

from pathlib import Path

from app.config import (
    get_service_root,
    get_vrm_blender_path,
    get_vrm_generation_artifact_dir,
    get_vrm_generation_storage_path,
    get_vrm_generation_template_path,
)
from app.vrm_generation.executor import BlenderVrmExecutor
from app.vrm_generation.repository import VrmGenerationRepository
from app.vrm_generation.service import VrmGenerationService


def build_vrm_generation_service() -> VrmGenerationService:
    service_root = get_service_root()
    script_path = service_root / "scripts" / "vrm_generation" / "roundtrip_vrm.py"
    default_model = service_root.parents[1] / "apps" / "desktop" / "public" / "avatar" / "xiaoyan.vrm"
    return VrmGenerationService(
        repository=VrmGenerationRepository(get_vrm_generation_storage_path()),
        executor=BlenderVrmExecutor(blender_path=get_vrm_blender_path(), script_path=script_path),
        artifact_dir=get_vrm_generation_artifact_dir(),
        template_path=get_vrm_generation_template_path(),
        default_input_model_path=default_model if default_model.exists() else None,
    )
