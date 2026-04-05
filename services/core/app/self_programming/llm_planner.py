"""
LLM 补丁生成器 — 自我编程多候选方案生成器

将现有的规则引擎 SelfProgrammingPlanner 作为后备规划器，
优先使用 LLM 生成多个代码补丁候选方案，通过评分选优。

当前增强内容：
- 单次 LLM 调用返回 N 个候选方案
- CandidateScorer 对每个候选做多维评分（置信度/风险/简洁性）
- Executor 按评分顺序逐个尝试，通过验证的即采用
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from datetime import timedelta

from app.domain.models import (
    EditKind,
    SelfProgrammingEdit,
    SelfProgrammingJob,
    SelfProgrammingStatus,
    SelfProgrammingVerification,
)
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage, ChatResult
from app.self_programming.models import SelfProgrammingCandidate
from app.self_programming.planner import SelfProgrammingPlanner
from app.self_programming.scorer import CandidateScorer, ScoredCandidate

logger = logging.getLogger(__name__)

# ── 安全护栏：禁止修改的路径前缀 ──────────────────────
PROTECTED_PATHS = (
    "services/core/app/llm/gateway.py",
    "services/core/app/self_programming/executor.py",
    "services/core/app/self_programming/scorer.py",
    ".env",
    ".env.local",
)

# ── 默认参数 ────────────────────────────────────────────
DEFAULT_NUM_CANDIDATES = 3  # 要求 LLM 生成的候选数量


# ── 系统提示词（多候选版本） ──────────────────
SYSTEM_PROMPT = """你是一个自我编程 AI 助手的「补丁生成器」。
你的任务是根据错误信息或改进需求，生成 {num_candidates} 个不同的代码修改方案。

## 输出格式要求
你必须输出一个 JSON 对象：
```json
{{
  "diagnosis": "对问题的诊断（一句话）",
  "candidates": [
    {{
      "id": "candidate-A",
      "description": "这个方案的简要描述（一句话）",
      "edits": [
        {{
          "file_path": "相对项目根目录的文件路径",
          "kind": "replace | create | insert",
          "search_text": "要搜索的原始文本（用于 replace）",
          "replace_text": "替换后的文本",
          "insert_after": "插入位置锚点文本（仅 insert 类型需要）",
          "file_content": "完整文件内容（仅 create 类型需要）"
        }}
      ],
      "confidence": 0.0-1.0,
      "risk_level": "low | medium | high"
    }},
    // ... 更多候选方案 ...
  ]
}}
```

## 编辑类型说明
- **replace**: 搜索 search_text 并替换为 replace_text（最常用）
- **create**: 创建新文件，使用 file_content 字段写入**完整**的文件内容（含 import、类定义、函数体等一切必要代码）
- **insert**: 在 insert_after 锚点文本之后插入 replace_text

## create 类型特别说明
当需要新建文件时：
1. **file_content 必须包含完整可运行的代码**（不是片段！）
2. 包含所有必要的 import 语句
3. 包含完整的类/函数定义
4. 遵循项目现有代码风格
5. 示例：创建一个新测试文件时，file_content 应包含 pytest imports + test class + 所有 test 方法

## 方案多样性要求
请提供 {num_candidates} 个**不同策略**的方案：
- 至少一个**保守方案**（最小改动）
- 可以有一个**激进方案**（更彻底的重构）
- 各方案的修改点应有明显差异

## 重要约束
1. 每次修改尽量小，只改必要的部分
2. 保持原有代码风格和缩进
3. 不要添加不必要的注释或日志
4. confidence 反映你对这个方案的把握程度
5. 如果问题无法通过代码修改解决，设置 candidates 为空数组并说明原因
6. 绝对不要修改配置文件中的密钥、token 或敏感信息"""


class LLMPlanner:
    """LLM 驱动的自我编程规划器（多候选版）。

    工作流程：
    1. 接收 SelfProgrammingCandidate → 构建上下文
    2. 调用 LLM 生成 N 个结构化补丁候选
    3. 解析 + 安全校验 + 评分排序
    4. 返回最佳候选（或按评分顺序的多候选列表）
    5. 如果 LLM 失败，回退到规则引擎
    """

    def __init__(
        self,
        gateway: ChatGateway,
        workspace_root: Path | None = None,
        fallback_planner: SelfProgrammingPlanner | None = None,
        min_confidence: float = 0.2,
        num_candidates: int = DEFAULT_NUM_CANDIDATES,
        scorer: CandidateScorer | None = None,
    ) -> None:
        self.gateway = gateway
        self.workspace_root = workspace_root
        self.fallback = fallback_planner or (SelfProgrammingPlanner(workspace_root=workspace_root) if workspace_root else None)
        self.min_confidence = min_confidence
        self.num_candidates = num_candidates
        self.scorer = scorer or CandidateScorer()

    def plan(self, candidate: SelfProgrammingCandidate) -> SelfProgrammingJob:
        """主入口：LLM 多候选规划 → 选最优 → 规则引擎兜底。"""
        # 尝试 LLM 多候选规划
        try:
            scored = self._plan_with_llm(candidate)
            if scored is not None:
                return scored.job
        except Exception as exc:
            logger.warning(f"LLM planner failed, falling back to rule engine: {exc}")

        # 回退到规则引擎
        if self.fallback is not None:
            return self.fallback.plan(candidate)

        # 兜底：返回空 Job
        cooldown = _cooldown_for(candidate)
        return SelfProgrammingJob(
            reason=candidate.reason,
            target_area=candidate.target_area,
            status=SelfProgrammingStatus.FAILED,
            spec=candidate.spec,
            patch_summary="LLM 和规则引擎均无法生成补丁方案。",
            verification=SelfProgrammingVerification(commands=candidate.test_commands),
            cooldown_until=(candidate.created_at + cooldown) if candidate.created_at else None,
        )

    def plan_all(self, candidate: SelfProgrammingCandidate) -> list[ScoredCandidate]:
        """返回所有评分后的候选方案（供外部做 A/B 测试）。

        返回按 score 降序排列的候选列表。
        """
        try:
            raw_candidates = self._generate_candidates(candidate)
            if not raw_candidates:
                return []
            return self._score_and_rank(raw_candidates, candidate)
        except Exception as exc:
            logger.warning(f"LLM multi-candidate generation failed: {exc}")
            return []

    def _plan_with_llm(self, candidate: SelfProgrammingCandidate) -> ScoredCandidate | None:
        """调用 LLM 生成多候选 → 评分 → 返回最佳。"""
        raw_candidates = self._generate_candidates(candidate)
        if not raw_candidates:
            return None

        ranked = self._score_and_rank(raw_candidates, candidate)
        best = ranked[0]

        # 最佳候选也必须过最低置信度门槛
        if best.confidence < self.min_confidence:
            logger.info(f"Best candidate confidence too low ({best.confidence}), falling back")
            return None

        logger.info(
            f"Selected candidate '{best.candidate_id}' with score {best.total_score:.2f} "
            f"(confidence={best.confidence:.2f}, risk={best.risk_level})"
        )
        return best

    def _generate_candidates(
        self, candidate: SelfProgrammingCandidate
    ) -> list[tuple[str, list[SelfProgrammingEdit], dict]]:
        """调用 LLM 并解析出多个候选方案。

        返回 [(candidate_id, edits, metadata), ...] 列表。
        """
        user_prompt = self._build_user_prompt(candidate)

        messages = [
            ChatMessage(
                role="system",
                content=SYSTEM_PROMPT.format(num_candidates=self.num_candidates),
            ),
            ChatMessage(role="user", content=user_prompt),
        ]

        result: ChatResult = self.gateway.create_response(messages)
        candidates_data = self._parse_multi_candidate_response(result.output_text)

        if not candidates_data:
            return []

        output: list[tuple[str, list[SelfProgrammingEdit], dict]] = []
        for cand_id, edits, metadata in candidates_data:
            # 安全检查所有 edit
            safe = True
            for edit in edits:
                if not self._is_safe_edit(edit):
                    logger.warning(f"Rejected unsafe edit in candidate '{cand_id}': {edit.file_path}")
                    safe = False
                    break
            if safe and edits:
                output.append((cand_id, edits, metadata))

        return output

    def _score_and_rank(
        self,
        raw_candidates: list[tuple[str, list[SelfProgrammingEdit], dict]],
        candidate: SelfProgrammingCandidate,
    ) -> list[ScoredCandidate]:
        """对原始候选进行评分和排序。"""
        scored_list: list[ScoredCandidate] = []
        for cand_id, edits, metadata in raw_candidates:
            cooldown = _cooldown_for(candidate)
            job = SelfProgrammingJob(
                reason=candidate.reason,
                target_area=candidate.target_area,
                status=SelfProgrammingStatus.DIAGNOSING,
                spec=candidate.spec,
                test_edits=[],
                edits=edits,
                verification=SelfProgrammingVerification(commands=candidate.test_commands),
                patch_summary=f"[LLM-{cand_id}] {metadata.get('description', metadata.get('diagnosis', ''))}",
                cooldown_until=(candidate.created_at + cooldown) if candidate.created_at else None,
            )
            scored = self.scorer.score(job, metadata)
            scored_list.append(scored)

        # 按总分降序排列
        scored_list.sort(key=lambda sc: sc.total_score, reverse=True)
        return scored_list

    def _build_user_prompt(self, candidate: SelfProgrammingCandidate) -> str:
        """构建发送给 LLM 的用户上下文。"""
        parts = [
            f"## 任务\n{candidate.spec}\n",
            f"## 原因\n{candidate.reason}\n",
            f"## 目标区域\n{candidate.target_area}\n",
            f"## 触发类型\n{candidate.trigger.value}\n",
        ]

        if candidate.test_commands:
            parts.append(
                f"## 测试命令\n"
                + "\n".join(f"- `{cmd}`" for cmd in candidate.test_commands)
                + "\n"
            )

        # 附带相关源码上下文
        if self.workspace_root is not None:
            source_context = self._gather_source_context(candidate)
            if source_context:
                parts.append(f"## 相关源码\n```\n{source_context}\n```")

        return "\n".join(parts)

    def _gather_source_context(self, candidate: SelfProgrammingCandidate, max_lines: int = 120) -> str:
        """收集与 candidate 相关的源码上下文，帮助 LLM 做出精准修改。"""
        lines: list[str] = []

        if self.workspace_root is None:
            return ""

        # 从测试命令推断目标文件
        target_files: set[Path] = set()
        for cmd in candidate.test_commands:
            for token in cmd.split():
                if token.endswith(".py"):
                    p = self.workspace_root / token
                    if p.exists():
                        target_files.add(p)

        # 根据目标区域补充可能相关的源码文件
        area_file_map = {
            "agent": ["services/core/app/agent/loop.py", "services/core/app/agent/autonomy.py"],
            "planning": ["services/core/app/planning/morning_plan.py"],
            "ui": ["apps/desktop/src/App.tsx", "apps/desktop/src/components/StatusPanel.tsx"],
        }
        for rel_path in area_file_map.get(candidate.target_area, []):
            p = self.workspace_root / rel_path
            if p.exists():
                target_files.add(p)

        for path in sorted(target_files)[:5]:  # 最多 5 个文件
            try:
                content = path.read_text(encoding="utf-8")
                rel = path.relative_to(self.workspace_root).as_posix()
                file_lines = content.splitlines()
                total_lines = len(file_lines)
                # 截断过大的文件
                if total_lines > max_lines:
                    half = max_lines // 2
                    content = "\n".join(
                        file_lines[:half]
                        + [f"\n... (省略 {total_lines - max_lines} 行) ..."]
                        + file_lines[-half:]
                    )
                lines.append(f"# {rel} ({total_lines} 行)")
                lines.append(content)
            except Exception as exc:
                lines.append(f"# {path.name} (读取失败: {exc})")

        return "\n\n".join(lines)

    @staticmethod
    def _parse_multi_candidate_response(text: str) -> list[tuple[str, list[SelfProgrammingEdit], dict]]:
        """从 LLM 输出解析多候选方案数据。

        返回 [(candidate_id, edits_list, metadata_dict), ...]，解析失败返回空列表。
        """
        json_str = text.strip()

        # 移除 markdown 代码块标记
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        first_brace = json_str.find("{")
        last_brace = json_str.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            json_str = json_str[first_brace : last_brace + 1]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM response as JSON: {text[:200]}...")
            return []

        diagnosis = data.get("diagnosis", "")
        candidates_raw = data.get("candidates", [])

        output: list[tuple[str, list[SelfProgrammingEdit], dict]] = []
        for idx, cand_data in enumerate(candidates_raw):
            cand_id = cand_data.get("id", f"candidate-{chr(65 + idx)}")
            edits = LLMPlanner._parse_edits(cand_data)
            metadata = {
                "diagnosis": diagnosis or cand_data.get("description", ""),
                "confidence": float(cand_data.get("confidence", data.get("confidence", 0.5))),
                "risk_level": cand_data.get("risk_level", data.get("risk_level", "medium")),
                "explanation": cand_data.get("explanation", data.get("explanation", "")),
                "description": cand_data.get("description", ""),
            }
            if edits:
                output.append((cand_id, edits, metadata))

        return output

    @staticmethod
    def _parse_edits(data: dict) -> list[SelfProgrammingEdit]:
        """从单个候选数据中解析 edits 列表。"""
        edits: list[SelfProgrammingEdit] = []
        for edit_data in data.get("edits", []):
            kind_str = edit_data.get("kind", "replace")
            try:
                kind = EditKind(kind_str)
            except ValueError:
                kind = EditKind.REPLACE

            edit_kwargs: dict = {
                "file_path": edit_data["file_path"],
                "kind": kind,
            }

            if kind == EditKind.CREATE:
                edit_kwargs["file_content"] = edit_data.get("file_content", "")
            elif kind == EditKind.INSERT:
                edit_kwargs["insert_after"] = edit_data.get("insert_after")
                edit_kwargs["replace_text"] = edit_data.get("replace_text", "")
            else:  # REPLACE
                edit_kwargs["search_text"] = edit_data.get("search_text", "")
                edit_kwargs["replace_text"] = edit_data.get("replace_text", "")

            edits.append(SelfProgrammingEdit(**edit_kwargs))

        return edits

    @staticmethod
    def _is_safe_edit(edit: SelfProgrammingEdit) -> bool:
        """安全校验：拒绝修改受保护路径的文件。"""
        fp = edit.file_path
        for protected in PROTECTED_PATHS:
            if fp.endswith(protected) or protected in fp:
                return False
        if re.search(r"\.env(\.|$)", fp):
            return False
        return True


def _cooldown_for(candidate: SelfProgrammingCandidate) -> timedelta:
    """根据触发类型返回冷却时间。"""
    return (
        timedelta(hours=1)
        if candidate.trigger.value == "hard_failure"
        else timedelta(hours=12)
    )
