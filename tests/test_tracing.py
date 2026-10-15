import json

import pytest

from evals import tracing
from evals.models import ErrorKind
from evals.tracing import Tracer, classify_error, read_trace

# the exact 429 text committed in metrics.json by the first benchmark run
DAILY_429 = ("429 You exceeded your current quota ... Quota exceeded for metric: generativelanguage.googleapis.com/"
             "generate_content_free_tier_requests, limit: 20, model: gemini-3-flash ... quota_id: "
             "\"GenerateRequestsPerDayPerProjectPerModel-FreeTier\"")


def test_span_records_latency_tokens_and_hashes(tmp_path):
    t = Tracer("r1", "c1", tmp_path / "t.jsonl")
    with t.span("generate_design", model="m", input="build a crm") as s:
        s.set_usage(100, 50)
        s.set_output("# design")
    sp = t.spans[0]
    assert sp.status == "ok" and sp.latency_ms >= 0 and sp.prompt_tokens == 100 and sp.completion_tokens == 50
    assert sp.input_hash and sp.output_hash and sp.input_preview == "build a crm"
    assert t.total_tokens() == 150


def test_cost_is_computed_only_for_priced_models(monkeypatch, tmp_path):
    monkeypatch.setitem(tracing.PRICES_PER_MTOK, "priced", (1.0, 2.0))
    t = Tracer("r", "c")
    with t.span("a", model="priced") as s:
        s.set_usage(1_000_000, 500_000)
    with t.span("b", model="unpriced") as s:
        s.set_usage(10, 10)
    assert t.spans[0].cost_usd == pytest.approx(2.0)
    assert t.spans[1].cost_usd is None
    assert t.total_cost() == pytest.approx(2.0)


def test_failing_step_is_recorded_and_exception_propagates(tmp_path):
    t = Tracer("r", "c", tmp_path / "t.jsonl")
    with t.span("generate_design"):
        pass
    with pytest.raises(json.JSONDecodeError):
        with t.span("generate_schemas"):
            json.loads("{not json")
    bad = t.first_error()
    assert bad.step == "generate_schemas" and bad.error_kind == ErrorKind.MODEL_OUTPUT_INVALID
    assert [s.step for s in read_trace(tmp_path / "t.jsonl")] == ["generate_design", "generate_schemas"]


def test_daily_quota_is_infra_and_not_retryable():
    # regression R3/R4: this error made 10/10 benchmark cases "fail" and was retried for ~2.8h
    assert classify_error(Exception(DAILY_429)) == (ErrorKind.INFRA_QUOTA_DAILY, False)


def test_per_minute_quota_is_infra_and_retryable():
    assert classify_error(Exception("429 rate limit exceeded, retry in 30s")) == (ErrorKind.INFRA_QUOTA, True)


@pytest.mark.parametrize("exc,kind", [
    (TimeoutError("deadline exceeded"), ErrorKind.INFRA_TIMEOUT),
    (RuntimeError("Gemini model not initialized. Check your GOOGLE_API_KEY."), ErrorKind.CONFIG),
    (ValueError("Response is not a JSON object"), ErrorKind.MODEL_OUTPUT_INVALID),
    (KeyError("ui_layout"), ErrorKind.UNKNOWN),
])
def test_error_classification(exc, kind):
    assert classify_error(exc)[0] == kind
