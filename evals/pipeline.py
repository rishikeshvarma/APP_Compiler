"""Adapters that run the system under test with every step traced."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from .tracing import Tracer


@dataclass
class PipelineOutput:
    schemas: Any
    design: str = ""
    repairs: int = 0


class Pipeline(Protocol):
    def __call__(self, prompt: str, tracer: Tracer) -> PipelineOutput: ...


def _usage(resp: Any) -> tuple[int | None, int | None]:
    um = getattr(resp, "usage_metadata", None)
    return (getattr(um, "prompt_token_count", None), getattr(um, "candidates_token_count", None)) if um else (None, None)


class CompilerPipeline:
    """Wraps agents.SaaSCompiler (duck-typed) and records one span per stage.

    Token usage is read from `compiler.last_usage` if the compiler exposes it; the
    current agents.py does not, so tokens are None until that is added (see README).
    """
    def __init__(self, compiler: Any, model_name: str | None = None) -> None:
        self.compiler = compiler
        self.model_name = model_name or getattr(compiler, "model_name", None)

    def __call__(self, prompt: str, tracer: Tracer) -> PipelineOutput:
        c = self.compiler
        with tracer.span("generate_design", model=self.model_name, input=prompt) as s:
            design = c.generate_design(prompt)
            s.set_output(design)
            s.set_usage(*getattr(c, "last_usage", (None, None)))
        with tracer.span("generate_schemas", model=self.model_name, input=design) as s:
            schemas = c.generate_schemas(design)
            s.set_output(schemas)
            s.set_usage(*getattr(c, "last_usage", (None, None)))
        with tracer.span("validate_and_repair", model=self.model_name, input=schemas) as s:
            final, repairs = c.validate_and_repair(schemas)
            s.set_output(final)
            s.attributes["repairs"] = repairs
        return PipelineOutput(schemas=final, design=design, repairs=repairs)


class ReplayPipeline:
    """Re-grades previously recorded outputs (evals/recorded/<case_id>.json) with no API calls.

    This is what runs in CI: it keeps the deterministic checks honest on every commit
    without spending quota. Cases with no recording raise FileNotFoundError -> SKIPPED.
    """
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def __call__(self, prompt: str, tracer: Tracer) -> PipelineOutput:  # prompt unused; case id is bound by the runner
        raise NotImplementedError("use .for_case(case_id)")

    def for_case(self, case_id: str) -> Callable[[str, Tracer], PipelineOutput]:
        def run(prompt: str, tracer: Tracer) -> PipelineOutput:
            path = self.directory / f"{case_id}.json"
            with tracer.span("replay", input=case_id) as s:
                data = json.loads(path.read_text())  # FileNotFoundError propagates to the runner
                s.set_output(data)
            return PipelineOutput(schemas=data["schemas"], design=data.get("design", ""), repairs=data.get("repairs", 0))
        return run
