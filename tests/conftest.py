import json
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures" / "healthcare"


@pytest.fixture
def healthcare():
    return {
        "ui_layout": json.loads((FIX / "ui_layout.json").read_text()),
        "api_endpoints": json.loads((FIX / "api_endpoints.json").read_text()),
        "db_schema": (FIX / "db_schema.sql").read_text(),
    }


def make_schemas(ui_endpoints, api_paths, sql="CREATE TABLE leads (id UUID PRIMARY KEY);", shape="top"):
    """Minimal schema builder. shape='top' puts data_endpoint on the component, 'props' nests it."""
    comps = []
    for i, ep in enumerate(ui_endpoints):
        comp = {"id": f"c{i}", "type": "DataTable"}
        if shape == "top":
            comp["data_endpoint"] = ep
        else:
            comp["props"] = {"data_endpoint": ep}
        comps.append(comp)
    return {
        "ui_layout": {"pages": [{"id": "p", "components": comps}]},
        "api_endpoints": {"endpoints": [{"path": p, "method": "GET"} for p in api_paths]},
        "db_schema": sql,
    }
