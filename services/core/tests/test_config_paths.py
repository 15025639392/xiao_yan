from pathlib import Path

import app.config as config


def test_get_mempalace_palace_path_defaults_to_service_root(monkeypatch):
    monkeypatch.setattr(config, "load_local_env", lambda: None)
    monkeypatch.delenv("MEMPALACE_PALACE_PATH", raising=False)

    expected = Path(config.__file__).resolve().parents[1] / ".mempalace" / "palace"
    assert config.get_mempalace_palace_path() == str(expected)


def test_get_mempalace_palace_path_prefers_env_override(monkeypatch):
    monkeypatch.setattr(config, "load_local_env", lambda: None)
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", ".data/custom-palace")

    service_root = Path(config.__file__).resolve().parents[1]
    assert config.get_mempalace_palace_path() == str(service_root / ".data" / "custom-palace")


def test_get_mempalace_palace_path_resolves_relative_override_from_service_root(monkeypatch):
    monkeypatch.setattr(config, "load_local_env", lambda: None)
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", ".mempalace/palace")

    service_root = Path(config.__file__).resolve().parents[1]
    assert config.get_mempalace_palace_path() == str(service_root / ".mempalace" / "palace")


def test_get_mempalace_palace_path_rejects_home_absolute_override(monkeypatch):
    monkeypatch.setattr(config, "load_local_env", lambda: None)
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", "~/.mempalace/palace")

    service_root = Path(config.__file__).resolve().parents[1]
    assert config.get_mempalace_palace_path() == str(service_root / ".mempalace" / "palace")


def test_get_mempalace_palace_path_rejects_external_absolute_override(monkeypatch):
    monkeypatch.setattr(config, "load_local_env", lambda: None)
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", "/tmp/external-palace")

    service_root = Path(config.__file__).resolve().parents[1]
    assert config.get_mempalace_palace_path() == str(service_root / ".mempalace" / "palace")
