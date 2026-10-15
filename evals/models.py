"""Typed records shared by the eval harness.

Everything that crosses a file boundary (dataset rows, traces, reports) is a
pydantic model so a schema change fails loudly instead of silently skewing a score.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

DATASET_SCHEMA_VERSION = 1


class Severity(str, Enum):
    ERROR = "error"  # hard gate: a failure here fails the case
    WARN = "warn"    # surfaced in the report, never fails the case


class Expectations(BaseModel):
    """Deterministic, per-case assertions about the compiled output."""
    required_tables: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    required_endpoint_patterns: list[str] = Field(default_factory=list)  # regexes
    requires_audit_log: bool = False
    forbidden_tables: list[str] = Field(default_factory=list)


class Case(BaseModel):
    id: str
    prompt: str
    tags: list[str] = Field(default_factory=list)  # e.g. ["vague"], ["conflicting"], ["compliance"]
    expectations: Expectations = Field(default_factory=Expectations)
    source: str = "synthetic"  # "synthetic" | "production-failure:<ref>"


class CheckResult(BaseModel):
    name: str
    passed: bool
    severity: Severity = Severity.ERROR
    detail: str = ""
    evidence: list[str] = Field(default_factory=list)


class ErrorKind(str, Enum):
    INFRA_QUOTA = "infra_quota"              # retryable rate limit (per-minute)
    INFRA_QUOTA_DAILY = "infra_quota_daily"  # per-day quota: retrying cannot help
    INFRA_TIMEOUT = "infra_timeout"
    CONFIG = "config"                        # missing API key etc.
    MODEL_OUTPUT_INVALID = "model_output_invalid"
    UNKNOWN = "unknown"


class Span(BaseModel):
    run_id: str
    case_id: str
    span_id: str
    step: str
    started_at: float
    latency_ms: float
    status: str  # "ok" | "error"
    model: Optional[str] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    input_preview: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    error_kind: Optional[ErrorKind] = None
    error_message: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class CaseStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"                  # compiled, but checks/judge said it is wrong
    INFRA_ERROR = "infra_error"    # never got a real answer (quota, timeout, config)
    PIPELINE_ERROR = "pipeline_error"  # the system under test crashed / emitted unparseable output
    JUDGE_ERROR = "judge_error"    # judge output could not be parsed after retry
    SKIPPED = "skipped"            # e.g. replay mode with no recording


class JudgeDimension(BaseModel):
    score: int = Field(ge=1, le=5)
    reason: str
    evidence: str = ""


class CaseResult(BaseModel):
    case_id: str
    status: CaseStatus
    checks: list[CheckResult] = Field(default_factory=list)
    judge: dict[str, JudgeDimension] = Field(default_factory=dict)
    judge_mean: Optional[float] = None
    latency_ms: Optional[float] = None
    repairs: int = 0
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    error_kind: Optional[ErrorKind] = None
    error_message: str = ""
    trace_file: Optional[str] = None


class RunReport(BaseModel):
    run_id: str
    dataset_version: int
    n_cases: int
    n_completed: int            # cases that produced an answer we could grade
    completion_rate: float
    pass_rate: float            # over completed cases only; infra errors are not model failures
    infra_error_rate: float
    p50_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    mean_repairs: float = 0.0
    total_cost_usd: Optional[float] = None
    results: list[CaseResult]
