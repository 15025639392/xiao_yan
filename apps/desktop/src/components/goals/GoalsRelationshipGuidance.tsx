import type { RelationshipSummary } from "../../lib/api";

type GoalsRelationshipGuidanceProps = {
  relationship: RelationshipSummary | null;
};

type GuidanceTone = "boundary" | "commitment" | "preference";

type GuidanceItem = {
  tone: GuidanceTone;
  label: string;
  content: string;
};

function dedupeItems(items: GuidanceItem[]): GuidanceItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.tone}:${item.content}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function buildBoundaryGuidance(boundary: string): GuidanceItem[] {
  const items: GuidanceItem[] = [];

  if (boundary.includes("别催") || boundary.includes("不要催")) {
    items.push({
      tone: "boundary",
      label: "边界优先",
      content: "避免把目标做成催促式推进，别逼用户现在就决定。",
    });
  }

  if (
    boundary.includes("先自己想") ||
    boundary.includes("自己想") ||
    boundary.includes("自己决定") ||
    boundary.includes("自己判断")
  ) {
    items.push({
      tone: "boundary",
      label: "判断归还用户",
      content: "涉及重要判断时，优先支持用户自己比较、思考、决定。",
    });
  }

  if (boundary.includes("空间")) {
    items.push({
      tone: "boundary",
      label: "节奏放缓",
      content: "给关系留出空间，避免把目标设计成高压式连续推进。",
    });
  }

  if (items.length === 0) {
    items.push({
      tone: "boundary",
      label: "边界优先",
      content: `新增目标先确认不触碰这条边界：${boundary}`,
    });
  }

  return items;
}

function buildGuidanceItems(relationship: RelationshipSummary): GuidanceItem[] {
  const items: GuidanceItem[] = relationship.boundaries.flatMap(buildBoundaryGuidance);

  if (relationship.commitments[0]) {
    items.push({
      tone: "commitment",
      label: "承诺优先",
      content: `优先让目标服务这项承诺：${relationship.commitments[0]}`,
    });
  }

  if (relationship.preferences[0]) {
    items.push({
      tone: "preference",
      label: "方式贴合",
      content: `推进方式尽量贴合这个偏好：${relationship.preferences[0]}`,
    });
  }

  return dedupeItems(items);
}

export function GoalsRelationshipGuidance({ relationship }: GoalsRelationshipGuidanceProps) {
  if (!relationship || !relationship.available) {
    return null;
  }

  const items = buildGuidanceItems(relationship);
  if (items.length === 0) {
    return null;
  }

  return (
    <section className="goals-guidance" aria-label="目标关系约束">
      <div className="goals-guidance__header">
        <span className="goals-guidance__title">目标关系约束</span>
        <span className="goals-guidance__hint">新目标能不能推进，先看是否尊重边界、承接承诺、贴合偏好。</span>
      </div>

      <div className="goals-guidance__items">
        {items.map((item) => (
          <div key={`${item.label}:${item.content}`} className={`goals-guidance__item goals-guidance__item--${item.tone}`}>
            <span className="goals-guidance__label">{item.label}</span>
            <span className="goals-guidance__content">{item.content}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
