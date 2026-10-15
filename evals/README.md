# AppCompiler evals

An eval + tracing harness for the 4-stage compiler (`intent → design → schemas → validate/repair`).
It answers three questions: *is this output wrong, which step broke, and will it stay fixed?*

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                                                    # 52 tests, no API key
python -m evals.runner --replay evals/recorded --no-judge              # re-grade recorded outputs, gate on baseline
GOOGLE_API_KEY=... python -m evals.runner --live --record evals/recorded   # real run; saves outputs for replay
python -m evals.runner --live --update-baseline                        # deliberately accept new baseline
```

## How it works
| Piece | File | Why |
|---|---|---|
| Deterministic checks | `checks.py` | UI→API, API→table, FK targets, duplicate tables, per-case expectations. Code decides everything code can decide. Independent of `agents.py` on purpose, so the grader does not share bugs with the system under test. |
| LLM-as-judge | `judge.py` | Only for what code can't decide (requirement coverage, assumption handling, domain safety). Needs reason + evidence per score. Unparseable output → `JUDGE_ERROR`, never a silent score. **The judge cannot rescue a deterministic failure.** |
| Tracing | `tracing.py` | One span per step: latency, tokens, cost, input/output hash, classified error. A bad output points at the step that produced it. |
| Versioned dataset | `dataset.py`, `datasets/cases.v1.jsonl` | Schema-versioned JSONL with a header line; a version mismatch or bad row fails loudly with the line number. |
| Runner + gate | `runner.py` | Statuses: `pass / fail / infra_error / pipeline_error / judge_error / skipped`. Infra errors (quota, timeout, missing key) are **not** counted as model failures. Exit code 1 on pass→fail regressions. |

## Failures this harness found in the repo (each is a regression test)
1. **Validator never checked UI→API when `data_endpoint` was top-level** — `agents.py` read `comp["props"]["data_endpoint"]`, but generated schemas put it on the component. The "self-healing" check was vacuous for that shape. (`test_validator_detects_missing_endpoint_when_data_endpoint_is_top_level`)
2. **Prefix matching** — UI `/api/v1/leads` "matched" an API that only had `/api/v1/leads/hot`. (`test_validator_rejects_prefix_only_match`)
3. **Quota errors scored as model failures** — the committed `metrics.json` shows 0/10 "success" caused entirely by a 429. (`test_quota_errors_are_infra_not_model_failures`)
4. **Daily quota retried for ~2.8 hours** — the backoff decorator retried a per-day 429 that cannot recover. (`test_daily_quota_is_not_retried`)

## Known limits (read before trusting a number)
- Only **one** recorded output (`healthcare-hipaa`, copied from `schemas/`; original run unknown). The other 12 cases are `skipped` until you run `--live --record`.
- The judge is **uncalibrated** until you label real outputs: copy `datasets/calibration.template.jsonl`, add ~15 rows, run `judge.calibrate()`, and report agreement and which direction it errs.
- API→table matching is name-based; namespace paths (`/doctor/queue`, `/ai/...`) are surfaced as warnings, not decided.
- `PRICES_PER_MTOK` in `tracing.py` is empty: cost is `None` until you add your model's prices.
- `validate_and_repair` still doesn't re-validate after repairing; it returns `1` whether or not the repair worked.
