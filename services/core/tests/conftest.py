from __future__ import annotations

import pytest

from app.main import app
from app.runtime_ext.bootstrap import shutdown_runtime


def _clear_app_state() -> None:
    state_dict = getattr(app.state, "_state", {})
    for key in list(state_dict.keys()):
        delattr(app.state, key)


@pytest.fixture(autouse=True)
def isolate_app_state_and_overrides():
    app.dependency_overrides.clear()
    _clear_app_state()
    yield
    app.dependency_overrides.clear()
    shutdown_runtime(app)
    _clear_app_state()
