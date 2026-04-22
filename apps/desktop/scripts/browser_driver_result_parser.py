from __future__ import annotations

import json
from typing import Any


def parse_evaluate_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"evaluate returned non-JSON str: {raw[:200]}") from exc
        if isinstance(parsed, dict):
            return parsed
        raise ValueError(f"evaluate returned JSON {type(parsed).__name__}, expected object")

    raise ValueError(f"evaluate returned {type(raw).__name__}: {str(raw)[:200]}")
