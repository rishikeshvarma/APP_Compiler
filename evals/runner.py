"""Run a dataset through the pipeline, grade it, write traces + a report, gate on regressions.

    python -m evals.runner --replay evals/recorded --no-judge --baseline evals/baseline.json
    python -m evals.runner --live --baseline evals/baseline.json            # needs GOOGLE_API_KEY
    python -m evals.runner --live --record evals/recorded --update-baseline
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

from .checks import hard_failures, run_all_checks
from .dataset import DatasetSchemaError, load_dataset
from .judge import PASS_THRESHOLD, JudgeParseError, judge_case, mean_score
from .models import DATASET_SCHEMA_VERSION, Case, CaseResult, CaseStatus, ErrorKind, RunReport
from .pipeline import CompilerPipeline, Pipeline, ReplayPipeline
from .tracing import Tracer

INFRA_KINDS = {ErrorKind.INFRA_QUOTA, ErrorKind.INFRA_QUOTA_DAILY, ErrorKind.INFRA_TIMEOUT, ErrorKind.CONFIG}


def run_case(case: Case, pipeline: Pipeline | ReplayPipeline, judge: Callable[[str], str] | None,
             run_id: str, out_dir: Path, record_dir: Path | None = None) -> CaseResult:
    trace_file = out_dir / "traces" / f"{case.id}.jsonl"
    tracer = Tracer(run_id, case.id, trace_file)
    runner = pipeline.for_case(case.id) if isinstance(pipeline, ReplayPipeline) else pipeline
    try:
        output = runner(case.prompt, tracer)
    except FileNotFoundError:
        return CaseResult(case_id=case.id, status=CaseStatus.SKIPPED, error_message="no recorded output for this case", trace_file=str(trace_file))
    except Exception as e:  # noqa: BLE001 - classification happens via the failing span
        span = tracer.first_error()
        kind = span.error_kind if span and span.error_kind else ErrorKind.UNKNOWN
        status = CaseStatus.INFRA_ERROR if kind in INFRA_KINDS else CaseStatus.PIPELINE_ERROR
        return CaseResult(case_id=case.id, status=status, error_kind=kind, error_message=f"{span.step if span else '?'}: {e}"[:500],
                          latency_ms=tracer.total_latency_ms(), trace_file=str(trace_file))

    if record_dir:
        record_dir.mkdir(parents=True, exist_ok=True)
        (record_dir / f"{case.id}.json").write_text(json.dumps({"prompt": case.prompt, "design": output.design, "schemas": output.schemas, "repairs": output.repairs}, indent=2))

    checks = run_all_checks(output.schemas, case.expectations)
    result = CaseResult(case_id=case.id, status=CaseStatus.PASS, checks=checks, latency_ms=tracer.total_latency_ms(),
                        repairs=output.repairs, total_tokens=tracer.total_tokens(), cost_usd=tracer.total_cost(), trace_file=str(trace_file))
    if hard_failures(checks):
        result.status = CaseStatus.FAIL  # the judge never gets to rescue a deterministic failure
        return result
    if judge is not None:
        try:
            dims = judge_case(judge, case, output.schemas)
        except JudgeParseError as e:
            result.status, result.error_message = CaseStatus.JUDGE_ERROR, str(e)[:500]
            return result
        result.judge, result.judge_mean = dims, mean_score(dims)
        if result.judge_mean < PASS_THRESHOLD:
            result.status = CaseStatus.FAIL
    return result


def _pct(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    vals = sorted(vals)
    return round(vals[min(len(vals) - 1, int(round(q * (len(vals) - 1))))], 2)


def summarize(run_id: str, results: list[CaseResult]) -> RunReport:
    graded_pool = [r for r in results if r.status != CaseStatus.SKIPPED]
    completed = [r for r in graded_pool if r.status in (CaseStatus.PASS, CaseStatus.FAIL, CaseStatus.PIPELINE_ERROR)]
    n = len(graded_pool)
    lat = [r.latency_ms for r in completed if r.latency_ms is not None]
    costs = [r.cost_usd for r in results if r.cost_usd is not None]
    return RunReport(
        run_id=run_id, dataset_version=DATASET_SCHEMA_VERSION, n_cases=len(results), n_completed=len(completed),
        completion_rate=round(len(completed) / n, 3) if n else 0.0,
        pass_rate=round(sum(r.status == CaseStatus.PASS for r in completed) / len(completed), 3) if completed else 0.0,
        infra_error_rate=round(sum(r.status == CaseStatus.INFRA_ERROR for r in graded_pool) / n, 3) if n else 0.0,
        p50_latency_ms=_pct(lat, 0.5), p95_latency_ms=_pct(lat, 0.95),
        mean_repairs=round(statistics.mean(r.repairs for r in completed), 3) if completed else 0.0,
        total_cost_usd=round(sum(costs), 6) if costs else None, results=results,
    )


def run_eval(cases: list[Case], pipeline, judge=None, out_dir: str | Path = "evals/runs", run_id: str | None = None,
             record_dir: str | Path | None = None) -> RunReport:
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out = Path(out_dir) / run_id
    results = [run_case(c, pipeline, judge, run_id, out, Path(record_dir) if record_dir else None) for c in cases]
    report = summarize(run_id, results)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(report.model_dump_json(indent=2))
    return report


# ---- regression gate -------------------------------------------------------
def to_baseline(report: RunReport) -> dict:
    return {"dataset_version": report.dataset_version, "pass_rate": report.pass_rate,
            "cases": {r.case_id: r.status.value for r in report.results if r.status in (CaseStatus.PASS, CaseStatus.FAIL)}}


def compare_to_baseline(report: RunReport, baseline: dict, tolerance: float = 0.05) -> list[str]:
    """Regressions only. INFRA_ERROR/SKIPPED/JUDGE_ERROR are inconclusive, never a regression."""
    problems: list[str] = []
    if baseline.get("dataset_version") != report.dataset_version:
        return [f"dataset version changed ({baseline.get('dataset_version')} -> {report.dataset_version}); re-baseline deliberately"]
    now = {r.case_id: r for r in report.results}
    for cid, was in baseline.get("cases", {}).items():
        r = now.get(cid)
        if was == "pass" and r and r.status in (CaseStatus.FAIL, CaseStatus.PIPELINE_ERROR):
            failing = [c.name for c in r.checks if not c.passed and c.severity.value == "error"]
            problems.append(f"{cid}: pass -> {r.status.value} {failing or r.error_message[:120]}")
    if report.n_completed and report.pass_rate < baseline.get("pass_rate", 0) - tolerance:
        problems.append(f"pass_rate {report.pass_rate} < baseline {baseline['pass_rate']} - {tolerance}")
    return problems


def _print(report: RunReport) -> None:
    print(f"run {report.run_id}: {report.n_completed}/{report.n_cases} completed | pass_rate={report.pass_rate} "
          f"| infra_error_rate={report.infra_error_rate} | p95={report.p95_latency_ms}ms | repairs/case={report.mean_repairs}")
    for r in report.results:
        bad = [c.name for c in r.checks if not c.passed and c.severity.value == "error"]
        warn = [c.name for c in r.checks if not c.passed and c.severity.value == "warn"]
        extra = f" FAILED:{bad}" if bad else ""
        extra += f" warn:{warn}" if warn else ""
        extra += f" judge={r.judge_mean}" if r.judge_mean is not None else ""
        extra += f" [{r.error_kind.value}]" if r.error_kind else ""
        print(f"  {r.status.value:15} {r.case_id}{extra}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="evals.runner")
    ap.add_argument("--dataset", default="evals/datasets/cases.v1.jsonl")
    ap.add_argument("--out", default="evals/runs")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="call the real compiler (needs GOOGLE_API_KEY)")
    mode.add_argument("--replay", metavar="DIR", help="re-grade recorded outputs; no API calls")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--record", metavar="DIR", help="save live outputs here for later replay")
    ap.add_argument("--baseline", default="evals/baseline.json")
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args(argv)
    try:
        cases = load_dataset(args.dataset)
    except DatasetSchemaError as e:
        print(f"dataset error: {e}", file=sys.stderr)
        return 2

    judge = None
    if args.live:
        from agents import SaaSCompiler  # imported lazily: replay/CI needs no SDK or key
        from .judge import gemini_judge
        compiler = SaaSCompiler()
        pipeline: Pipeline | ReplayPipeline = CompilerPipeline(compiler)
        if not args.no_judge and compiler.model:
            judge = gemini_judge(compiler.model)
    else:
        pipeline = ReplayPipeline(args.replay)

    report = run_eval(cases, pipeline, judge, args.out, record_dir=args.record)
    _print(report)
    base_path = Path(args.baseline)
    if args.update_baseline:
        base_path.write_text(json.dumps(to_baseline(report), indent=2) + "\n")
        print(f"baseline written to {base_path}")
        return 0
    if base_path.exists():
        problems = compare_to_baseline(report, json.loads(base_path.read_text()))
        for p in problems:
            print(f"REGRESSION: {p}")
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
