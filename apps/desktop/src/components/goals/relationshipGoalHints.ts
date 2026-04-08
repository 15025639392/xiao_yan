import type { Goal, RelationshipSummary } from "../../lib/api";

export type GoalRelationshipHint = {
  tone: "boundary" | "commitment" | "preference";
  label: string;
  reason: string;
};

function includesAny(text: string, markers: string[]): boolean {
  return markers.some((marker) => text.includes(marker));
}

function meaningfulTokens(text: string): Set<string> {
  const tokens = new Set<string>();
  const asciiWords = text.toLowerCase().match(/[a-z0-9_]+/g) ?? [];
  asciiWords.forEach((word) => {
    if (word.length >= 3) {
      tokens.add(word);
    }
  });

  const cjkChunks = text.match(/[\u4e00-\u9fff]+/g) ?? [];
  const stopTokens = new Set(["继续", "推进", "用户", "计划", "整理"]);
  cjkChunks.forEach((chunk) => {
    if (chunk.length === 1) {
      return;
    }

    for (let index = 0; index < chunk.length - 1; index += 1) {
      tokens.add(chunk.slice(index, index + 2));
    }

    if (chunk.length <= 8) {
      tokens.add(chunk);
    }
  });

  return new Set(Array.from(tokens).filter((token) => token.length >= 2 && !stopTokens.has(token)));
}

function textOverlapRatio(left: string, right: string): number {
  const leftTokens = meaningfulTokens(left);
  const rightTokens = meaningfulTokens(right);
  if (leftTokens.size === 0 || rightTokens.size === 0) {
    return 0;
  }

  const overlap = Array.from(leftTokens).filter((token) => rightTokens.has(token));
  return overlap.length / leftTokens.size;
}

export function getGoalRelationshipHints(goal: Goal, relationship: RelationshipSummary | null): GoalRelationshipHint[] {
  if (!relationship || !relationship.available) {
    return [];
  }

  const title = goal.title.trim();
  if (!title) {
    return [];
  }

  const hints: GoalRelationshipHint[] = [];

  const hasNoPressureBoundary = relationship.boundaries.some((boundary) => includesAny(boundary, ["别催", "不要催"]));
  if (hasNoPressureBoundary && includesAny(title, ["催", "逼", "尽快", "马上", "立刻", "现在就"])) {
    hints.push({
      tone: "boundary",
      label: "避免催促",
      reason: "这类目标容易把关系推成催促式推进，节奏需要更柔和。",
    });
  }

  const hasAutonomyBoundary = relationship.boundaries.some((boundary) =>
    includesAny(boundary, ["先自己想", "自己想", "自己决定", "自己判断"]),
  );
  if (hasAutonomyBoundary && includesAny(title, ["决定", "判断", "选择", "结论", "方案"])) {
    hints.push({
      tone: "boundary",
      label: "让用户自己判断",
      reason: "这类目标要支持用户自己比较和判断，不替用户拍板。",
    });
  }

  const matchingCommitment = relationship.commitments.find((commitment) => textOverlapRatio(commitment, title) >= 0.2);
  if (matchingCommitment) {
    hints.push({
      tone: "commitment",
      label: "承接承诺",
      reason: `可以直接服务这项承诺：${matchingCommitment}`,
    });
  }

  const matchingPreference = relationship.preferences.find((preference) => textOverlapRatio(preference, title) >= 0.2);
  if (matchingPreference) {
    hints.push({
      tone: "preference",
      label: "贴合偏好",
      reason: `推进方式和这个偏好一致：${matchingPreference}`,
    });
  }

  return hints;
}
