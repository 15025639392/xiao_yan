import { useState } from "react";

import { MemoryPanel, type MemoryPanelMode } from "../components/MemoryPanel";
import { KnowledgeReviewPanel } from "../components/KnowledgeReviewPanel";

export function MemoryPage({ assistantName }: { assistantName: string }) {
  const [mode, setMode] = useState<MemoryPanelMode | "review">("all");

  const subtitle =
    mode === "review"
      ? "知识专项治理：审核自动抽取内容，确保长期知识可控可信"
      :
    mode === "knowledge"
      ? "当前为结构化知识模式，仅展示服务端 knowledge 命名空间数据"
      : "浏览和管理数字人的全部记忆";

  return (
    <div className="memory-page">
      <header className="memory-page__header">
        <h2 className="memory-page__title">记忆库</h2>
        <p className="memory-page__subtitle">{subtitle}</p>
        <div className="memory-page__mode-switch" role="tablist" aria-label="记忆模式切换">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "all"}
            className={`memory-page__mode-btn ${mode === "all" ? "memory-page__mode-btn--active" : ""}`}
            onClick={() => setMode("all")}
          >
            全部记忆
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "knowledge"}
            className={`memory-page__mode-btn ${mode === "knowledge" ? "memory-page__mode-btn--active" : ""}`}
            onClick={() => setMode("knowledge")}
          >
            结构化知识
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "review"}
            className={`memory-page__mode-btn ${mode === "review" ? "memory-page__mode-btn--active" : ""}`}
            onClick={() => setMode("review")}
          >
            知识审核
          </button>
        </div>
      </header>
      <div className="memory-page__content">
        {mode === "review" ? (
          <KnowledgeReviewPanel />
        ) : (
          <MemoryPanel assistantName={assistantName} mode={mode} />
        )}
      </div>
    </div>
  );
}
