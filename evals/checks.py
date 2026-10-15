"""Deterministic cross-layer consistency checks.

These replace "ask an LLM whether the schemas are consistent" for everything that
can be decided by code: does every UI data endpoint exist in the API, does every
API resource have a backing table, do foreign keys point at real tables.
An LLM judge is only used for what code cannot decide (see judge.py).
"""
from __future__ import annotations

import re
from typing import Any

from .models import CheckResult, Expectations, Severity

_VERSION_SEG = re.compile(r"^v\d+$")
# Path segments that name a role/namespace rather than a table.
NAMESPACES = {"api", "admin", "ai", "auth", "me", "internal", "public", "health", "doctor", "staff"}
_PARAM = re.compile(r"\{[^}]*\}|:[A-Za-z_]\w*|<[^>]*>")


def normalize_path(path: str) -> str:
    """'/api/v1/patients/{patientId}/vitals/' -> '/api/v1/patients/{}/vitals'.

    Treats {x}, :x and <x> path params as equivalent and ignores trailing slashes
    and query strings. Comparison is exact on the normalized form (never prefix).
    """
    path = path.split("?")[0].strip()
    path = _PARAM.sub("{}", path)
    return path.rstrip("/") or "/"


def extract_ui_endpoints(ui: dict) -> list[tuple[str, str]]:
    """(component_id, data_endpoint) for every component, whether the generator put
    `data_endpoint` at the top level or under `props` (both shapes occur in practice)."""
    out: list[tuple[str, str]] = []
    for page in ui.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        for comp in page.get("components", []) or []:
            if not isinstance(comp, dict):
                continue
            ep = comp.get("data_endpoint")
            if ep is None and isinstance(comp.get("props"), dict):
                ep = comp["props"].get("data_endpoint")
            if isinstance(ep, str) and ep:
                out.append((str(comp.get("id") or comp.get("component") or "?"), ep))
    return out


def extract_tables(sql: str) -> list[str]:
    return [t.lower() for t in re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?\"?(\w+)\"?", sql, re.I)]


def extract_fk_targets(sql: str) -> list[tuple[str, str]]:
    """(table, referenced_table) pairs. Crude but sufficient: tracks the current CREATE TABLE."""
    pairs, current = [], None
    for line in sql.splitlines():
        m = re.search(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?\"?(\w+)\"?", line, re.I)
        if m:
            current = m.group(1).lower()
        for ref in re.findall(r"REFERENCES\s+\"?(\w+)\"?", line, re.I):
            pairs.append((current or "?", ref.lower()))
    return pairs


def _resource_candidates(path: str) -> list[str]:
    segs = [s for s in path.split("/") if s]
    return [s.lower() for s in segs if not _VERSION_SEG.match(s) and s.lower() != "api" and not s.startswith("{")]


def _matches_table(resource: str, tables: list[str]) -> bool:
    """Name-based match between an API resource and a table.

    Accepts: exact / singular / plural equality, a table that starts with the resource
    (patients -> patient_profiles) or ends with it (records -> medical_records).
    """
    singular = resource[:-1] if resource.endswith("s") else resource
    toks = {resource.replace("-", "_"), singular.replace("-", "_")}
    for t in tables:
        t_sing = t[:-1] if t.endswith("s") else t
        if t in toks or t_sing in toks:
            return True
        if any(t.startswith(tok + "_") or t.endswith("_" + tok) or t_sing.endswith("_" + tok) for tok in toks):
            return True
    return False


def check_shape(schemas: Any) -> CheckResult:
    problems = []
    if not isinstance(schemas, dict):
        return CheckResult(name="shape", passed=False, detail=f"schemas is {type(schemas).__name__}, not dict")
    ui, api, db = schemas.get("ui_layout"), schemas.get("api_endpoints"), schemas.get("db_schema")
    if not (isinstance(ui, dict) and isinstance(ui.get("pages"), list) and ui["pages"]):
        problems.append("ui_layout must be an object with a non-empty 'pages' list")
    if not (isinstance(api, dict) and isinstance(api.get("endpoints"), list) and api["endpoints"]):
        problems.append("api_endpoints must be an object with a non-empty 'endpoints' list")
    elif any(not isinstance(e, dict) or not e.get("path") or not e.get("method") for e in api["endpoints"]):
        problems.append("every endpoint needs 'path' and 'method'")
    if not (isinstance(db, str) and extract_tables(db)):
        problems.append("db_schema must be a string containing at least one CREATE TABLE")
    return CheckResult(name="shape", passed=not problems, detail="; ".join(problems), evidence=problems)


def check_ui_endpoints_exist(schemas: dict) -> CheckResult:
    api_paths = {normalize_path(e["path"]): e for e in schemas["api_endpoints"]["endpoints"]}
    missing = []
    for comp_id, ep in extract_ui_endpoints(schemas["ui_layout"]):
        if normalize_path(ep) not in api_paths:
            missing.append(f"component '{comp_id}' -> {ep}")
    return CheckResult(
        name="ui_endpoints_exist", passed=not missing,
        detail=f"{len(missing)} UI data_endpoint(s) have no matching API path (exact match, params normalized)" if missing else "",
        evidence=missing,
    )


def check_ui_endpoints_use_get(schemas: dict) -> CheckResult:
    by_path: dict[str, set[str]] = {}
    for e in schemas["api_endpoints"]["endpoints"]:
        by_path.setdefault(normalize_path(e["path"]), set()).add(str(e["method"]).upper())
    bad = [f"component '{cid}' reads {ep} but it only exposes {sorted(by_path[normalize_path(ep)])}"
           for cid, ep in extract_ui_endpoints(schemas["ui_layout"])
           if normalize_path(ep) in by_path and "GET" not in by_path[normalize_path(ep)]]
    return CheckResult(name="ui_reads_use_get", passed=not bad, severity=Severity.WARN,
                       detail="; ".join(bad), evidence=bad)


def check_api_resources_have_tables(schemas: dict) -> list[CheckResult]:
    tables = extract_tables(schemas["db_schema"])
    hard, soft = [], []
    for e in schemas["api_endpoints"]["endpoints"]:
        cands = _resource_candidates(e["path"])
        if not cands or any(_matches_table(c, tables) for c in cands):
            continue
        (soft if cands[0] in NAMESPACES else hard).append(f"{e['method']} {e['path']} (resource {cands[0]!r}; tables: {tables})")
    return [
        CheckResult(name="api_resources_have_tables", passed=not hard, detail=f"{len(hard)} endpoint(s) with no plausible backing table" if hard else "", evidence=hard),
        CheckResult(name="api_namespaced_resources_unresolved", passed=not soft, severity=Severity.WARN,
                    detail="namespace-style paths cannot be mapped to a table by name; review manually or via judge" if soft else "", evidence=soft),
    ]


def check_fk_targets_exist(schemas: dict) -> CheckResult:
    tables = set(extract_tables(schemas["db_schema"]))
    bad = [f"{t} REFERENCES {r}" for t, r in extract_fk_targets(schemas["db_schema"]) if r not in tables]
    return CheckResult(name="fk_targets_exist", passed=not bad, detail="foreign key points at a table that is never created" if bad else "", evidence=bad)


def check_no_duplicate_tables(schemas: dict) -> CheckResult:
    tables = extract_tables(schemas["db_schema"])
    dups = sorted({t for t in tables if tables.count(t) > 1})
    return CheckResult(name="no_duplicate_tables", passed=not dups, detail=f"duplicate CREATE TABLE: {dups}" if dups else "", evidence=dups)


def check_roles_defined(schemas: dict) -> CheckResult:
    sql = schemas["db_schema"].lower()
    roles = {r for p in schemas["ui_layout"].get("pages", []) if isinstance(p, dict) for r in (p.get("role_access") or []) if isinstance(r, str)}
    missing = sorted(r for r in roles if r.lower() not in sql)
    return CheckResult(name="ui_roles_defined_in_db", passed=not missing, severity=Severity.WARN,
                       detail=f"roles used in UI but absent from DB schema: {missing}" if missing else "", evidence=missing)


def check_expectations(schemas: dict, exp: Expectations) -> list[CheckResult]:
    out: list[CheckResult] = []
    sql = schemas["db_schema"]
    tables = extract_tables(sql)
    paths = [e["path"] for e in schemas["api_endpoints"]["endpoints"]]
    if exp.required_tables:
        miss = [t for t in exp.required_tables if not any(t.lower() == x or t.lower().rstrip("s") in x for x in tables)]
        out.append(CheckResult(name="expect_required_tables", passed=not miss, detail=f"missing tables: {miss}" if miss else "", evidence=miss))
    if exp.required_roles:
        miss = [r for r in exp.required_roles if r.lower() not in sql.lower()]
        out.append(CheckResult(name="expect_required_roles", passed=not miss, detail=f"missing roles: {miss}" if miss else "", evidence=miss))
    if exp.required_endpoint_patterns:
        miss = [p for p in exp.required_endpoint_patterns if not any(re.search(p, x) for x in paths)]
        out.append(CheckResult(name="expect_required_endpoints", passed=not miss, detail=f"no endpoint matches: {miss}" if miss else "", evidence=miss))
    if exp.forbidden_tables:
        bad = [t for t in exp.forbidden_tables if t.lower() in tables]
        out.append(CheckResult(name="expect_forbidden_tables", passed=not bad, detail=f"forbidden tables present: {bad}" if bad else "", evidence=bad))
    if exp.requires_audit_log:
        has_table = any("audit" in t for t in tables)
        immutable = bool(re.search(r"(DO\s+INSTEAD\s+NOTHING|BEFORE\s+(UPDATE|DELETE)|REVOKE\s+(UPDATE|DELETE))", sql, re.I))
        out.append(CheckResult(name="expect_audit_log_table", passed=has_table, detail="" if has_table else "no audit table"))
        out.append(CheckResult(name="expect_audit_log_immutable", passed=immutable, severity=Severity.WARN,
                               detail="" if immutable else "audit table has no rule/trigger/REVOKE preventing UPDATE/DELETE"))
    return out


def run_all_checks(schemas: Any, expectations: Expectations | None = None) -> list[CheckResult]:
    shape = check_shape(schemas)
    if not shape.passed:  # nothing else is safe to run on a malformed structure
        return [shape]
    results = [
        shape,
        check_ui_endpoints_exist(schemas),
        check_ui_endpoints_use_get(schemas),
        *check_api_resources_have_tables(schemas),
        check_fk_targets_exist(schemas),
        check_no_duplicate_tables(schemas),
        check_roles_defined(schemas),
    ]
    if expectations:
        results += check_expectations(schemas, expectations)
    return results


def hard_failures(results: list[CheckResult]) -> list[CheckResult]:
    return [r for r in results if not r.passed and r.severity == Severity.ERROR]
