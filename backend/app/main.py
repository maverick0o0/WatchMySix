from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .job_runner import JobNotFound, job_manager
from .models import ArtifactList, JobDetail, JobListResponse, JobRequest, JobResponse

app = FastAPI(title="WatchMySix Backend", version="0.1.0")


@app.on_event("startup")
async def startup_event() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)


@app.post("/jobs", response_model=JobResponse, status_code=202)
async def create_job(request: JobRequest) -> JobResponse:
    job = await job_manager.create_job(request)
    return JobResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@app.get("/jobs", response_model=JobListResponse)
async def list_jobs() -> JobListResponse:
    jobs = [
        JobResponse(
            job_id=job.id,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            message=job.message,
        )
        for job in job_manager.list_jobs()
    ]
    return JobListResponse(jobs=jobs)


@app.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(job_id: str) -> JobDetail:
    try:
        job = job_manager.get_job(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Job not found")
    artifacts = [path.name for path in job_manager.get_artifacts(job_id)]
    return JobDetail(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        message=job.message,
        targets=job.request.targets,
        tools=[result.tool for result in job.results],
        data_path=job.data_path,
        artifacts=artifacts,
    )


@app.get("/jobs/{job_id}/logs")
async def get_logs(job_id: str) -> JSONResponse:
    try:
        job = job_manager.get_job(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.log_path.exists():
        return JSONResponse(content={"lines": []})
    lines = job.log_path.read_text().splitlines()
    return JSONResponse(content={"lines": lines})


@app.websocket("/ws/jobs/{job_id}/logs")
async def websocket_logs(websocket: WebSocket, job_id: str) -> None:
    await job_manager.attach_websocket(job_id, websocket)


@app.get("/jobs/{job_id}/artifacts", response_model=ArtifactList)
async def list_artifacts(job_id: str) -> ArtifactList:
    try:
        artifacts = job_manager.get_artifacts(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Job not found")
    return ArtifactList(files=[artifact.name for artifact in artifacts])


@app.get("/jobs/{job_id}/artifacts/{filename}")
async def download_artifact(job_id: str, filename: str) -> FileResponse:
    try:
        path = job_manager.get_artifact(job_id, filename)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Job not found")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)


@app.get("/jobs/{job_id}/archive")
async def download_archive(job_id: str) -> FileResponse:
    try:
        archive = job_manager.build_archive(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Job not found")
    if not archive.exists():
        raise HTTPException(status_code=404, detail="Archive not available")
    return FileResponse(archive, filename=archive.name)
