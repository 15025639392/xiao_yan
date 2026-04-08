from fastapi.testclient import TestClient

from app.main import app


def test_capabilities_contract_exposes_v0_shapes_and_descriptors():
    client = TestClient(app)

    response = client.get("/capabilities/contract")
    assert response.status_code == 200

    payload = response.json()
    assert payload["version"] == "v0"
    assert isinstance(payload.get("descriptors"), list)
    names = {item["name"] for item in payload["descriptors"]}
    assert {"fs.read", "fs.write", "fs.list", "fs.search", "shell.run"}.issubset(names)

    request_schema = payload.get("request_schema", {})
    result_schema = payload.get("result_schema", {})
    assert request_schema.get("title") == "CapabilityRequest"
    assert result_schema.get("title") == "CapabilityResult"


def test_capability_shell_policy_endpoint_exposes_allowed_lists():
    client = TestClient(app)

    response = client.get("/capabilities/shell-policy")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("version"), str)
    assert payload.get("revision", 0) >= 1
    assert "git" in payload.get("allowed_executables", [])
    assert "status" in payload.get("allowed_git_subcommands", [])


def test_capability_file_policy_endpoint_exposes_limits():
    client = TestClient(app)

    response = client.get("/capabilities/file-policy")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("version"), str)
    assert payload.get("revision", 0) >= 1
    assert payload.get("max_read_bytes", 0) > 0
    assert payload.get("max_write_bytes", 0) > 0
    assert payload.get("max_search_results", 0) > 0
    assert "*.py" in payload.get("allowed_search_file_patterns", [])
