"""Step-level tracing: every pipeline step, its latency, token usage and cost.

One JSONL file per case. A bad output should be traceable to the exact step that
broke, and an infrastructure failure must be distinguishable from a model failure.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from .models import ErrorKind, Span

# USD per 1M tokens: {model: (input, output)}. Fill in from your provider's pricing page;
# unknown models are recorded with cost_usd=None rather than a made-up number.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {}


def _h(obj: Any) -> str:
    raw = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def classify_error(exc: BaseException) -> tuple[ErrorKind, bool]:
    """Return (kind, retryable). Per-day quota is not retryable: waiting seconds cannot fix it."""
    msg = f"{type(exc).__name__}: {exc}"
    low = msg.lower()
    if "429" in msg or "quota" in low or "resourceexhausted" in low or "rate limit" in low:
        if re.search(r"PerDay|per_day|daily", msg, re.I):
            return ErrorKind.INFRA_QUOTA_DAILY, False
        return ErrorKind.INFRA_QUOTA, True
    if isinstance(exc, TimeoutError) or "timed out" in low or "deadline" in low:
        return ErrorKind.INFRA_TIMEOUT, True
    if isinstance(exc, ValueError):  # JSONDecodeError is a ValueError
        return ErrorKind.MODEL_OUTPUT_INVALID, False
    if "api_key" in low or "api key" in low or "not initialized" in low:
        return ErrorKind.CONFIG, False
    return ErrorKind.UNKNOWN, False


class SpanHandle:
    def __init__(self) -> None:
        self.model: Optional[str] = None
        self.prompt_tokens: Optional[int] = None
        self.completion_tokens: Optional[int] = None
        self.output: Any = None
        self.attributes: dict[str, Any] = {}

    def set_usage(self, prompt_tokens: int | None, completion_tokens: int | None) -> None:
        self.prompt_tokens, self.completion_tokens = prompt_tokens, completion_tokens

    def set_output(self, output: Any) -> None:
        self.output = output


class Tracer:
    def __init__(self, run_id: str, case_id: str, sink: Path | None = None) -> None:
        self.run_id, self.case_id = run_id, case_id
        self.sink = Path(sink) if sink else None
        self.spans: list[Span] = []
        if self.sink:
            self.sink.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def span(self, step: str, *, model: str | None = None, input: Any = None, **attributes: Any) -> Iterator[SpanHandle]:
        handle = SpanHandle()
        handle.model = model
        handle.attributes.update(attributes)
        t0 = time.perf_counter()
        started = time.time()
        err: BaseException | None = None
        try:
            yield handle
        except BaseException as e:  # noqa: BLE001 - we re-raise after recording
            err = e
            raise
        finally:
            kind, retryable = (classify_error(err) if err else (None, False))
            cost = None
            if handle.model in PRICES_PER_MTOK and handle.prompt_tokens is not None and handle.completion_tokens is not None:
                pin, pout = PRICES_PER_MTOK[handle.model]
                cost = (handle.prompt_tokens * pin + handle.completion_tokens * pout) / 1_000_000
            attrs = dict(handle.attributes)
            if err:
                attrs["retryable"] = retryable
            span = Span(
                run_id=self.run_id, case_id=self.case_id, span_id=uuid.uuid4().hex[:8], step=step,
                started_at=started, latency_ms=round((time.perf_counter() - t0) * 1000, 2),
                status="error" if err else "ok", model=handle.model,
                input_hash=_h(input) if input is not None else None,
                output_hash=_h(handle.output) if handle.output is not None else None,
                input_preview=(input if isinstance(input, str) else json.dumps(input, default=str))[:200] if input is not None else "",
                prompt_tokens=handle.prompt_tokens, completion_tokens=handle.completion_tokens, cost_usd=cost,
                error_kind=kind, error_message=str(err)[:500] if err else "", attributes=attrs,
            )
            self.spans.append(span)
            if self.sink:
                with self.sink.open("a", encoding="utf-8") as f:
                    f.write(span.model_dump_json() + "\n")

    def first_error(self) -> Span | None:
        return next((s for s in self.spans if s.status == "error"), None)

    def total_latency_ms(self) -> float:
        return round(sum(s.latency_ms for s in self.spans), 2)

    def total_tokens(self) -> int | None:
        vals = [(s.prompt_tokens or 0) + (s.completion_tokens or 0) for s in self.spans if s.prompt_tokens is not None]
        return sum(vals) if vals else None

    def total_cost(self) -> float | None:
        vals = [s.cost_usd for s in self.spans if s.cost_usd is not None]
        return round(sum(vals), 6) if vals else None


def read_trace(path: str | Path) -> list[Span]:
    return [Span.model_validate_json(ln) for ln in Path(path).read_text().splitlines() if ln.strip()]
