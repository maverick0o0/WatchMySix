from __future__ import annotations

import asyncio
import shutil
import tarfile
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Deque, Dict, List, Optional

from fastapi import WebSocket

from .config import settings
from .models import BruteforceConfig, JobRequest, JobStatus, ToolResult
from .tools import TOOL_DEFINITIONS, ToolContext, ToolDefinition, run_command


DEFAULT_STATIC_WORDLIST = Path("/opt/watchmysix/wordlists/static-dns/best-dns-wordlist.txt")
DEFAULT_DYNAMIC_WORDLIST = Path("/opt/watchmysix/wordlists/dynamic-dns/words-merged.txt")
DEFAULT_RESOLVERS = Path("/opt/watchmysix/resolvers/resolvers.txt")


@dataclass
class Job:
    id: str
    request: JobRequest
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    message: Optional[str] = None
    data_path: Path = field(default_factory=Path)
    log_path: Path = field(default_factory=Path)
    results: List[ToolResult] = field(default_factory=list)
    merged_file: Optional[Path] = None
    probe_file: Optional[Path] = None
    log_buffer: Deque[str] = field(default_factory=lambda: deque(maxlen=settings.log_buffer_lines))
    subscribers: List[asyncio.Queue[str]] = field(default_factory=list)
    task: Optional[asyncio.Task[None]] = None


class JobNotFound(Exception):
    pass


class JobManager:
    def __init__(self) -> None:
        self.jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def create_job(self, request: JobRequest) -> Job:
        async with self._lock:
            job_id = uuid.uuid4().hex
            data_path = settings.data_dir / job_id
            data_path.mkdir(parents=True, exist_ok=True)
            log_path = data_path / "job.log"
            job = Job(
                id=job_id,
                request=request,
                data_path=data_path,
                log_path=log_path,
            )
            self.jobs[job_id] = job
        job.task = asyncio.create_task(self._execute(job))
        return job

    async def _execute(self, job: Job) -> None:
        job.status = JobStatus.RUNNING
        job.updated_at = datetime.utcnow()
        await self._log(job, "Job started")
        try:
            async with self._semaphore:
                await self._run_job(job)
            job.status = JobStatus.COMPLETED
            await self._log(job, "Job completed successfully")
        except Exception as exc:  # pragma: no cover - runtime errors
            job.status = JobStatus.FAILED
            job.message = str(exc)
            await self._log(job, f"Job failed: {exc}")
        finally:
            job.updated_at = datetime.utcnow()

    async def _run_job(self, job: Job) -> None:
        self._apply_bruteforce_defaults(job.request)
        available_tools = self._resolve_tools(job.request)
        context = ToolContext(
            job_id=job.id,
            targets=job.request.targets,
            workdir=job.data_path,
            environment=self._build_environment(job.request),
        )
        await self._log(job, f"Resolved tools: {', '.join(available_tools.keys())}")
        # Start tool executions concurrently
        tool_tasks = [
            asyncio.create_task(self._run_tool(job, context, tool)) for tool in available_tools.values()
        ]
        if job.request.static_bruteforce.enabled:
            await self._run_bruteforce(job, context, job.request.static_bruteforce, phase="static")
        if job.request.dynamic_bruteforce.enabled:
            await self._run_bruteforce(job, context, job.request.dynamic_bruteforce, phase="dynamic")
        if tool_tasks:
            await asyncio.gather(*tool_tasks)
        await self._merge_artifacts(job)

    def _apply_bruteforce_defaults(self, request: JobRequest) -> None:
        if request.static_bruteforce.enabled:
            if not request.static_bruteforce.wordlist:
                request.static_bruteforce.wordlist = str(DEFAULT_STATIC_WORDLIST)
            if not request.static_bruteforce.resolvers:
                request.static_bruteforce.resolvers = str(DEFAULT_RESOLVERS)
        if request.dynamic_bruteforce.enabled:
            if not request.dynamic_bruteforce.wordlist:
                request.dynamic_bruteforce.wordlist = str(DEFAULT_DYNAMIC_WORDLIST)
            if not request.dynamic_bruteforce.resolvers:
                request.dynamic_bruteforce.resolvers = str(DEFAULT_RESOLVERS)

    def _resolve_tools(self, request: JobRequest) -> Dict[str, ToolDefinition]:
        tools = {
            name: definition
            for name, definition in TOOL_DEFINITIONS.items()
            if definition.output_file
        }
        if request.tools:
            requested = {name for name in request.tools}
            tools = {name: tools[name] for name in requested if name in tools}
        for name in request.exclude_tools:
            tools.pop(name, None)
        return tools

    async def _run_tool(self, job: Job, context: ToolContext, tool: ToolDefinition) -> None:
        start_time = datetime.utcnow()
        result = ToolResult(
            tool=tool.name,
            return_code=None,
            output_file=str(job.data_path / (tool.output_file or f"{tool.name}.txt")),
            status="running",
            started_at=start_time,
            finished_at=None,
        )
        job.results.append(result)
        await self._log(job, f"Starting tool {tool.name}")
        output_path: Optional[Path] = None
        try:
            if tool.custom_runner:
                output_path = await tool.custom_runner(context, lambda message: self._log(job, f"[{tool.name}] {message}"))
            elif tool.command_builder:
                command = tool.command_builder(context)
                if not shutil.which(command[0]):
                    await self._log(job, f"Tool {tool.name} not found on PATH. Skipping.")
                    result.status = "skipped"
                    return
                else:
                    output_path, return_code = await run_command(
                        command,
                        workdir=job.data_path,
                        output_path=job.data_path / (tool.output_file or f"{tool.name}.txt"),
                        log=lambda message: self._log(job, f"[{tool.name}] {message}"),
                        environment=context.environment or None,
                    )
                    result.return_code = return_code
            else:
                await self._log(job, f"Tool {tool.name} has no runner configured")
                result.status = "skipped"
                return
            if output_path:
                result.status = "completed"
            else:
                result.status = "failed"
        except Exception as exc:  # pragma: no cover
            result.status = "error"
            result.error = str(exc)
            await self._log(job, f"Tool {tool.name} failed: {exc}")
        finally:
            result.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            if output_path:
                result.output_file = str(output_path)

    async def _run_bruteforce(
        self,
        job: Job,
        context: ToolContext,
        config: BruteforceConfig,
        phase: str,
    ) -> None:
        description = f"{phase.capitalize()} bruteforce"
        await self._log(job, f"Starting {description}")
        wordlist = config.wordlist
        resolvers = config.resolvers
        if not wordlist:
            await self._log(job, f"{description}: no wordlist provided, skipping")
            return
        executable = "puredns" if phase == "static" else "shuffledns"
        if not shutil.which(executable):
            await self._log(job, f"{description}: command {executable} not found, skipping")
            return
        targets = [target.strip() for target in context.targets if target.strip()]
        if not targets:
            await self._log(job, f"{description}: no valid targets provided, skipping")
            return
        output_path = job.data_path / f"{phase}_bruteforce.txt"
        existing_entries: list[str] = []
        seen: set[str] = set()
        if output_path.exists():
            for line in output_path.read_text().splitlines():
                clean = line.strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    existing_entries.append(clean)
        result = ToolResult(
            tool=f"{phase}_bruteforce",
            return_code=None,
            output_file=str(output_path),
            status="running",
            started_at=datetime.utcnow(),
            finished_at=None,
        )
        job.results.append(result)
        try:
            successful = False
            final_return_code: Optional[int] = None
            for target in targets:
                if phase == "static":
                    command = ["puredns", "bruteforce", str(wordlist), target]
                    resolver_path = str(resolvers or "resolvers.txt")
                    command.extend(["-r", resolver_path])
                else:
                    command = ["shuffledns", "-d", target, "-w", str(wordlist)]
                    resolver_path = str(resolvers or "resolvers.txt")
                    command.extend(["-r", resolver_path])
                if config.threads:
                    command.extend(["-t", str(config.threads)])
                if config.tools:
                    command.extend(config.tools)
                temp_output = job.data_path / f"{phase}_bruteforce_{uuid.uuid4().hex}.txt"
                await self._log(job, f"{description}: running against {target}")
                path, return_code = await run_command(
                    command,
                    workdir=job.data_path,
                    output_path=temp_output,
                    log=lambda message: self._log(job, f"[{phase}_bruteforce] {message}"),
                    environment=context.environment or None,
                )
                if path:
                    successful = True
                    final_return_code = 0
                    async with aiofiles.open(path, "r") as reader:
                        async for line in reader:
                            clean = line.strip()
                            if clean and clean not in seen:
                                seen.add(clean)
                                existing_entries.append(clean)
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
                else:
                    if final_return_code is None:
                        final_return_code = return_code
                    await self._log(job, f"{description}: command failed for {target} with code {return_code}")
                    try:
                        temp_output.unlink()
                    except FileNotFoundError:
                        pass
            if successful:
                async with aiofiles.open(output_path, "w") as writer:
                    for entry in existing_entries:
                        await writer.write(entry + "\n")
                result.status = "completed"
                result.return_code = final_return_code
            else:
                result.status = "failed"
                result.return_code = final_return_code
        except Exception as exc:  # pragma: no cover
            result.status = "error"
            result.error = str(exc)
            await self._log(job, f"{description} failed: {exc}")
        finally:
            result.finished_at = datetime.utcnow()

    async def _merge_artifacts(self, job: Job) -> None:
        await self._log(job, "Merging artifacts")
        txt_files = list(job.data_path.glob("*.txt"))
        merged_path = job.data_path / "subs.txt"
        seen: set[str] = set()
        async with aiofiles.open(merged_path, "w") as handle:
            for txt_file in txt_files:
                if txt_file == merged_path:
                    continue
                async with aiofiles.open(txt_file, "r") as reader:
                    async for line in reader:
                        normalized = line.strip()
                        if not normalized:
                            continue
                        if normalized not in seen:
                            seen.add(normalized)
                            await handle.write(normalized + "\n")
        job.merged_file = merged_path
        await self._log(job, f"Merged {len(seen)} unique entries into {merged_path.name}")
        await self._renew_with_anew(job, seen)
        job.probe_file = await self._probe_with_httpx(job, merged_path)

    async def _probe_with_httpx(self, job: Job, merged_path: Path) -> Optional[Path]:
        if not merged_path.exists():
            await self._log(job, "Merged file does not exist; skipping httpx probe")
            return None
        output_path = job.data_path / "httpx_probed.txt"
        command = ["httpx", "-silent", "-l", str(merged_path), "-o", str(output_path)]
        if not shutil.which(command[0]):
            await self._log(job, "httpx command not found; skipping probe")
            return None
        path, _ = await run_command(
            command,
            workdir=job.data_path,
            output_path=output_path,
            log=lambda message: self._log(job, f"[httpx] {message}"),
            environment=None,
        )
        if path:
            await self._log(job, f"httpx probe completed: {output_path}")
        else:
            await self._log(job, "httpx probe failed")
        return path

    def _build_environment(self, request: JobRequest) -> Dict[str, str]:
        environment = {**request.environment}
        if settings.api.chaos_key:
            environment.setdefault("CHAOS_KEY", settings.api.chaos_key)
        if settings.api.github_token:
            environment.setdefault("GITHUB_TOKEN", settings.api.github_token)
        if settings.api.gitlab_token:
            environment.setdefault("GITLAB_TOKEN", settings.api.gitlab_token)
        return environment

    async def _log(self, job: Job, message: str) -> None:
        timestamp = datetime.utcnow()
        line = f"{timestamp.isoformat()} | {message}"
        job.log_buffer.append(line)
        async with aiofiles.open(job.log_path, "a") as handle:
            await handle.write(line + "\n")
        for subscriber in list(job.subscribers):
            try:
                subscriber.put_nowait(line)
            except asyncio.QueueFull:  # pragma: no cover - queue too small
                pass

    async def stream_logs(self, job_id: str) -> AsyncGenerator[str, None]:
        job = self.jobs.get(job_id)
        if not job:
            raise JobNotFound(job_id)
        queue: asyncio.Queue[str] = asyncio.Queue()
        job.subscribers.append(queue)
        try:
            for line in job.log_buffer:
                yield line
            while True:
                line = await queue.get()
                yield line
        finally:
            job.subscribers.remove(queue)

    async def attach_websocket(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        job = self.jobs.get(job_id)
        if not job:
            await websocket.close(code=4040)
            return
        queue: asyncio.Queue[str] = asyncio.Queue()
        job.subscribers.append(queue)
        try:
            for line in job.log_buffer:
                await websocket.send_text(line)
            while True:
                line = await queue.get()
                await websocket.send_text(line)
        except asyncio.CancelledError:  # pragma: no cover - connection drop
            raise
        except Exception:  # pragma: no cover - websocket errors
            pass
        finally:
            job.subscribers.remove(queue)
            await websocket.close()

    async def _renew_with_anew(self, job: Job, entries: set[str]) -> None:
        history_path = job.data_path / "subs_history.txt"
        existing: set[str] = set()
        if history_path.exists():
            existing.update(line.strip() for line in history_path.read_text().splitlines() if line.strip())
        new_values = [entry for entry in entries if entry not in existing]
        if not new_values:
            await self._log(job, "anew: no new entries to append")
            return
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a") as handle:
            for entry in new_values:
                handle.write(entry + "\n")
        await self._log(job, f"anew: appended {len(new_values)} new entries to {history_path.name}")

    def get_job(self, job_id: str) -> Job:
        job = self.jobs.get(job_id)
        if not job:
            raise JobNotFound(job_id)
        return job

    def list_jobs(self) -> List[Job]:
        return list(self.jobs.values())

    def get_artifacts(self, job_id: str) -> List[Path]:
        job = self.get_job(job_id)
        return sorted(p for p in job.data_path.glob("*") if p.is_file())

    def get_artifact(self, job_id: str, filename: str) -> Path:
        job = self.get_job(job_id)
        path = job.data_path / filename
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(filename)
        return path

    def build_archive(self, job_id: str) -> Path:
        job = self.get_job(job_id)
        archive_path = job.data_path / f"{job_id}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for artifact in job.data_path.glob("*"):
                if artifact.name == archive_path.name:
                    continue
                archive.add(artifact, arcname=artifact.name)
        return archive_path


# Lazy import to avoid circular dependency
try:
    import aiofiles  # type: ignore
except ImportError:  # pragma: no cover
    aiofiles = None  # type: ignore

if aiofiles is None:  # pragma: no cover
    raise RuntimeError("aiofiles dependency must be installed to use JobManager")


job_manager = JobManager()
