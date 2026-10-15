from evals.checks import hard_failures, normalize_path, run_all_checks
from evals.models import Expectations, Severity
from tests.conftest import make_schemas


def by_name(results, name):
    return next(r for r in results if r.name == name)


def test_real_healthcare_output_has_no_hard_failures(healthcare):
    assert hard_failures(run_all_checks(healthcare)) == []


def test_real_healthcare_output_surfaces_known_soft_warnings(healthcare):
    results = run_all_checks(healthcare)
    # a UI component reads a POST-only endpoint, and doctor/ai namespaces cannot be mapped to tables by name
    assert not by_name(results, "ui_reads_use_get").passed
    assert not by_name(results, "api_namespaced_resources_unresolved").passed
    assert all(r.severity == Severity.WARN for r in results if not r.passed)


# --- regression: production failure R1 -------------------------------------------------
# agents.py read data_endpoint only from comp["props"], but the generator emits it at the top level
# (see schemas/ui_layout.json), so the UI->API check silently never fired.
def test_missing_endpoint_is_caught_when_data_endpoint_is_top_level():
    s = make_schemas(["/api/v1/ghost"], ["/api/v1/leads"], shape="top")
    r = by_name(run_all_checks(s), "ui_endpoints_exist")
    assert not r.passed and "ghost" in r.evidence[0]


def test_missing_endpoint_is_caught_when_data_endpoint_is_under_props():
    s = make_schemas(["/api/v1/ghost"], ["/api/v1/leads"], shape="props")
    assert not by_name(run_all_checks(s), "ui_endpoints_exist").passed


# --- regression: production failure R2 -------------------------------------------------
# the old check used startswith(): UI '/api/v1/leads' "matched" an API that only had '/api/v1/leads/hot'.
def test_prefix_of_a_real_endpoint_is_not_a_match():
    s = make_schemas(["/api/v1/leads"], ["/api/v1/leads/hot"])
    assert not by_name(run_all_checks(s), "ui_endpoints_exist").passed


def test_path_param_styles_are_equivalent():
    assert normalize_path("/api/v1/patients/{patientId}/vitals/") == normalize_path("/api/v1/patients/:id/vitals") == "/api/v1/patients/{}/vitals"
    s = make_schemas(["/api/v1/leads/:id"], ["/api/v1/leads/{leadId}"])
    assert by_name(run_all_checks(s), "ui_endpoints_exist").passed


def test_api_resource_without_any_table_is_a_hard_failure():
    s = make_schemas(["/api/v1/invoices"], ["/api/v1/invoices"], sql="CREATE TABLE leads (id UUID);")
    r = by_name(run_all_checks(s), "api_resources_have_tables")
    assert not r.passed and r.severity == Severity.ERROR


def test_suffix_table_names_resolve():
    s = make_schemas(["/api/v1/records"], ["/api/v1/records"], sql="CREATE TABLE medical_records (id UUID);")
    assert by_name(run_all_checks(s), "api_resources_have_tables").passed


def test_foreign_key_to_missing_table_is_flagged():
    sql = "CREATE TABLE a (id UUID, b_id UUID REFERENCES b(id));"
    r = by_name(run_all_checks(make_schemas([], ["/api/v1/a"], sql=sql)), "fk_targets_exist")
    assert not r.passed and "a REFERENCES b" in r.evidence


def test_duplicate_tables_flagged():
    sql = "CREATE TABLE a (id UUID);\nCREATE TABLE a (id UUID);"
    assert not by_name(run_all_checks(make_schemas([], ["/api/v1/a"], sql=sql)), "no_duplicate_tables").passed


def test_malformed_output_short_circuits_to_shape_failure():
    results = run_all_checks({"ui_layout": [], "api_endpoints": {}, "db_schema": ""})
    assert [r.name for r in results] == ["shape"] and not results[0].passed
    assert [r.name for r in run_all_checks("not a dict")] == ["shape"]


def test_expectations(healthcare):
    exp = Expectations(required_tables=["messages", "prescriptions"], required_roles=["Doctor"], requires_audit_log=True,
                       required_endpoint_patterns=["message", "billing"], forbidden_tables=["users"])
    results = {r.name: r for r in run_all_checks(healthcare, exp)}
    assert results["expect_required_tables"].evidence == ["prescriptions"]
    assert results["expect_required_endpoints"].evidence == ["billing"]
    assert results["expect_forbidden_tables"].evidence == ["users"]
    assert results["expect_required_roles"].passed and results["expect_audit_log_table"].passed
    assert results["expect_audit_log_immutable"].passed  # the real schema has an immutability rule


def test_audit_log_without_immutability_is_a_warning_not_a_failure():
    sql = "CREATE TABLE audit_logs (id UUID);"
    s = make_schemas([], ["/api/v1/audit-logs"], sql=sql)
    results = {r.name: r for r in run_all_checks(s, Expectations(requires_audit_log=True))}
    assert not results["expect_audit_log_immutable"].passed
    assert results["expect_audit_log_immutable"].severity == Severity.WARN
    assert hard_failures(list(results.values())) == []
