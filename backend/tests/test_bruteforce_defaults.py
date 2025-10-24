from __future__ import annotations

from pathlib import Path
from types import MethodType
from typing import List

import pytest

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.job_runner import (
    DEFAULT_DYNAMIC_WORDLIST,
    DEFAULT_RESOLVERS,
    DEFAULT_STATIC_WORDLIST,
    Job,
    JobManager,
)
from app.models import JobRequest
from app.tools import ToolContext


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_ui_payload_injects_bruteforce_defaults(tmp_path, monkeypatch):
    manager = JobManager()

    payload = {
        "targets": ["example.com"],
        "tools": [
            "crtsh",
            "waybackurls",
            "gau",
            "waymore",
            "subfinder",
            "chaos",
            "github-subdomains",
            "gitlab-subdomains",
            "source_scan",
            "urlfinder",
        ],
        "static_bruteforce": {"enabled": True},
        "dynamic_bruteforce": {"enabled": True},
    }

    request = JobRequest(**payload)
    job = Job(
        id="job1",
        request=request,
        data_path=tmp_path,
        log_path=tmp_path / "job.log",
    )

    recorded_commands: List[List[str]] = []
    messages: list[str] = []

    async def fake_log(self: JobManager, job_obj: Job, message: str) -> None:
        messages.append(message)

    async def fake_run_command(command, workdir, output_path, log, environment):
        recorded_commands.append(command)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("simulated output\n")
        await log("Simulated execution")
        return output_path, 0

    manager._log = MethodType(fake_log, manager)
    monkeypatch.setattr("app.job_runner.run_command", fake_run_command)
    monkeypatch.setattr("app.job_runner.shutil.which", lambda _: "/usr/bin/fake")

    manager._apply_bruteforce_defaults(job.request)

    context = ToolContext(
        job_id=job.id,
        targets=job.request.targets,
        workdir=job.data_path,
        environment={},
    )

    await manager._run_bruteforce(job, context, job.request.static_bruteforce, phase="static")
    await manager._run_bruteforce(job, context, job.request.dynamic_bruteforce, phase="dynamic")

    assert job.request.static_bruteforce.wordlist == str(DEFAULT_STATIC_WORDLIST)
    assert job.request.dynamic_bruteforce.wordlist == str(DEFAULT_DYNAMIC_WORDLIST)
    assert job.request.static_bruteforce.resolvers == str(DEFAULT_RESOLVERS)
    assert job.request.dynamic_bruteforce.resolvers == str(DEFAULT_RESOLVERS)

    assert recorded_commands, "Expected bruteforce commands to be executed"
    static_command = recorded_commands[0]
    dynamic_command = recorded_commands[1]
    assert str(DEFAULT_STATIC_WORDLIST) in static_command
    assert str(DEFAULT_RESOLVERS) in static_command
    assert str(DEFAULT_DYNAMIC_WORDLIST) in dynamic_command
    assert str(DEFAULT_RESOLVERS) in dynamic_command

    assert all("no wordlist provided" not in message.lower() for message in messages)
