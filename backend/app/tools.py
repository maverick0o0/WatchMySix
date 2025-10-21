from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional

from .config import settings


@dataclass
class ToolContext:
    job_id: str
    targets: List[str]
    workdir: Path
    environment: Dict[str, str]


@dataclass
class ToolDefinition:
    name: str
    command_builder: Callable[[ToolContext], List[str]] | None = None
    output_file: Optional[str] = None
    description: str = ""
    optional: bool = True
    custom_runner: Callable[[ToolContext, Callable[[str], Awaitable[None]]], Awaitable[Optional[Path]]] | None = None

    def is_available(self) -> bool:
        if self.custom_runner:
            return True
        if not self.command_builder:
            return False
        cmd = self.command_builder(ToolContext(job_id="_", targets=[], workdir=settings.data_dir, environment={}))
        if not cmd:
            return False
        executable = cmd[0]
        return shutil.which(executable) is not None


async def run_command(
    command: List[str],
    workdir: Path,
    output_path: Path,
    log: Callable[[str], Awaitable[None]],
    environment: Optional[Dict[str, str]] = None,
) -> tuple[Optional[Path], int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = None
    if environment:
        import os
        env = {**os.environ, **environment}
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(workdir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    async with aiofiles.open(output_path, "w") as file_handle:
        assert process.stdout is not None
        async for line in process.stdout:
            text = line.decode().rstrip()
            await log(text)
            await file_handle.write(text + "\n")
    return_code = await process.wait()
    await log(f"Command {' '.join(command)} finished with code {return_code}")
    if return_code != 0:
        return None, return_code
    return output_path, return_code


async def run_crtsh(context: ToolContext, log: Callable[[str], Awaitable[None]]) -> Optional[Path]:
    try:
        import httpx
    except ImportError:  # pragma: no cover - dependency is declared but guard for safety
        await log("httpx is required for crt.sh queries but is not installed")
        return None

    output_path = context.workdir / "crtsh.txt"
    async with httpx.AsyncClient(timeout=30) as client:
        entries: set[str] = set()
        for target in context.targets:
            url = "https://crt.sh/?output=json&q=" + target
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                for item in data:
                    name_value = item.get("name_value")
                    if not name_value:
                        continue
                    for line in str(name_value).split("\n"):
                        clean = line.strip()
                        if clean:
                            entries.add(clean)
                await log(f"crt.sh retrieved {len(data)} certificates for {target}")
            except Exception as exc:  # pragma: no cover - network errors
                await log(f"crt.sh lookup failed for {target}: {exc}")
        if not entries:
            await log("No crt.sh entries found")
        async with aiofiles.open(output_path, "w") as handle:
            for entry in sorted(entries):
                await handle.write(entry + "\n")
    return output_path if output_path.exists() else None


try:
    import aiofiles  # type: ignore
except ImportError:  # pragma: no cover
    aiofiles = None  # type: ignore


if aiofiles is None:  # pragma: no cover - executed when aiofiles missing
    raise RuntimeError("aiofiles dependency must be installed to use tool runner")


def build_tool_definitions() -> Dict[str, ToolDefinition]:
    def simple_command(tool: str, *args: str, output: Optional[str] = None) -> ToolDefinition:
        def builder(context: ToolContext) -> List[str]:
            command = [tool, *args]
            if context.targets:
                command.extend(context.targets)
            return command

        return ToolDefinition(name=tool, command_builder=builder, output_file=output or f"{tool}.txt")

    tools: Dict[str, ToolDefinition] = {
        "crtsh": ToolDefinition(
            name="crtsh",
            custom_runner=run_crtsh,
            output_file="crtsh.txt",
            description="Fetches certificates from crt.sh",
        ),
        "waybackurls": simple_command("waybackurls", output="waybackurls.txt"),
        "gau": simple_command("gau", output="gau.txt"),
        "waymore": simple_command("waymore", output="waymore.txt"),
        "subfinder": simple_command("subfinder", "-silent", output="subfinder.txt"),
        "chaos": simple_command("chaos", "-silent", output="chaos.txt"),
        "github-subdomains": simple_command("github-subdomains", output="github-subdomains.txt"),
        "gitlab-subdomains": simple_command("gitlab-subdomains", output="gitlab-subdomains.txt"),
        "source_scan": simple_command("source_scan", output="source_scan.txt"),
        "urlfinder": simple_command("urlfinder", output="urlfinder.txt"),
        "httpx": simple_command("httpx", "-silent", output="httpx.txt"),
        "dnsx": simple_command("dnsx", "-silent", output="dnsx.txt"),
        "puredns": simple_command("puredns", "resolve", output="puredns.txt"),
        "shuffledns": simple_command("shuffledns", "-silent", output="shuffledns.txt"),
        "gotator": simple_command("gotator", output="gotator.txt"),
        "alterx": simple_command("alterx", output="alterx.txt"),
    }
    return tools


TOOL_DEFINITIONS = build_tool_definitions()
