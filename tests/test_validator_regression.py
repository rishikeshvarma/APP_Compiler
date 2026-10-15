"""Regression tests for bugs found in the system under test (agents.SaaSCompiler).

Each test reproduces a real failure found by running the harness against the committed
repo. They fail on the original agents.py and pass after the fix.
"""
import json
import types

import pytest

pytest.importorskip("google.generativeai")
import agents  # noqa: E402
from tests.conftest import make_schemas  # noqa: E402


class FakeModel:
    """Stands in for the Gemini model; returns a canned 'repaired' payload and counts calls."""
    def __init__(self, repaired):
        self.repaired, self.calls = repaired, 0

    def generate_content(self, prompt, generation_config=None):
        self.calls += 1
        return types.SimpleNamespace(text=json.dumps(self.repaired))


def compiler_with(repaired):
    c = agents.SaaSCompiler()
    c.model = FakeModel(repaired)
    return c


def test_validator_detects_missing_endpoint_when_data_endpoint_is_top_level():
    """R1: validator only looked in comp['props'], but the generator emits data_endpoint at the top level."""
    broken = make_schemas(["/api/v1/ghost"], ["/api/v1/leads"], sql="CREATE TABLE leads (id UUID);", shape="top")
    fixed = make_schemas(["/api/v1/leads"], ["/api/v1/leads"], sql="CREATE TABLE leads (id UUID);", shape="top")
    c = compiler_with(fixed)
    out, repairs = c.validate_and_repair.__wrapped__(c, broken)
    assert repairs == 1 and c.model.calls == 1 and out == fixed


def test_validator_rejects_prefix_only_match():
    """R2: startswith() let UI '/api/v1/leads' pass when the API only had '/api/v1/leads/hot'."""
    broken = make_schemas(["/api/v1/leads"], ["/api/v1/leads/hot"], sql="CREATE TABLE leads (id UUID);")
    c = compiler_with(broken)
    _, repairs = c.validate_and_repair.__wrapped__(c, broken)
    assert repairs == 1


def test_validator_does_not_repair_a_consistent_schema():
    ok = make_schemas(["/api/v1/leads/:id"], ["/api/v1/leads/{leadId}"], sql="CREATE TABLE leads (id UUID);")
    c = compiler_with(ok)
    _, repairs = c.validate_and_repair.__wrapped__(c, ok)
    assert repairs == 0 and c.model.calls == 0


def test_daily_quota_is_not_retried(monkeypatch):
    """R4: a per-day 429 was retried 10x with doubling sleeps (~2.8h) although it cannot recover."""
    monkeypatch.setattr(agents.time, "sleep", lambda s: pytest.fail("must not sleep on a per-day quota"))
    calls = []

    @agents.retry_with_backoff(retries=10, initial_delay=10)
    def call():
        calls.append(1)
        raise Exception('429 quota_id: "GenerateRequestsPerDayPerProjectPerModel-FreeTier"')

    with pytest.raises(Exception, match="PerDay"):
        call()
    assert len(calls) == 1


def test_per_minute_rate_limit_is_still_retried(monkeypatch):
    sleeps = []
    monkeypatch.setattr(agents.time, "sleep", lambda s: sleeps.append(s))
    attempts = []

    @agents.retry_with_backoff(retries=3, initial_delay=1)
    def call():
        attempts.append(1)
        if len(attempts) < 3:
            raise Exception("429 rate limit, retry in 5s")
        return "ok"

    assert call() == "ok" and sleeps == [1, 2]


def test_model_calls_record_token_usage_for_tracing():
    usage = types.SimpleNamespace(prompt_token_count=120, candidates_token_count=45)

    class M:
        def generate_content(self, prompt, generation_config=None):
            return types.SimpleNamespace(text="# design", usage_metadata=usage)

    c = agents.SaaSCompiler()
    c.model = M()
    assert c.generate_design.__wrapped__(c, "a crm") == "# design"
    assert c.last_usage == (120, 45)
