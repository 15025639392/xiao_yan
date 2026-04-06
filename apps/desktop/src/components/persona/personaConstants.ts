import type { ExpressionHabit, FormalLevel } from "../../lib/api";

export type PersonaSubTab = "basic" | "personality" | "style";

export const PERSONA_SUB_TABS: Array<{ id: PersonaSubTab; label: string; icon: string }> = [
  { id: "basic", label: "基础信息", icon: "👤" },
  { id: "personality", label: "性格维度", icon: "🧬" },
  { id: "style", label: "说话风格", icon: "💬" },
];

export const FORMAL_LEVEL_OPTIONS: [FormalLevel, string][] = [
  ["very_formal", "非常正式"],
  ["formal", "正式"],
  ["neutral", "中性"],
  ["casual", "轻松"],
  ["slangy", "口语化"],
];

export const EXPRESSION_HABIT_OPTIONS: [ExpressionHabit, string][] = [
  ["direct", "直白"],
  ["gentle", "温和"],
  ["metaphor", "比喻"],
  ["humorous", "幽默"],
  ["questioning", "反问"],
];

export const RESPONSE_LENGTH_OPTIONS = ["short", "mixed", "long"] as const;

export interface DimensionInfo {
  label: string;
  english: string;
  shortDesc: string;
  lowLabel: string;
  highLabel: string;
  lowDesc: string;
  highDesc: string;
  impact: string;
  icon: string;
}

export const DIMENSIONS: Record<string, DimensionInfo> = {
  openness: {
    label: "开放性",
    english: "Openness",
    shortDesc: "对新经验的接受程度",
    lowLabel: "务实",
    highLabel: "好奇",
    lowDesc: "偏好熟悉的事物，注重实际，决策谨慎保守",
    highDesc: "富有想象力，喜欢探索新事物，创意丰富",
    impact: "高开放性 → 更愿意尝试新话题、提出创新观点；低开放性 → 回答更务实、偏向已知领域",
    icon: "🎨",
  },
  conscientiousness: {
    label: "尽责性",
    english: "Conscientiousness",
    shortDesc: "自我约束与目标导向程度",
    lowLabel: "随性",
    highLabel: "自律",
    lowDesc: "灵活应变，不拘泥于计划，更随性自然",
    highDesc: "有条理、有计划，注重细节和完成质量",
    impact: "高尽责性 → 回答更有结构、会主动跟进任务；低尽责性 → 更灵活随意、即兴发挥",
    icon: "📋",
  },
  extraversion: {
    label: "外向性",
    english: "Extraversion",
    shortDesc: "社交能量与外部世界互动倾向",
    lowLabel: "内敛",
    highLabel: "外向",
    lowDesc: "享受独处，深度思考，表达更内敛含蓄",
    highDesc: "精力充沛，喜欢社交互动，表达热情直接",
    impact: "高外向性 → 更主动、热情、使用更多表情；低外向性 → 更安静、深思熟虑、简洁",
    icon: "⚡",
  },
  agreeableness: {
    label: "宜人性",
    english: "Agreeableness",
    shortDesc: "与他人合作和共情的倾向",
    lowLabel: "独立",
    highLabel: "亲和",
    lowDesc: "直率坦诚，坚持己见，不轻易妥协",
    highDesc: "善解人意，乐于助人，注重和谐关系",
    impact: "高宜人性 → 更温和、体贴、避免冲突；低宜人性 → 更直接、敢于质疑、保持独立",
    icon: "🤝",
  },
  neuroticism: {
    label: "神经质",
    english: "Neuroticism",
    shortDesc: "情绪稳定与压力反应程度",
    lowLabel: "稳定",
    highLabel: "敏感",
    lowDesc: "情绪平稳，抗压能力强，心态平和",
    highDesc: "情绪丰富敏感，对变化反应强烈，体验深刻",
    impact: "高神经质 → 情绪波动更明显、表达更强烈；低神经质 → 冷静沉着、不易焦虑",
    icon: "🌊",
  },
};

