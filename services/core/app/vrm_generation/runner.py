from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock

from app.vrm_generation.models import VrmGenerationJob, VrmGenerationStatus
from app.vrm_generation.service import VrmGenerationService


class VrmGenerationTaskRunner:
    def __init__(self, service: VrmGenerationService) -> None:
        self._service = service
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vrm-generation")
        self._lock = Lock()
        self._futures: dict[str, Future[None]] = {}
        self._cancelled: set[str] = set()

    @property
    def service(self) -> VrmGenerationService:
        return self._service

    def submit(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._futures:
                return
            self._cancelled.discard(job_id)
            self._futures[job_id] = self._executor.submit(self._run, job_id)

    def cancel(self, job_id: str) -> VrmGenerationJob | None:
        job = self._service.get_job(job_id)
        if job is None:
            return None
        if job.status in {VrmGenerationStatus.COMPLETED, VrmGenerationStatus.FAILED, VrmGenerationStatus.CANCELLED}:
            return job

        with self._lock:
            future = self._futures.get(job_id)
            self._cancelled.add(job_id)
            if future is not None:
                future.cancel()
        return self._service.mark_cancelled(job_id)

    def _run(self, job_id: str) -> None:
        try:
            with self._lock:
                if job_id in self._cancelled:
                    return
            self._service.run_job(job_id)
        finally:
            with self._lock:
                self._futures.pop(job_id, None)
