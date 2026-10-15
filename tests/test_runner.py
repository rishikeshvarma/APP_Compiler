import json

from evals.judge import JudgeParseError  # noqa: F401
from evals.models import Case, CaseStatus, ErrorKind, Expectations
from evals.pipeline import CompilerPipeline, PipelineOutput
from evals.runner import compare_to_baseline, main, run_eval, to_baseline
from tests.conftest import make_schemas

DAILY_429 = 'ResourceExhausted 429 quota exceeded quota_id: "GenerateRequestsPerDayPerProjectPerModel-FreeTier"'
GOOD = make_schemas(["/api/v1/leads"], ["/api/v1/leads"])
BAD = make_schemas(["/api/v1/ghost"], ["/api/v1/leads"])


def cases(*ids):
    return [Case(id=i, prompt=f"prompt {i}") for i in ids]


def const_pipeline(schemas, repairs=0):
    return lambda prompt, tracer: PipelineOutput(schemas=schemas, repairs=repairs)


def by_prompt(mapping):
    def run(prompt, tracer):
        with tracer.span("generate_schemas", input=prompt):
            v = mapping[prompt]
            if isinstance(v, Exception):
                raise v
        return PipelineOutput(schemas=v)
    return run


# --- regression R3: metrics.json reported 0.0% success because every call hit a daily quota -------------
def test_quota_errors_are_infra_not_model_failures(tmp_path):
    exc = Exception(DAILY_429)
    rep = run_eval(cases("a", "b", "c"), by_prompt({f"prompt {i}": exc for i in "abc"}), out_dir=tmp_path)
    assert {r.status for r in rep.results} == {CaseStatus.INFRA_ERROR}
    assert rep.infra_error_rate == 1.0 and rep.completion_rate == 0.0 and rep.n_completed == 0
    assert all(r.error_kind == ErrorKind.INFRA_QUOTA_DAILY for r in rep.results)


def test_infra_errors_do_not_dilute_pass_rate(tmp_path):
    rep = run_eval(cases("a", "b", "c", "d"), by_prompt({"prompt a": GOOD, "prompt b": GOOD, "prompt c": BAD, "prompt d": Exception(DAILY_429)}), out_dir=tmp_path)
    assert rep.n_completed == 3 and rep.pass_rate == 0.667 and rep.completion_rate == 0.75 and rep.infra_error_rate == 0.25


def test_failure_is_traced_to_the_exact_step(tmp_path):
    rep = run_eval(cases("a"), by_prompt({"prompt a": json.JSONDecodeError("Expecting value", "{", 1)}), out_dir=tmp_path)
    r = rep.results[0]
    assert r.status == CaseStatus.PIPELINE_ERROR and r.error_kind == ErrorKind.MODEL_OUTPUT_INVALID and r.error_message.startswith("generate_schemas")
    spans = [json.loads(ln) for ln in open(r.trace_file)]
    assert spans[-1]["step"] == "generate_schemas" and spans[-1]["status"] == "error"


def test_compiler_pipeline_traces_each_stage_in_order(tmp_path):
    class Fake:
        model_name = "fake"
        def generate_design(self, p): return "design"
        def generate_schemas(self, d): return GOOD
        def validate_and_repair(self, s): return s, 1
    rep = run_eval(cases("a"), CompilerPipeline(Fake()), out_dir=tmp_path)
    r = rep.results[0]
    assert r.status == CaseStatus.PASS and r.repairs == 1
    assert [json.loads(ln)["step"] for ln in open(r.trace_file)] == ["generate_design", "generate_schemas", "validate_and_repair"]


def test_hard_check_failure_fails_the_case_and_judge_is_never_called(tmp_path):
    called = []
    def lenient_judge(prompt):
        called.append(1)
        return json.dumps({k: {"score": 5, "reason": "great"} for k in ("requirement_coverage", "assumption_handling", "domain_safety")})
    rep = run_eval(cases("a"), const_pipeline(BAD), judge=lenient_judge, out_dir=tmp_path)
    assert rep.results[0].status == CaseStatus.FAIL and not called


def test_judge_scores_gate_the_case_and_unparseable_judge_is_its_own_status(tmp_path):
    def dims(s):
        return json.dumps({k: {"score": s, "reason": "r"} for k in ("requirement_coverage", "assumption_handling", "domain_safety")})
    assert run_eval(cases("a"), const_pipeline(GOOD), judge=lambda p: dims(2), out_dir=tmp_path).results[0].status == CaseStatus.FAIL
    assert run_eval(cases("a"), const_pipeline(GOOD), judge=lambda p: dims(5), out_dir=tmp_path).results[0].status == CaseStatus.PASS
    r = run_eval(cases("a"), const_pipeline(GOOD), judge=lambda p: "nope", out_dir=tmp_path).results[0]
    assert r.status == CaseStatus.JUDGE_ERROR


def test_expectations_are_enforced_per_case(tmp_path):
    c = [Case(id="a", prompt="p", expectations=Expectations(required_tables=["invoices"]))]
    assert run_eval(c, const_pipeline(GOOD), out_dir=tmp_path).results[0].status == CaseStatus.FAIL


# --- baseline gate -------------------------------------------------------------------------------------
def test_baseline_flags_pass_to_fail_but_not_infra_errors(tmp_path):
    base = to_baseline(run_eval(cases("a", "b"), const_pipeline(GOOD), out_dir=tmp_path))
    regressed = run_eval(cases("a", "b"), by_prompt({"prompt a": GOOD, "prompt b": BAD}), out_dir=tmp_path)
    problems = compare_to_baseline(regressed, base)
    assert any(p.startswith("b: pass -> fail") and "ui_endpoints_exist" in p for p in problems)
    flaky = run_eval(cases("a", "b"), by_prompt({"prompt a": GOOD, "prompt b": Exception(DAILY_429)}), out_dir=tmp_path)
    assert compare_to_baseline(flaky, base) == []  # inconclusive is not a regression


def test_dataset_version_change_requires_deliberate_rebaseline(tmp_path):
    rep = run_eval(cases("a"), const_pipeline(GOOD), out_dir=tmp_path)
    assert "dataset version changed" in compare_to_baseline(rep, {"dataset_version": 0, "cases": {}})[0]


def test_record_then_replay_round_trip(tmp_path):
    rec = tmp_path / "rec"
    run_eval(cases("a"), const_pipeline(GOOD), out_dir=tmp_path, record_dir=rec)
    from evals.pipeline import ReplayPipeline
    rep = run_eval(cases("a", "missing"), ReplayPipeline(rec), out_dir=tmp_path)
    assert [r.status for r in rep.results] == [CaseStatus.PASS, CaseStatus.SKIPPED]


def test_cli_replay_gate_exit_codes(tmp_path, capsys):
    base = tmp_path / "base.json"
    args = ["--replay", "evals/recorded", "--no-judge", "--out", str(tmp_path / "runs"), "--baseline", str(base)]
    assert main(args + ["--update-baseline"]) == 0
    assert main(args) == 0
    # simulate a regression by pointing replay at a corrupted recording
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    rec = json.loads(open("evals/recorded/healthcare-hipaa.json").read())
    rec["schemas"]["api_endpoints"]["endpoints"] = rec["schemas"]["api_endpoints"]["endpoints"][:1]
    (bad_dir / "healthcare-hipaa.json").write_text(json.dumps(rec))
    assert main(["--replay", str(bad_dir), "--no-judge", "--out", str(tmp_path / "runs"), "--baseline", str(base)]) == 1
    assert "REGRESSION" in capsys.readouterr().out
    assert main(["--dataset", str(tmp_path / "nope.jsonl"), "--replay", "x"]) == 2  # unreadable dataset is a harness error, not a regression
