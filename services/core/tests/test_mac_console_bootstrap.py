from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import app.runtime_ext.mac_console_bootstrap as bootstrap


def _result(code: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def test_bootstrap_skips_when_not_macos(monkeypatch):
    bootstrap.maybe_bootstrap_mac_console_environment.cache_clear()
    monkeypatch.setenv("MAC_CONSOLE_BOOTSTRAP_ENABLED", "1")
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Linux")

    calls: list[list[str]] = []

    def _fake_run(command: list[str], timeout_seconds: int):
        calls.append(command)
        return _result(0)

    monkeypatch.setattr(bootstrap, "_run_bootstrap_command", _fake_run)

    status = bootstrap.maybe_bootstrap_mac_console_environment()

    assert calls == []
    assert status["state"] == "skipped_non_macos"
    assert status["healthy"] is True


def test_bootstrap_runs_check_only_when_environment_ready(monkeypatch, tmp_path: Path):
    bootstrap.maybe_bootstrap_mac_console_environment.cache_clear()
    monkeypatch.setenv("MAC_CONSOLE_BOOTSTRAP_ENABLED", "1")
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Darwin")

    script = tmp_path / "bootstrap.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "_resolve_bootstrap_script_path", lambda: script)

    calls: list[list[str]] = []

    def _fake_run(command: list[str], timeout_seconds: int):
        calls.append(command)
        return _result(0)

    monkeypatch.setattr(bootstrap, "_run_bootstrap_command", _fake_run)

    status = bootstrap.maybe_bootstrap_mac_console_environment()

    assert calls == [[str(script), "--check"]]
    assert status["state"] == "check_passed"
    assert status["healthy"] is True
    assert status["attempted_autofix"] is False


def test_bootstrap_runs_autofix_when_check_fails(monkeypatch, tmp_path: Path):
    bootstrap.maybe_bootstrap_mac_console_environment.cache_clear()
    monkeypatch.setenv("MAC_CONSOLE_BOOTSTRAP_ENABLED", "1")
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Darwin")

    script = tmp_path / "bootstrap.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "_resolve_bootstrap_script_path", lambda: script)

    calls: list[list[str]] = []
    responses = iter([_result(1, "missing tools"), _result(0, "fixed")])

    def _fake_run(command: list[str], timeout_seconds: int):
        calls.append(command)
        return next(responses)

    monkeypatch.setattr(bootstrap, "_run_bootstrap_command", _fake_run)

    status = bootstrap.maybe_bootstrap_mac_console_environment()

    assert calls == [[str(script), "--check"], [str(script)]]
    assert status["state"] == "autofix_succeeded"
    assert status["healthy"] is True
    assert status["attempted_autofix"] is True


def test_bootstrap_is_process_singleton(monkeypatch, tmp_path: Path):
    bootstrap.maybe_bootstrap_mac_console_environment.cache_clear()
    monkeypatch.setenv("MAC_CONSOLE_BOOTSTRAP_ENABLED", "1")
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Darwin")

    script = tmp_path / "bootstrap.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "_resolve_bootstrap_script_path", lambda: script)

    calls: list[list[str]] = []

    def _fake_run(command: list[str], timeout_seconds: int):
        calls.append(command)
        return _result(0)

    monkeypatch.setattr(bootstrap, "_run_bootstrap_command", _fake_run)

    first = bootstrap.maybe_bootstrap_mac_console_environment()
    second = bootstrap.maybe_bootstrap_mac_console_environment()

    assert calls == [[str(script), "--check"]]
    assert first == second
