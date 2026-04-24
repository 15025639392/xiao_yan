from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.utils.file_utils import write_json_file
from app.vrm_generation.environment_remediation import request_blender_install_remediation
from app.vrm_generation.executor import BlenderExecutionError, BlenderUnavailableError, BlenderVrmExecutor
from app.vrm_generation.models import (
    VrmGenerationArtifacts,
    VrmGenerationJob,
    VrmGenerationRequest,
    VrmGenerationStatus,
)
from app.vrm_generation.repository import VrmGenerationRepository


class VrmGenerationService:
    def __init__(
        self,
        *,
        repository: VrmGenerationRepository,
        executor: BlenderVrmExecutor,
        artifact_dir: Path,
        template_path: Path | None = None,
        default_input_model_path: Path | None = None,
    ) -> None:
        self._repository = repository
        self._executor = executor
        self._artifact_dir = artifact_dir
        self._template_path = template_path
        self._default_input_model_path = default_input_model_path

    def create_job(self, request: VrmGenerationRequest) -> VrmGenerationJob:
        job = VrmGenerationJob(prompt=request.prompt, input_model_path=request.input_model_path)
        self._repository.save(job)
        spec_path = self._safe_job_dir(job.job_id) / "request.json"
        write_json_file(spec_path, request.model_dump(mode="json"), ensure_ascii=False, indent=2, create_parent=True)
        return job

    def get_job(self, job_id: str) -> VrmGenerationJob | None:
        return self._repository.get(job_id)

    def list_recent_jobs(self, limit: int = 20) -> list[VrmGenerationJob]:
        return self._repository.list_recent(limit=limit)

    def mark_cancelled(self, job_id: str) -> VrmGenerationJob | None:
        job = self._repository.get(job_id)
        if job is None:
            return None
        cancelled = job.with_status(VrmGenerationStatus.CANCELLED)
        self._repository.save(cancelled)
        return cancelled

    def run_job(self, job_id: str) -> VrmGenerationJob | None:
        job = self._repository.get(job_id)
        if job is None or job.status == VrmGenerationStatus.CANCELLED:
            return job
        request = self._load_request(job_id)
        try:
            job = self._run_job(job, request)
        except BlenderUnavailableError as exc:
            remediation_request_id = request_blender_install_remediation(job_id=job.job_id)
            job = job.fail(code="blender_unavailable", message=f"Blender unavailable: {exc}").model_copy(
                update={
                    "artifacts": job.artifacts.model_copy(
                        update={"remediation_capability_request_id": remediation_request_id}
                    )
                }
            )
        except BlenderExecutionError as exc:
            job = job.fail(code="blender_execution_failed", message=str(exc))
        except Exception as exc:
            job = job.fail(code="vrm_generation_failed", message=str(exc))
        latest = self._repository.get(job_id)
        if latest is not None and latest.status == VrmGenerationStatus.CANCELLED:
            return latest
        self._repository.save(job)
        return job

    def _load_request(self, job_id: str) -> VrmGenerationRequest:
        request_path = self._safe_job_dir(job_id) / "request.json"
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        return VrmGenerationRequest.model_validate(payload)

    def _run_job(self, job: VrmGenerationJob, request: VrmGenerationRequest) -> VrmGenerationJob:
        input_model_path = None if self._has_template() else self._resolve_input_path(request.input_model_path)
        job_dir = self._safe_job_dir(job.job_id)
        spec_path = job_dir / "character_spec.json"
        output_path = job_dir / "output.vrm"
        log_path = job_dir / "blender.log"

        job = job.with_status(VrmGenerationStatus.VALIDATING_SPEC)
        self._repository.save(job)
        if self._is_cancelled(job.job_id):
            return self._repository.get(job.job_id) or job
        spec = request.spec if request.spec is not None else build_spec_from_prompt(request.prompt)
        write_json_file(spec_path, spec, ensure_ascii=False, indent=2, create_parent=True)

        job = job.with_status(VrmGenerationStatus.RUNNING_BLENDER).model_copy(
            update={
                "input_model_path": str(input_model_path),
                "artifacts": VrmGenerationArtifacts(spec_path=str(spec_path), log_path=str(log_path)),
            }
        )
        self._repository.save(job)
        if self._is_cancelled(job.job_id):
            return self._repository.get(job.job_id) or job
        if self._has_template():
            self._executor.export_vrm_from_template(
                template_path=self._template_path,
                spec_path=spec_path,
                output_path=output_path,
                log_path=log_path,
                is_cancelled=lambda: self._is_cancelled(job.job_id),
            )
        else:
            self._executor.export_vrm(
                input_path=input_model_path,
                spec_path=spec_path,
                output_path=output_path,
                log_path=log_path,
                is_cancelled=lambda: self._is_cancelled(job.job_id),
            )
        if self._is_cancelled(job.job_id):
            return self._repository.get(job.job_id) or job

        return job.with_status(VrmGenerationStatus.COMPLETED).model_copy(
            update={
                "artifacts": VrmGenerationArtifacts(
                    spec_path=str(spec_path),
                    output_vrm_path=str(output_path),
                    log_path=str(log_path),
                )
            }
        )

    def _resolve_input_path(self, input_model_path: str | None) -> Path:
        candidate = Path(input_model_path).expanduser() if input_model_path else self._default_input_model_path
        if candidate is None or not candidate.is_file():
            raise FileNotFoundError("input VRM model is not available")
        return candidate.resolve()

    def _has_template(self) -> bool:
        return self._template_path is not None and self._template_path.is_file()

    def _safe_job_dir(self, job_id: str) -> Path:
        job_dir = (self._artifact_dir / job_id).resolve()
        artifact_root = self._artifact_dir.resolve()
        try:
            job_dir.relative_to(artifact_root)
        except ValueError as exc:
            raise ValueError("job artifact path escaped artifact root") from exc
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def _is_cancelled(self, job_id: str) -> bool:
        latest = self._repository.get(job_id)
        return latest is not None and latest.status == VrmGenerationStatus.CANCELLED


def build_spec_from_prompt(prompt: str) -> dict[str, Any]:
    hair_color = "#b98a5a" if "棕" in prompt else "#2f2f35"
    eye_color = "#7fb8ff" if "蓝" in prompt else "#5a4638"
    primary_color = "#ffffff" if "白" in prompt else "#d9ecff"
    return {
        "identity": {
            "name": "小晏",
            "style": "soft_anime",
            "personality_visual_keywords": ["温柔", "安静", "亲近感"],
        },
        "face": {"eye_color": eye_color, "skin_tone": "#f7d8c8"},
        "hair": {"style": "short_bob", "color": hair_color},
        "clothes": {"preset": "home_dress", "primary_color": primary_color, "secondary_color": "#d9ecff"},
        "expressions": {"default": "soft_smile", "required": ["happy", "sad", "blink", "surprised", "thinking"]},
        "vrm": {"version": "0.x", "author": "xiao_yan_project", "license": "private_prototype"},
        "source_prompt": prompt,
    }
