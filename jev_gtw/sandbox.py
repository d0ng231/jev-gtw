"""Optional local probes: explicit isolation, bounded capture, private artifacts.

No host-shell fallback. The Docker daemon / Apptainer installation and image are
operator-controlled. Containers do not defend against kernel exploits or timing
channels; provision CPU/memory/disk quotas for the server as well.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import time
import uuid


@dataclass(frozen=True)
class Capture:
    text: str = field(repr=False)
    complete: bool
    artifact_id: str


class ProbeRunner:
    def __init__(self, *, backend, image, artifact_root, image_sha256=None, executable=None, timeout=30):
        if backend not in ("docker", "apptainer") or type(timeout) is not int or not 1 <= timeout <= 120:
            raise ValueError("Invalid sandbox configuration")
        self.backend, self.image, self.timeout = backend, image, timeout
        self.executable = executable or shutil.which(backend)
        if not self.executable:
            raise ValueError("Sandbox executable is unavailable")
        if backend == "docker":
            if not re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", image):
                raise ValueError("Docker image must be pinned by digest")
        else:
            path = Path(image).resolve(strict=True)
            if not path.is_file() or not re.fullmatch(r"[a-f0-9]{64}", image_sha256 or ""):
                raise ValueError("Local SIF and SHA256 are required")
            with path.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else self._sha(stream)
            if checksum != image_sha256:
                raise ValueError("Sandbox image hash mismatch")
            self.image = str(path)
        self.root = Path(artifact_root).absolute()
        if self.root.is_symlink():
            raise ValueError("Artifact root cannot be a symlink")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.stat().st_uid != os.getuid() or self.root.stat().st_mode & 0o077:
            raise ValueError("Artifact root must be owner-only")
        self.scratch = Path(os.environ.get("TMPDIR", ""))
        if not self.scratch.is_absolute() or not self.scratch.is_dir() or str(self.scratch.resolve()) == "/tmp" or "/tmp" in [str(p) for p in self.scratch.resolve().parents]:
            raise ValueError("Set TMPDIR to a private scratch directory outside /tmp")

    @staticmethod
    def _sha(stream):
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
        return h.hexdigest()

    def argv(self, job: Path, name: str):
        if self.backend == "docker":
            return [self.executable, "run", "--rm", "--name", name, "--network=none", "--read-only",
                    "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=32", "--memory=512m", "--cpus=1",
                    "--user", f"{os.getuid()}:{os.getgid()}", "--workdir", "/outputs", "--tmpfs", "/scratch:rw,size=64m,mode=1777",
                    "--env", "TMPDIR=/scratch", "--mount", f"type=bind,source={job / 'inputs'},target=/inputs,readonly",
                    "--mount", f"type=bind,source={job / 'outputs'},target=/outputs",
                    "--mount", f"type=bind,source={job / 'program.py'},target=/program.py,readonly",
                    self.image, "python", "-I", "-B", "/program.py"]
        return [self.executable, "--quiet", "exec", "--containall", "--cleanenv", "--no-home",
                "--no-mount", "hostfs,cwd,bind-paths", "--workdir", str(job / "state"),
                "--bind", f"{job / 'inputs'}:/inputs:ro", "--bind", f"{job / 'outputs'}:/outputs:rw",
                "--bind", f"{job / 'program.py'}:/program.py:ro", "--pwd", "/outputs",
                "--net", "--network", "none", "--env", "TMPDIR=/outputs/.scratch",
                self.image, "python", "-I", "-B", "/program.py"]

    def run(self, code: str, inputs: dict[str, bytes]) -> Capture:
        artifact_id = uuid.uuid4().hex
        job = self.root / artifact_id
        job.mkdir(mode=0o700)
        for folder in ("inputs", "outputs", "state"):
            (job / folder).mkdir(mode=0o700)
        (job / "outputs/.scratch").mkdir(mode=0o700)
        for handle, raw in inputs.items():
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", handle):
                raise ValueError("Invalid input handle")
            (job / "inputs" / handle).write_bytes(raw)
        # Limits are installed before agent code and cannot be raised by it.
        wrapper = ("import resource\n"
                   "resource.setrlimit(resource.RLIMIT_FSIZE, (16777216, 16777216))\n"
                   f"resource.setrlimit(resource.RLIMIT_CPU, ({self.timeout}, {self.timeout}))\n"
                   f"exec(compile({code!r}, '<probe>', 'exec'))\n")
        (job / "program.py").write_text(wrapper)
        name = "jev-gtw-" + artifact_id
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "TMPDIR": str(self.scratch),
               "APPTAINER_TMPDIR": str(self.scratch), "SINGULARITY_TMPDIR": str(self.scratch),
               "APPTAINER_CACHEDIR": str(job / "state/cache"), "SINGULARITY_CACHEDIR": str(job / "state/cache")}
        output, complete = bytearray(), True
        process = None
        try:
            process = subprocess.Popen(self.argv(job, name), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, env=env, cwd=job, start_new_session=True)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline, limit = time.monotonic() + self.timeout, 96_000
            try:
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        complete = False
                        break
                    for key, _ in selector.select(0.05):
                        block = os.read(key.fd, min(8192, limit + 1 - len(output)))
                        if not block:
                            selector.unregister(key.fileobj)
                        else:
                            output.extend(block)
                            if len(output) > limit:
                                complete = False
                                break
                    if not complete:
                        break
                if complete:
                    try:
                        process.wait(timeout=max(0.01, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        complete = False
            finally:
                selector.close()
                process.stdout.close()
        except Exception:
            complete = False
        finally:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
            if self.backend == "docker":
                # Killing the CLI alone does not terminate a detached container.
                try:
                    subprocess.run([self.executable, "rm", "-f", name], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=10, env=env)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            shutil.rmtree(job / "inputs")
            shutil.rmtree(job / "state")
        # Raw capture stays with the private artifacts for the operator.
        (job / "capture.bin").write_bytes(output[:96_000])
        try:
            text = output[:96_000].decode("utf-8")
        except UnicodeDecodeError:
            text, complete = "", False
        return Capture(text, complete, artifact_id)

