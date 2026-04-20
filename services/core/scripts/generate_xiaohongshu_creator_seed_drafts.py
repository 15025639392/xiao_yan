from __future__ import annotations

import json
import sys
from pathlib import Path

from app.api.platform_route_models import XiaohongshuCreatorHomePreviewRequest
from app.usecases.xiaohongshu_creator_home_preview import build_xiaohongshu_creator_home_preview_items
from app.usecases.xiaohongshu_seed_drafts import build_seed_drafts_from_creator_opportunities


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m scripts.generate_xiaohongshu_creator_seed_drafts <snapshot.json>")
        return 1
    snapshot_path = Path(sys.argv[1])
    if not snapshot_path.is_file():
        print(f"snapshot file not found: {snapshot_path}")
        return 1

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    request = XiaohongshuCreatorHomePreviewRequest.model_validate(payload)
    opportunities = build_xiaohongshu_creator_home_preview_items(request)
    drafts = build_seed_drafts_from_creator_opportunities(opportunities)
    print(json.dumps([draft.model_dump(mode="json") for draft in drafts], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
