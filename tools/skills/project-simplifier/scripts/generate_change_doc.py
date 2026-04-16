#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS_DIR = REPO_ROOT / "docs/plans"


def build_doc_content(date_text: str, title: str, changed_files: list[str]) -> str:
    changed_lines = "\n".join(f"- `{item}`" for item in changed_files) if changed_files else "- 待补充"
    return f"""# {title}

日期：{date_text}

## 1. 背景

- 当前项目为什么需要做这轮简化
- 当前复杂度主要来自哪里
- 如果不做，会带来什么问题

## 2. 当前最小目标

- 这轮简化之后，项目最少要稳定保留什么能力

## 3. 运行链路依据

- 复杂度扫描给出的主要收敛信号是什么
- 运行面分析说明默认主链路覆盖了哪些页面、路由、接口
- 如果存在异常项、决策卡片、门禁或执行模式建议，这轮如何采用、拒绝或延后

## 4. 范围

### 4.1 保留

- 待补充

### 4.2 延后

- 待补充

### 4.3 删除或冻结

- 待补充

## 5. 决策卡片与门禁

- 输出了哪些 `decision_cards`
- 默认动作建议是什么，最终是否采用
- `safety_gates` 哪些通过，哪些没通过
- 最终执行模式是 `decision_only`、`guided_backend_patch`、`guided_frontend_patch` 还是 `eligible_for_safe_cleanup`

## 6. Guided Patch Workflow

- 待补充

## 7. 具体改动

- 待补充

## 8. 同步文档与测试

### 8.1 文档

- 待补充

### 8.2 测试

- 待补充

### 8.3 关联检查

- 待补充

## 9. 影响文件

{changed_lines}

## 10. 验证方式

- 待补充

## 11. 风险与回退

- 当前已知风险待补充
- 如需回退，最小回退路径待补充

## 12. 下一步

- 下一轮还能继续做的减法
- 当前明确不做的内容
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a simplification change document draft.")
    parser.add_argument("--slug", required=True, help="Short topic slug, for example desktop-mainline")
    parser.add_argument("--title", default="", help="Document title. Defaults to '<slug> simplification'.")
    parser.add_argument(
        "--changed-file",
        action="append",
        dest="changed_files",
        default=[],
        help="Changed file path to prefill into the document. Can be repeated.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    date_text = datetime.now().strftime("%Y-%m-%d")
    slug = args.slug.strip()
    title = args.title.strip() or f"{slug} simplification"
    target = DOCS_DIR / f"{date_text}-{slug}-simplification.md"

    if target.exists():
        raise SystemExit(f"Document already exists: {target}")

    content = build_doc_content(date_text=date_text, title=title, changed_files=args.changed_files)
    target.write_text(content, encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
