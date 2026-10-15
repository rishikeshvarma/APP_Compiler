import json

import pytest

from evals.judge import PASS_THRESHOLD, JudgeParseError, calibrate, judge_case, mean_score, parse_judge_output
from evals.models import Case

DIM = {"score": 4, "reason": "covers entities", "evidence": "table messages"}


def good(**over):
    d = {"requirement_coverage": DIM, "assumption_handling": DIM, "domain_safety": DIM}
    d.update(over)
    return json.dumps(d)


def test_parses_valid_output_and_code_fences():
    dims = parse_judge_output("```json\n" + good() + "\n```")
    assert mean_score(dims) == 4.0


@pytest.mark.parametrize("raw", [
    "not json",
    json.dumps([1, 2]),
    json.dumps({"requirement_coverage": DIM}),                                           # missing dimensions
    good(requirement_coverage={"score": 9, "reason": "x"}),                              # out of range
    good(requirement_coverage={"score": 3, "reason": "  "}),                             # no reason
])
def test_malformed_judge_output_is_an_error_not_a_score(raw):
    with pytest.raises(JudgeParseError):
        parse_judge_output(raw)


def test_judge_retries_once_then_gives_up():
    calls = []

    def flaky(prompt):
        calls.append(1)
        return "garbage"
    with pytest.raises(JudgeParseError, match="2 attempts"):
        judge_case(flaky, Case(id="a", prompt="p"), {})
    assert len(calls) == 2


def test_calibration_reports_direction_of_error():
    case = {"id": "x", "prompt": "p"}
    # stub judge: scores 5 when the artifact text contains "good", else 1
    def stub(prompt):
        s = 5 if '"good"' in prompt else 1
        return good(**{k: {"score": s, "reason": "r"} for k in ("requirement_coverage", "assumption_handling", "domain_safety")})
    rows = [
        {"case": case, "schemas": {"v": "good"}, "human_pass": True},
        {"case": case, "schemas": {"v": "good"}, "human_pass": False},   # judge too lenient
        {"case": case, "schemas": {"v": "bad"}, "human_pass": False},
        {"case": case, "schemas": {"v": "bad"}, "human_pass": False},
    ]
    out = calibrate(stub, rows)
    assert out["n"] == 4 and out["agreement"] == 0.75 and out["judge_too_lenient(fp)"] == 1 and out["judge_too_strict(fn)"] == 0
    assert PASS_THRESHOLD == 3.5
