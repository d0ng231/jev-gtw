"""One release check, three outcomes, with host-owned source permissions."""
from __future__ import annotations

import base64
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import secrets
from threading import RLock
import time
from typing import Callable

from .images import validate_png
from .signals import categories

MAX_TEXT = 24_000
SHOW_THRESHOLD = 0.98
FEEDBACK = {
    "local": "[Gateway] Content withheld. Write a local probe to process the source; keep records and derived private outputs local. Use an approved public view for navigation.",
    "hold": "[Gateway] Content withheld. Use an approved source or ask the operator to review the permitted scope.",
}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Context:
    task: str
    policy: str
    recipient: str = "coding-agent model context"
    session: str = "default"
    history: tuple[str, ...] = ()

    def __post_init__(self):
        if any(type(v) is not str or not v.strip() for v in (self.task, self.policy, self.recipient, self.session)):
            raise ValueError("Context requires nonempty trusted strings")
        if type(self.history) is not tuple or any(type(v) is not str for v in self.history):
            raise ValueError("History must be an immutable tuple of admitted text")


@dataclass(frozen=True)
class Access:
    """The host grants access. Tool arguments and source text cannot grant it."""
    view: str = "local"  # local / deny / contextual / approved
    local_compute: bool = True
    approved_sha256: str | None = None

    def __post_init__(self):
        if self.view not in {"local", "deny", "contextual", "approved"} or type(self.local_compute) is not bool:
            raise ValueError("Invalid source policy")
        if self.view == "approved" and (type(self.approved_sha256) is not str or len(self.approved_sha256) != 64
                                        or any(c not in "0123456789abcdef" for c in self.approved_sha256)):
            raise ValueError("Approved views require an exact trusted fingerprint")


@dataclass(frozen=True)
class Observation:
    text: str = field(default="", repr=False)
    image: bytes | None = field(default=None, repr=False)
    complete: bool = True
    source: str = "tool output"
    request: str = ""

    def __post_init__(self):
        if any(type(v) is not str for v in (self.text, self.source, self.request)):
            raise ValueError("Observation requires text fields")
        if self.image is not None and type(self.image) is not bytes:
            raise ValueError("Image must be immutable bytes")
        if type(self.complete) is not bool:
            raise ValueError("Completeness must be explicit")

    def fingerprint(self):
        return digest({"text": self.text,
                       "image_sha256": hashlib.sha256(self.image).hexdigest() if self.image is not None else None})


@dataclass(frozen=True)
class Assessment:
    permitted: float
    request_sha256: str = ""
    cached: bool = False

    def validate(self):
        if type(self.permitted) not in (int, float) or not math.isfinite(self.permitted) or not 0 <= self.permitted <= 1:
            raise ValueError("Expected a finite permission score")
        if type(self.cached) is not bool:
            raise ValueError("Expected a boolean cache indicator")


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    capability: str = field(repr=False)


class Gateway:
    """Use one instance per agent session. Scores are not calibrated guarantees.

    Retain this object outside agent-controlled code. The default policy is
    local-only; contextual review is a host opt-in. Redaction is not an automatic
    release path. Submit a transformed view as a new observation to review it.
    """

    def __init__(self, judge: Callable | None = None, *, show_threshold=SHOW_THRESHOLD, max_chars=MAX_TEXT,
                 max_receipts=4096):
        if type(show_threshold) not in (int, float) or not math.isfinite(show_threshold) or not 0 < show_threshold <= 1:
            raise ValueError("Invalid threshold")
        if type(max_chars) is not int or not 1 <= max_chars <= 1_000_000:
            raise ValueError("Invalid text limit")
        if type(max_receipts) is not int or not 2 <= max_receipts <= 65_536:
            raise ValueError("Invalid receipt limit")
        self.judge, self.threshold, self.max_chars = judge, show_threshold, max_chars
        self.max_receipts = max_receipts
        self._pending, self._admitted = {}, OrderedDict()
        self._lock = RLock()
        self.events = []

    def inspect(self, context: Context, observation: Observation, access: Access = Access()) -> Decision:
        started = time.perf_counter()
        event = {"context_sha256": digest(asdict(context)), "observation_sha256": observation.fingerprint(),
                 "model_calls": 0, "signal_types": []}

        def finish(action, reason):
            decision = Decision(action, reason, secrets.token_hex(24))
            payload = observation if action == "show" else Observation(text=FEEDBACK[action])
            with self._lock:
                # An abandoned consumer cannot retain an unbounded raw-data queue.
                if len(self._pending) >= 256:
                    self._pending.pop(next(iter(self._pending)))
                self._pending[decision.capability] = (digest(asdict(context)), decision, payload)
                event.update(action=action, reason=reason, elapsed_ms=(time.perf_counter() - started) * 1000)
                self.events.append(event)
                if len(self.events) > 4096:
                    del self.events[:2048]
            return decision

        fallback = "local" if access.local_compute else "hold"
        if access.view == "deny":
            return finish("hold", "source_denied")
        if access.view == "local":
            return finish(fallback, "source_local_only")
        if not observation.complete or len(observation.text) > self.max_chars:
            return finish(fallback, "incomplete_inspection")
        if len(canonical(asdict(context))) > self.max_chars:
            return finish("hold", "context_too_large")
        try:
            if observation.image is not None:
                validate_png(observation.image)
        except Exception:
            return finish("hold", "invalid_image")
        if access.view == "approved":
            if observation.fingerprint() != access.approved_sha256:
                return finish("hold", "approved_view_changed")
            return finish("show", "exact_trusted_view")
        if not observation.text and observation.image is None:
            return finish("show", "complete_empty_observation")
        event["signal_types"] = list(categories(observation.text))
        if event["signal_types"]:
            return finish(fallback, "sensitive_signal")
        if self.judge is None:
            return finish("hold", "inspector_unavailable")
        try:
            event["model_calls"] = 1
            assessment = self.judge(context, observation)
            if type(assessment) is not Assessment:
                raise ValueError("Expected a typed permission assessment")
            assessment.validate()
            event.update(permitted=assessment.permitted, request_sha256=assessment.request_sha256,
                         cache_hit=assessment.cached, model_calls=0 if assessment.cached else 1)
            if assessment.permitted >= self.threshold:
                return finish("show", "model_permitted")
            return finish(fallback, "view_not_permitted")
        except Exception as exc:
            event["error_type"] = type(exc).__name__
            return finish("hold", "inspection_failed")

    def messages(self, context: Context, decision: Decision, *, tool_call_id: str) -> list[dict]:
        """Consume a one-use capability; no caller-supplied observation bytes."""
        if type(tool_call_id) is not str or not tool_call_id or len(tool_call_id) > 256:
            raise ValueError("A bounded tool call ID is required")
        with self._lock:
            record = self._pending.get(decision.capability)
            if record is None or record[:2] != (digest(asdict(context)), decision):
                raise ValueError("Invalid or consumed release capability")
            _, _, view = self._pending.pop(decision.capability)
            messages = [{"role": "tool", "tool_call_id": tool_call_id, "content": view.text}]
            if view.image is not None:
                messages.append({"role": "user", "content": [
                    {"type": "text", "text": "Gateway-reviewed image."},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(view.image).decode()}}
                ]})
            scope = self._scope(context)
            for message in messages:
                key = (scope, digest(message))
                self._admitted[key] = None
                self._admitted.move_to_end(key)
            # Retain hashes only. Old receipts fail closed after eviction; the
            # harness must prune or re-review observations in a longer history.
            while len(self._admitted) > self.max_receipts:
                self._admitted.popitem(last=False)
            return messages

    @staticmethod
    def _scope(context):
        return digest({k: v for k, v in asdict(context).items() if k != "history"})

    def validate_request(self, context: Context, messages: list[dict]):
        """Call after final formatting; every tool/image message needs a receipt.

        Plain system/user/assistant text is trusted harness input. This does not
        inspect bypass tools, arbitrary API fields, files or network egress.
        """
        if type(messages) is not list:
            raise ValueError("Expected an ordinary message list")
        scope = self._scope(context)
        with self._lock:
            for message in messages:
                if type(message) is not dict or type(message.get("content")) not in (str, list, type(None)):
                    raise ValueError("Unsupported message representation")
                if message.get("role") not in {"system", "developer", "user", "assistant", "tool"}:
                    raise ValueError("Unsupported message role")
                if set(message) - {"role", "content", "tool_call_id", "name", "tool_calls"}:
                    raise ValueError("Unsupported message fields")
                if message.get("role") == "tool" or type(message.get("content")) is list:
                    if (scope, digest(message)) not in self._admitted:
                        raise ValueError("Unreviewed or altered observation")

