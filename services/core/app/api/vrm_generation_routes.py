from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.vrm_generation.models import VrmGenerationArtifacts, VrmGenerationJob, VrmGenerationJobList, VrmGenerationRequest
from app.vrm_generation.runner import VrmGenerationTaskRunner
from app.vrm_generation.runtime import build_vrm_generation_service
from app.vrm_generation.service import VrmGenerationService


def get_vrm_generation_runner(request: Request) -> VrmGenerationTaskRunner:
    runner = getattr(request.app.state, "vrm_generation_runner", None)
    if runner is None:
        runner = VrmGenerationTaskRunner(build_vrm_generation_service())
        request.app.state.vrm_generation_runner = runner
    return runner


def get_vrm_generation_service(request: Request) -> VrmGenerationService:
    return get_vrm_generation_runner(request).service


def build_vrm_generation_router() -> APIRouter:
    router = APIRouter(prefix="/vrm-generation")

    @router.post("/jobs")
    def create_job(payload: VrmGenerationRequest, request: Request) -> VrmGenerationJob:
        runner = get_vrm_generation_runner(request)
        job = runner.service.create_job(payload)
        runner.submit(job.job_id)
        return job

    @router.get("/jobs")
    def list_jobs(request: Request, limit: int = Query(default=20, ge=1, le=50)) -> VrmGenerationJobList:
        service = get_vrm_generation_service(request)
        return VrmGenerationJobList(items=service.list_recent_jobs(limit=limit))

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str, request: Request) -> VrmGenerationJob:
        service = get_vrm_generation_service(request)
        job = service.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="vrm generation job not found")
        return job

    @router.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, request: Request) -> VrmGenerationJob:
        runner = get_vrm_generation_runner(request)
        job = runner.cancel(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="vrm generation job not found")
        return job

    @router.get("/jobs/{job_id}/artifacts")
    def get_artifacts(job_id: str, request: Request) -> VrmGenerationArtifacts:
        service = get_vrm_generation_service(request)
        job = service.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="vrm generation job not found")
        return job.artifacts

    return router
