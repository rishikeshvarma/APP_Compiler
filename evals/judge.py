"""LLM-as-judge, used ONLY for what deterministic checks cannot decide.

Design rules (so the scoring can be defended):
  * The judge can never rescue a case that failed a deterministic check.
  * Every score needs a reason and an evidence quote; unparseable output is a
    JUDGE_ERROR, never silently scored 0 or 5.
  * Judge quality is measured, not assumed: `calibrate()` compares the judge's
    pass/fail against human labels you provide (evals/datasets/calibration.template.jsonl).
"""
from __future__ import annotations

import json
import re
from typing import Callable, Protocol

from pydantic import ValidationError

from .models import Case, JudgeDimension

RUBRIC: dict[str, str] = {
    "requirement_coverage": "Does the compiled app cover every distinct capability the prompt asks for (entities, roles, features)? 5 = all covered, 1 = most missing.",
    "assumption_handling": "For vague or conflicting prompts: does the output make its assumptions explicit or resolve the conflict sensibly rather than silently inventing or ignoring requirements? 5 = explicit and sensible.",
    "domain_safety": "For regulated domains (health, finance): does the schema include the controls the prompt implies (audit trail, encryption of sensitive fields, access roles)? 5 = all implied controls present; N/A cases should score 5.",
}
PASS_THRESHOLD = 3.5

JUDGE_PROMPT = """You are grading a generated SaaS architecture against a user request.
Be strict. Cite the specific table, endpoint or component that supports each score.

USER REQUEST:
{prompt}

GENERATED ARTIFACTS (ui_layout, api_endpoints, db_schema):
{artifacts}

Score each dimension from 1 to 5 using this rubric:
{rubric}

Return ONLY JSON of the form:
{{"requirement_coverage": {{"score": <1-5>, "reason": "<one sentence>", "evidence": "<quote or identifier>"}}, "assumption_handling": {{...}}, "domain_safety": {{...}}}}
"""


class JudgeParseError(ValueError):
    pass


class Judge(Protocol):
    def __call__(self, case: Case, schemas: dict) -> str: ...


def build_prompt(case: Case, schemas: dict) -> str:
    rubric = "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    return JUDGE_PROMPT.format(prompt=case.prompt, artifacts=json.dumps(schemas)[:12000], rubric=rubric)


def parse_judge_output(text: str) -> dict[str, JudgeDimension]:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise JudgeParseError(f"judge did not return JSON: {e}") from e
    if not isinstance(raw, dict):
        raise JudgeParseError("judge JSON must be an object")
    missing = [k for k in RUBRIC if k not in raw]
    if missing:
        raise JudgeParseError(f"judge omitted dimensions: {missing}")
    out: dict[str, JudgeDimension] = {}
    for k in RUBRIC:
        try:
            dim = JudgeDimension.model_validate(raw[k])
        except ValidationError as e:
            raise JudgeParseError(f"dimension {k!r} invalid: {e.errors()[0]['msg']}") from e
        if not dim.reason.strip():
            raise JudgeParseError(f"dimension {k!r} has no reason")
        out[k] = dim
    return out


def mean_score(dims: dict[str, JudgeDimension]) -> float:
    return round(sum(d.score for d in dims.values()) / len(dims), 3)


def judge_case(judge: Callable[[str], str], case: Case, schemas: dict, retries: int = 1) -> dict[str, JudgeDimension]:
    """`judge` maps prompt text -> raw model text. Retries once on a parse failure."""
    prompt = build_prompt(case, schemas)
    last: Exception | None = None
    for _ in range(retries + 1):
        try:
            return parse_judge_output(judge(prompt))
        except JudgeParseError as e:
            last = e
    raise JudgeParseError(f"judge output unparseable after {retries + 1} attempts: {last}")


def calibrate(judge: Callable[[str], str], labeled: list[dict]) -> dict:
    """Compare judge pass/fail to human pass/fail.

    labeled rows: {"case": <Case dict>, "schemas": {...}, "human_pass": bool}.
    Returns agreement plus the confusion counts, so you can state how far the judge
    can be trusted (and which direction it errs in) instead of just asserting it.
    """
    tp = fp = tn = fn = 0
    for row in labeled:
        case = Case.model_validate(row["case"])
        verdict = mean_score(judge_case(judge, case, row["schemas"])) >= PASS_THRESHOLD
        human = bool(row["human_pass"])
        tp += verdict and human
        fp += verdict and not human
        tn += (not verdict) and (not human)
        fn += (not verdict) and human
    n = tp + fp + tn + fn
    po = (tp + tn) / n if n else 0.0
    pe = (((tp + fp) * (tp + fn)) + ((fn + tn) * (fp + tn))) / (n * n) if n else 0.0
    kappa = (po - pe) / (1 - pe) if n and pe != 1 else 0.0
    return {"n": n, "agreement": round(po, 3), "cohens_kappa": round(kappa, 3),
            "judge_too_lenient(fp)": fp, "judge_too_strict(fn)": fn, "tp": tp, "tn": tn}


def gemini_judge(model) -> Callable[[str], str]:
    """Adapter for a google.generativeai GenerativeModel (temperature 0, JSON mime type)."""
    def _call(prompt: str) -> str:
        resp = model.generate_content(prompt, generation_config={"temperature": 0, "response_mime_type": "application/json"})
        return resp.text
    return _call
