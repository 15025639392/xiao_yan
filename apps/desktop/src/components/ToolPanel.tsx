import { useEffect, useState } from "react";
import type { ToolsListResponse, ToolsStatusResponse } from "../lib/api";
import { fetchToolHistory, fetchTools, fetchToolsStatus } from "../lib/api";
import { ExecuteTab } from "./tools/ExecuteTab";
import { FilesTab } from "./tools/FilesTab";
import { HistoryTab } from "./tools/HistoryTab";
import { StatusTab } from "./tools/StatusTab";
import { ToolTabs } from "./tools/ToolTabs";
import type { ToolTabType } from "./tools/toolTypes";
import { ToolsBrowseTab } from "./tools/ToolsBrowseTab";

export function ToolPanel() {
  const [activeTab, setActiveTab] = useState<ToolTabType>("execute");
  const [tools, setTools] = useState<ToolsListResponse | null>(null);
  const [status, setStatus] = useState<ToolsStatusResponse | null>(null);

  useEffect(() => {
    fetchTools().then(setTools).catch(() => {});
    fetchToolsStatus().then(setStatus).catch(() => {});
  }, []);

  return (
    <section className="tool-panel">
      <div className="tool-panel__header">
        <div className="panel__title-group" style={{ marginBottom: 0 }}>
          <div className="panel__icon">🛠️</div>
          <div>
            <h2 className="panel__title">工具箱</h2>
            <p className="panel__subtitle">命令执行 · 文件操作 · 工具状态</p>
          </div>
        </div>

        {status ? (
          <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
            <span
              className="status-badge"
              style={
                status.statistics.success_rate >= 0.8
                  ? { background: "var(--success-muted)", color: "var(--success)" }
                  : status.statistics.success_rate >= 0.5
                    ? { background: "var(--warning-muted)", color: "var(--warning)" }
                    : { background: "var(--danger-muted)", color: "var(--danger)" }
              }
            >
              成功率 {Math.round(status.statistics.success_rate * 100)}%
            </span>
            <span style={{ fontSize: "0.75rem", color: "var(--text-tertiary)" }}>
              {status.allowed_command_count} 个工具可用
            </span>
          </div>
        ) : null}
      </div>

      <ToolTabs activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="tool-panel__body">
        {activeTab === "execute" ? (
          <ExecuteTab tools={tools} onExecuted={() => void fetchToolHistory().catch(() => {})} />
        ) : null}
        {activeTab === "tools" ? <ToolsBrowseTab tools={tools} /> : null}
        {activeTab === "files" ? <FilesTab /> : null}
        {activeTab === "history" ? <HistoryTab /> : null}
        {activeTab === "status" ? (
          <StatusTab status={status} onRefresh={() => void fetchToolsStatus().then(setStatus).catch(() => {})} />
        ) : null}
      </div>
    </section>
  );
}

