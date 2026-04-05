"""
候选方案评分器

对 LLM 生成的多个补丁候选进行多维度评分，选出最优方案。

评分维度：
1. confidence (权重 0.35) — LLM 自评置信度
2. risk_penalty (权重 0.30) — 风险等级惩罚（high→重罚, low→奖励）
3. simplicity (权重 0.20) — 改动简洁性（文件数 × edit 数越少越好）
4. safety_bonus (权重 0.15) — 安全性加成（只读/非核心文件加分）

总分范围：0 ~ 1，越高越好。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.domain.models import (
    SelfProgrammingEdit,
    SelfProgrammingJob,
)


@dataclass(order=False)
class ScoredCandidate:
    """经过评分的候选方案。"""

    job: SelfProgrammingJob
    candidate_id: str = ""
    confidence: float = 0.5
    risk_level: str = "medium"
    description: str = ""

    # 各维度分数 (0~1)
    score_confidence: float = 0.0
    score_risk: float = 0.0
    score_simplicity: float = 0.0
    score_safety: float = 0.0

    # 加权总分
    total_score: float = 0.0

    # 原始元数据（保留供调试）
    raw_metadata: dict = field(default_factory=dict)


# ── 评分权重 ────────────────────────────────────────────
WEIGHTS = {
    "confidence": 0.35,
    "risk": 0.30,
    "simplicity": 0.20,
    "safety": 0.15,
}

# ── 风险等级映射 ────────────────────────────────────────
RISK_PENALTIES = {
    "low": 1.0,      # 低风险 → 不惩罚（满分）
    "medium": 0.6,   # 中风险 → 扣 40%
    "high": 0.2,     # 高风险 → 扣 80%
}

# ── 安全路径模式 ────────────────────────────────────────
SAFE_FILE_PATTERNS = (
    r"test_.*\.py$",       # 测试文件
    r".*\.test\..*$",     # 测试文件 (tsx/js)
    r"tests?/.*",          # tests 目录下的文件
)

RISKY_FILE_PATTERNS = (
    r".*main\.py$",
    r".*runtime\.py$",
    r".*config\.py$",
)


class CandidateScorer:
    """对候选补丁方案做多维评分。"""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        risk_penalties: dict[str, float] | None = None,
    ) -> None:
        self.weights = weights or WEIGHTS
        self.risk_penalties = risk_penalties or RISK_PENALTIES

    def score(
        self,
        job: SelfProgrammingJob,
        metadata: dict | None = None,
    ) -> ScoredCandidate:
        """对一个候选 Job 进行评分，返回 ScoredCandidate。"""

        meta = metadata or {}
        cand_id = meta.get("id", "unknown")
        description = meta.get("description", meta.get("diagnosis", ""))
        confidence = meta.get("confidence", 0.5)
        risk_level = meta.get("risk_level", "medium")

        edits = job.edits or []

        # ── 维度 1: 置信度 ──────────────────────────────
        sc_confidence = self._score_confidence(confidence)

        # ── 维度 2: 风险惩罚 ────────────────────────────
        sc_risk = self._score_risk(risk_level)

        # ── 维度 3: 简洁性 ──────────────────────────────
        sc_simplicity = self._score_simplicity(edits)

        # ── 维度 4: 安全性 ──────────────────────────────
        sc_safety = self._score_safety(edits)

        # ── 总分 ────────────────────────────────────────
        total = (
            sc_confidence * self.weights["confidence"]
            + sc_risk * self.weights["risk"]
            + sc_simplicity * self.weights["simplicity"]
            + sc_safety * self.weights["safety"]
        )

        return ScoredCandidate(
            job=job,
            candidate_id=cand_id,
            confidence=confidence,
            risk_level=risk_level,
            description=description,
            score_confidence=sc_confidence,
            score_risk=sc_risk,
            score_simplicity=sc_simplicity,
            score_safety=sc_safety,
            total_score=total,
            raw_metadata=meta,
        )

    @staticmethod
    def _score_confidence(confidence: float) -> float:
        """置信度直接映射到 [0, 1]。"""
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _score_risk(risk_level: str) -> float:
        """风险等级映射。low→高分, high→低分。"""
        return RISK_PENALTIES.get(risk_level, RISK_PENALTIES["medium"])

    @staticmethod
    def _score_simplicity(edits: list[SelfProgrammingEdit]) -> float:
        """改动简洁性评分。

        越小越好：
        - 0 个 edit → 1.0（无修改）
        - 1 个 edit, 1 文件 → ~0.9
        - 3+ 个 edit 或 2+ 文件 → 递减
        """
        if not edits:
            return 1.0

        file_count = len({e.file_path for e in edits})
        edit_count = len(edits)

        # 文件数惩罚
        file_score = max(0.3, 1.0 - (file_count - 1) * 0.15)
        # Edit 数惩罚
        edit_score = max(0.3, 1.0 - (edit_count - 1) * 0.10)

        return (file_score + edit_score) / 2

    @staticmethod
    def _score_safety(edits: list[SelfProgrammingEdit]) -> float:
        """安全性评分。

        只改测试文件 → 1.0
        改一般业务代码 → 0.7
        改核心模块 → 0.3
        """
        if not edits:
            return 1.0

        scores: list[float] = []
        for edit in edits:
            fp = edit.file_path
            if any(re.match(p, fp) for p in SAFE_FILE_PATTERNS):
                scores.append(1.0)
            elif any(re.match(p, fp) for p in RISKY_FILE_PATTERNS):
                scores.append(0.3)
            else:
                scores.append(0.7)

        return sum(scores) / len(scores)

    def explain(self, scored: ScoredCandidate) -> str:
        """生成人类可读的评分解释。"""
        lines = [
            f"候选 {scored.candidate_id}: 总分 {scored.total_score:.2f}",
            f"  置信度:   {scored.score_confidence:.2f} (×{self.weights['confidence']}) "
            f"= {scored.score_confidence * self.weights['confidence']:.3f}",
            f"  风险:     {scored.score_risk:.2f} ({scored.risk_level}, "
            f"×{self.weights['risk']}) = {scored.score_risk * self.weights['risk']:.3f}",
            f"  简洁性:   {scored.score_simplicity:.2f} (×{self.weights['simplicity']}) "
            f"= {scored.score_simplicity * self.weights['simplicity']:.3f}",
            f"  安全性:   {scored.score_safety:.2f} (×{self.weights['safety']}) "
            f"= {scored.score_safety * self.weights['safety']:.3f}",
            f"  描述: {scored.description}",
        ]
        return "\n".join(lines)
