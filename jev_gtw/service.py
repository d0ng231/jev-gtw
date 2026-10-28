"""Host-owned source registry. MCP callers supply handles, never policy or paths."""
from __future__ import annotations

import base64
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
from threading import RLock

from .core import Access, Context, Gateway, Observation, FEEDBACK
from .images import MAX_IMAGE_BYTES
from .judge import StartLuxJudge

HANDLE = re.compile(r"[a-z][a-z0-9_-]{0,63}")


@dataclass(frozen=True)
class Source:
    path: str
    kind: str
    access: Access
    probe_view: str = "local"
    public_context: str | None = None


def read_beneath(root: Path, relative: str, limit: int) -> bytes:
    """Read a bounded regular file with no symlink traversal (POSIX)."""
    parts = PurePosixPath(relative).parts
    if not parts or relative.startswith("/") or any(p in (".", "..") for p in relative.split("/")):
        raise ValueError("Expected a relative source path")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        source = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            if not stat.S_ISREG(os.fstat(source).st_mode):
                raise ValueError("Only regular files are supported")
            with os.fdopen(source, "rb", closefd=False) as stream:
                return stream.read(limit + 1)
        finally:
            os.close(source)
    finally:
        os.close(fd)


class Service:
    def __init__(self, root, context, sources, gateway, runner=None):
        self.root, self.context = Path(root).resolve(strict=True), context
        self.sources, self.gateway, self.runner = dict(sources), gateway, runner
        for handle, source in self.sources.items():
            if not HANDLE.fullmatch(handle):
                raise ValueError("Invalid source handle")
            if source.public_context is not None:
                target = self.sources.get(source.public_context)
                if target is None or target.access.view != "approved" or source.public_context == handle:
                    raise ValueError("Navigation must reference a separate exact approved source")
        self.history = []
        self._lock = RLock()

    @classmethod
    def from_config(cls, path):
        config_path = Path(path).resolve(strict=True)
        config = json.loads(config_path.read_text())
        if config.get("version") != 1:
            raise ValueError("Expected configuration version 1")
        context = Context(**config["context"], session=secrets.token_hex(16))
        sources = {}
        for handle, spec in config["sources"].items():
            if not HANDLE.fullmatch(handle) or spec.get("kind", "text") not in ("text", "png"):
                raise ValueError("Invalid source handle or kind")
            source = Source(spec["path"], spec.get("kind", "text"), Access(**spec.get("access", {})),
                            spec.get("probe_view", "local"), spec.get("public_context"))
            if source.probe_view not in ("local", "contextual"):
                raise ValueError("Invalid probe-output policy")
            # Validation is lexical here; actual reads use descriptor-relative opens.
            parts = source.path.split("/")
            if source.path.startswith("/") or any(p in ("", ".", "..") for p in parts):
                raise ValueError("Source paths must be relative")
            sources[handle] = source
        judge = None
        if config.get("inspector"):
            spec = dict(config["inspector"])
            token_env = spec.pop("token_env", "JEV_GTW_INSPECTOR_TOKEN")
            judge = StartLuxJudge(token=os.environ.get(token_env, ""), **spec)
        runner = None
        if config.get("sandbox"):
            from .sandbox import ProbeRunner
            runner = ProbeRunner(**config["sandbox"])
        return cls(config_path.parent / config["root"], context, sources, Gateway(judge, **config.get("gateway", {})), runner)

    def catalog(self):
        # Handles, kinds and coarse policy are deliberately public operator metadata.
        return {"sources": [{"id": handle, "kind": source.kind, "view": source.access.view,
                            "local_compute": source.access.local_compute and source.access.view != "deny",
                            "public_context": source.public_context}
                           for handle, source in self.sources.items()],
                "compute_available": self.runner is not None}

    @staticmethod
    def _held():
        return {"action": "hold", "reason": "source_unavailable", "text": FEEDBACK["hold"]}

    def _review(self, observation, access):
        context = replace(self.context, history=tuple(self.history[-4:]))
        decision = self.gateway.inspect(context, observation, access)
        messages = self.gateway.messages(context, decision, tool_call_id=secrets.token_hex(12))
        self.gateway.validate_request(context, messages)
        result = {"action": decision.action, "reason": decision.reason, "text": messages[0]["content"]}
        if len(messages) == 2:
            url = messages[1]["content"][1]["image_url"]["url"]
            result["image_base64"] = url.removeprefix("data:image/png;base64,")
        # Only admitted text/fixed feedback is added to future inspector context.
        # Identical consecutive views add no evidence; avoid cycling the model
        # context and invalidating exact-request cache entries on every retry.
        latest = result["text"][:2048]
        if not self.history or self.history[-1] != latest:
            self.history.append(latest)
        del self.history[:-4]
        return result

    def _next_steps(self, source_id, source, result):
        if result["action"] == "show":
            return result
        steps = []
        if source.public_context is not None:
            steps.append({"tool":"gateway_read", "arguments":{"source_id":source.public_context}})
        if self.runner is not None and source.access.local_compute and source.access.view != "deny":
            steps.append({"tool":"gateway_compute", "source_ids":[source_id]})
        if not steps:
            steps.append({"action":"operator_review"})
        result["next_steps"] = steps
        return result

    def read(self, source_id: str):
        with self._lock:
            source = self.sources.get(source_id)
            if source is None:
                return self._held()
            # Protected/denied reads are withheld before opening the source.
            if source.access.view in ("local", "deny"):
                return self._next_steps(source_id, source, self._review(Observation(), source.access))
            try:
                limit = MAX_IMAGE_BYTES if source.kind == "png" else self.gateway.max_chars * 4
                raw = read_beneath(self.root, source.path, limit)
                observation = (Observation(image=raw, complete=len(raw) <= limit) if source.kind == "png"
                               else Observation(text=raw.decode("utf-8"), complete=len(raw) <= limit))
                return self._next_steps(source_id, source, self._review(observation, source.access))
            except Exception:
                # Never relay OS exceptions, filenames, parse errors or source bytes.
                return self._held()

    def compute(self, source_ids: list[str], code: str):
        """Run code only inside an explicitly configured isolated executor."""
        with self._lock:
            if (self.runner is None or type(source_ids) is not list or not 1 <= len(source_ids) <= 8
                    or any(type(s) is not str for s in source_ids) or len(set(source_ids)) != len(source_ids)
                    or type(code) is not str or not 0 < len(code.encode()) <= 32_768):
                return self._held()
            selected = [self.sources.get(handle) for handle in source_ids]
            if any(s is None or not s.access.local_compute or s.access.view == "deny" for s in selected):
                return self._held()
            try:
                # Snapshots prevent path changes and symlinks from widening the mount.
                inputs = {}
                for handle, source in zip(source_ids, selected):
                    raw = read_beneath(self.root, source.path, 16 * 1024 * 1024)
                    if len(raw) > 16 * 1024 * 1024:
                        return self._held()
                    inputs[handle] = raw
                capture = self.runner.run(code, inputs)
                output_access = Access("contextual" if all(s.probe_view == "contextual" for s in selected) else "local")
                # Return codes and exception messages have no separate release path.
                result = self._review(Observation(text=capture.text, complete=capture.complete), output_access)
                result["artifact_id"] = capture.artifact_id  # random, independent of input or success
                return result
            except Exception:
                return self._held()

