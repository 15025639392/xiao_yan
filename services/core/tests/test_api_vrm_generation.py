from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def _fake_blender(path: Path) -> Path:
    script = path / "fake_blender.py"
    script.write_text(
        """
from pathlib import Path
import json
import time
import sys

args = sys.argv
output = Path(args[args.index('--output') + 1])
spec = Path(args[args.index('--spec') + 1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(b'glTF fake vrm')
print(json.dumps({'output': str(output), 'spec_exists': spec.exists()}))
""".strip(),
        encoding="utf-8",
    )
    return script


def _wait_until_job_visible(client: TestClient, job_id: str, timeout_seconds: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/vrm-generation/jobs/{job_id}")
        if response.status_code == 200:
            return response.json()
        time.sleep(0.05)
    raise AssertionError("VRM generation job did not become visible in time")


def _wait_for_job(client: TestClient, job_id: str, timeout_seconds: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/vrm-generation/jobs/{job_id}")
        if response.status_code == 404:
            time.sleep(0.05)
            continue
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("VRM generation job did not finish in time")


def test_vrm_generation_job_runs_fake_blender_and_persists_artifacts(tmp_path, monkeypatch):
    storage_path = tmp_path / "jobs.json"
    artifact_dir = tmp_path / "artifacts"
    input_model = tmp_path / "input.vrm"
    input_model.write_bytes(b"input vrm")
    fake_blender = _fake_blender(tmp_path)

    monkeypatch.setenv("VRM_GENERATION_STORAGE_PATH", str(storage_path))
    monkeypatch.setenv("VRM_GENERATION_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("VRM_BLENDER_PATH", str(fake_blender))

    client = TestClient(app)
    response = client.post(
        "/vrm-generation/jobs",
        json={
            "prompt": "小晏，浅棕短发，蓝眼睛，白色居家裙",
            "input_model_path": str(input_model),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["prompt"] == "小晏，浅棕短发，蓝眼睛，白色居家裙"

    completed = _wait_for_job(client, payload["job_id"])
    assert completed["status"] == "completed"
    assert completed["artifacts"]["output_vrm_path"].startswith(str(artifact_dir))
    assert Path(completed["artifacts"]["output_vrm_path"]).is_file()

    persisted = json.loads(storage_path.read_text(encoding="utf-8"))
    assert payload["job_id"] in persisted["jobs"]

    artifacts_response = client.get(f"/vrm-generation/jobs/{payload['job_id']}/artifacts")
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()["output_vrm_path"] == completed["artifacts"]["output_vrm_path"]


def test_vrm_generation_missing_blender_fails_without_breaking_api(tmp_path, monkeypatch):
    input_model = tmp_path / "input.vrm"
    input_model.write_bytes(b"input vrm")
    monkeypatch.setenv("VRM_GENERATION_STORAGE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("VRM_GENERATION_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("VRM_BLENDER_PATH", str(tmp_path / "missing_blender"))

    client = TestClient(app)
    response = client.post(
        "/vrm-generation/jobs",
        json={"prompt": "生成小晏 VRM", "input_model_path": str(input_model)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"

    failed = _wait_for_job(client, payload["job_id"])
    assert failed["status"] == "failed"
    assert failed["error_code"] == "blender_unavailable"
    assert "Blender" in failed["error_message"]

def _slow_fake_blender(path: Path) -> Path:
    script = path / "slow_fake_blender.py"
    script.write_text(
        """
from pathlib import Path
import sys
import time

time.sleep(1.2)
args = sys.argv
output = Path(args[args.index('--output') + 1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(b'glTF slow fake vrm')
""".strip(),
        encoding="utf-8",
    )
    return script


def test_vrm_generation_job_returns_before_slow_blender_finishes(tmp_path, monkeypatch):
    input_model = tmp_path / "input.vrm"
    input_model.write_bytes(b"input vrm")
    monkeypatch.setenv("VRM_GENERATION_STORAGE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("VRM_GENERATION_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("VRM_BLENDER_PATH", str(_slow_fake_blender(tmp_path)))

    client = TestClient(app)
    started_at = time.monotonic()
    response = client.post(
        "/vrm-generation/jobs",
        json={"prompt": "生成小晏 VRM", "input_model_path": str(input_model)},
    )
    elapsed = time.monotonic() - started_at

    assert response.status_code == 200
    assert elapsed < 0.5
    payload = response.json()
    assert payload["status"] in {"queued", "running_blender"}

    completed = _wait_for_job(client, payload["job_id"])
    assert completed["status"] == "completed"
    assert Path(completed["artifacts"]["output_vrm_path"]).is_file()


def test_vrm_generation_running_job_can_be_cancelled(tmp_path, monkeypatch):
    input_model = tmp_path / "input.vrm"
    input_model.write_bytes(b"input vrm")
    monkeypatch.setenv("VRM_GENERATION_STORAGE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("VRM_GENERATION_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("VRM_BLENDER_PATH", str(_slow_fake_blender(tmp_path)))

    client = TestClient(app)
    response = client.post(
        "/vrm-generation/jobs",
        json={"prompt": "生成小晏 VRM", "input_model_path": str(input_model)},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    visible = _wait_until_job_visible(client, job_id)
    assert visible["status"] in {"queued", "validating_spec", "running_blender"}
    cancel_response = client.post(f"/vrm-generation/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    time.sleep(1.4)
    final = client.get(f"/vrm-generation/jobs/{job_id}")
    assert final.status_code == 200
    assert final.json()["status"] == "cancelled"


def test_vrm_generation_cancel_stops_external_process_output(tmp_path, monkeypatch):
    artifact_dir = tmp_path / "artifacts"
    input_model = tmp_path / "input.vrm"
    input_model.write_bytes(b"input vrm")
    monkeypatch.setenv("VRM_GENERATION_STORAGE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("VRM_GENERATION_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("VRM_BLENDER_PATH", str(_slow_fake_blender(tmp_path)))

    client = TestClient(app)
    response = client.post(
        "/vrm-generation/jobs",
        json={"prompt": "生成小晏 VRM", "input_model_path": str(input_model)},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    visible = _wait_until_job_visible(client, job_id)
    assert visible["status"] in {"queued", "validating_spec", "running_blender"}
    cancel_response = client.post(f"/vrm-generation/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200
    time.sleep(1.4)

    assert not (artifact_dir / job_id / "output.vrm").exists()
    assert client.get(f"/vrm-generation/jobs/{job_id}").json()["status"] == "cancelled"


def _fake_blender_template_exporter(path: Path) -> Path:
    script = path / "fake_template_blender.py"
    script.write_text(
        """
from pathlib import Path
import sys

args = sys.argv
assert '--input' not in args
assert '--spec' in args
assert '--output' in args
blend_args = [arg for arg in args if arg.endswith('.blend')]
assert blend_args, args
output = Path(args[args.index('--output') + 1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(b'glTF template fake vrm')
""".strip(),
        encoding="utf-8",
    )
    return script


def test_vrm_generation_uses_blend_template_when_configured(tmp_path, monkeypatch):
    template_path = tmp_path / "xiaoyan_base.blend"
    template_path.write_bytes(b"blend")
    monkeypatch.setenv("VRM_GENERATION_STORAGE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("VRM_GENERATION_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("VRM_BLENDER_PATH", str(_fake_blender_template_exporter(tmp_path)))
    monkeypatch.setenv("VRM_GENERATION_TEMPLATE_PATH", str(template_path))

    client = TestClient(app)
    response = client.post("/vrm-generation/jobs", json={"prompt": "小晏，白色居家裙"})

    assert response.status_code == 200
    completed = _wait_for_job(client, response.json()["job_id"])
    assert completed["status"] == "completed"
    assert Path(completed["artifacts"]["output_vrm_path"]).read_bytes() == b"glTF template fake vrm"


def test_vrm_generation_jobs_endpoint_lists_recent_jobs(tmp_path, monkeypatch):
    input_model = tmp_path / "input.vrm"
    input_model.write_bytes(b"input vrm")
    monkeypatch.setenv("VRM_GENERATION_STORAGE_PATH", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("VRM_GENERATION_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("VRM_BLENDER_PATH", str(_fake_blender(tmp_path)))

    client = TestClient(app)
    first = client.post("/vrm-generation/jobs", json={"prompt": "first", "input_model_path": str(input_model)}).json()
    second = client.post("/vrm-generation/jobs", json={"prompt": "second", "input_model_path": str(input_model)}).json()
    _wait_for_job(client, first["job_id"])
    _wait_for_job(client, second["job_id"])

    response = client.get("/vrm-generation/jobs?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["job_id"] == second["job_id"]
    assert payload["items"][0]["prompt"] == "second"
