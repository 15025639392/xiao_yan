from __future__ import annotations

from pathlib import Path
from threading import RLock

from app.utils.file_utils import read_json_file, write_json_file
from app.vrm_generation.models import VrmGenerationJob, VrmGenerationStatus

PERSIST_VERSION = "v1"


class VrmGenerationRepository:
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path
        self._lock = RLock()

    def save(self, job: VrmGenerationJob) -> None:
        with self._lock:
            self._save_locked(job)

    def _save_locked(self, job: VrmGenerationJob) -> None:
        payload = self._load_payload()
        jobs = payload.setdefault("jobs", {})
        current = self._get_locked(job.job_id)
        if current is not None and current.status == VrmGenerationStatus.CANCELLED and job.status != VrmGenerationStatus.CANCELLED:
            return
        jobs[job.job_id] = job.model_dump(mode="json")
        write_json_file(self._storage_path, payload, ensure_ascii=False, indent=2, create_parent=True)

    def get(self, job_id: str) -> VrmGenerationJob | None:
        with self._lock:
            return self._get_locked(job_id)

    def list_recent(self, limit: int = 20) -> list[VrmGenerationJob]:
        with self._lock:
            payload = self._load_payload()
            jobs: list[VrmGenerationJob] = []
            for raw_job in payload.get("jobs", {}).values():
                if not isinstance(raw_job, dict):
                    continue
                try:
                    jobs.append(VrmGenerationJob.model_validate(raw_job))
                except Exception:
                    continue
            jobs.sort(key=lambda job: job.created_at, reverse=True)
            return jobs[:limit]

    def _get_locked(self, job_id: str) -> VrmGenerationJob | None:
        payload = self._load_payload()
        raw_job = payload.get("jobs", {}).get(job_id)
        if not isinstance(raw_job, dict):
            return None
        try:
            return VrmGenerationJob.model_validate(raw_job)
        except Exception:
            return None

    def _load_payload(self) -> dict:
        if not self._storage_path.exists():
            return {"version": PERSIST_VERSION, "jobs": {}}
        try:
            payload = read_json_file(self._storage_path)
        except Exception:
            return {"version": PERSIST_VERSION, "jobs": {}}
        if not isinstance(payload, dict):
            return {"version": PERSIST_VERSION, "jobs": {}}
        jobs = payload.get("jobs")
        if not isinstance(jobs, dict):
            payload["jobs"] = {}
        payload.setdefault("version", PERSIST_VERSION)
        return payload
