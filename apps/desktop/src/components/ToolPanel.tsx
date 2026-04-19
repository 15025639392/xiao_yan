import { useEffect, useState } from "react";
import type { ToolsListResponse, ToolsStatusResponse } from "../lib/api";
import { fetchTools, fetchToolsStatus } from "../lib/api";
import { Button, StatusBadge } from "./ui";
import { FilesTab } from "./tools/FilesTab";
import { HistoryTab } from "./tools/HistoryTab";
import { StatusTab } from "./tools/StatusTab";
import { ToolTabs } from "./tools/ToolTabs";
import type { ToolTabType } from "./tools/toolTypes";
import { getSuccessRateBadgeStyle } from "./tools/toolUtils";
import { ToolsBrowseTab } from "./tools/ToolsBrowseTab";
import { McpManageTab } from "./tools/McpManageTab";
import { SkillsManageTab } from "./tools/SkillsManageTab";
import { CapabilitiesPage } from "../pages/CapabilitiesPage";

type ToolPanelProps = {
  initialTab?: ToolTabType;
};

const TOOL_COLLECTION_TABS: ToolTabType[] = ["tools"];

const SECONDARY_TAB_ACTIONS: Array<{ tab: ToolTabType; label: string }> = [
  { tab: "capabilities", label: "能力详情" },
  { tab: "tools", label: "能力目录" },
  { tab: "history", label: "调用记录" },
  { tab: "status", label: "状态概览" },
  { tab: "mcp", label: "MCP 接入" },
  { tab: "skills", label: "技能选择" },
];

export function ToolPanel({ initialTab = "files" }: ToolPanelProps) {
  const [activeTab, setActiveTab] = useState<ToolTabType>(initialTab);
  const [tools, setTools] = useState<ToolsListResponse | null>(null);
  const [status, setStatus] = useState<ToolsStatusResponse | null>(null);

  useEffect(() => {
    if (!TOOL_COLLECTION_TABS.includes(activeTab) || tools) {
      return;
    }
    fetchTools().then(setTools).catch(() => {});
  }, [activeTab, tools]);

  useEffect(() => {
    if (activeTab !== "status" || status) {
      return;
    }
    fetchToolsStatus().then(setStatus).catch(() => {});
  }, [activeTab, status]);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  const successRate = status?.statistics?.success_rate;
  const allowedCommandCount = status?.allowed_command_count;
  const successRateBadgeStyle =
    typeof successRate === "number" ? getSuccessRateBadgeStyle(successRate) : undefined;

  return (
    <section className="tool-panel">
      <div className="tool-panel__header">
        <div className="panel__title-group" style={{ marginBottom: 0 }}>
          <div className="panel__icon">🛠️</div>
          <div>
            <h2 className="panel__title">外部能力</h2>
            <p className="panel__subtitle">文件、接入能力与运行状态都收在这里按需查看。</p>
          </div>
        </div>

        {status ? (
          <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
            {typeof successRate === "number" ? (
              <StatusBadge
                style={successRateBadgeStyle}
              >
                成功率 {Math.round(successRate * 100)}%
              </StatusBadge>
            ) : null}
            {typeof allowedCommandCount === "number" ? (
              <span style={{ fontSize: "0.75rem", color: "var(--text-tertiary)" }}>
                {allowedCommandCount} 个扩展工具可用
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      <ToolTabs activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="tool-panel__secondary">
        <div className="tool-panel__secondary-label">延伸查看</div>
        <div className="tool-panel__secondary-actions">
          {SECONDARY_TAB_ACTIONS.map(({ tab, label }) => (
            <Button
              key={tab}
              type="button"
              variant={activeTab === tab ? "default" : "secondary"}
              size="sm"
              className="tool-panel__secondary-btn"
              onClick={() => setActiveTab(tab)}
            >
              {label}
            </Button>
          ))}
        </div>
      </div>

      <div className="tool-panel__body">
        {activeTab === "capabilities" ? <CapabilitiesPage /> : null}
        {activeTab === "tools" ? <ToolsBrowseTab tools={tools} /> : null}
        {activeTab === "mcp" ? <McpManageTab /> : null}
        {activeTab === "skills" ? <SkillsManageTab /> : null}
        {activeTab === "files" ? <FilesTab /> : null}
        {activeTab === "history" ? <HistoryTab /> : null}
        {activeTab === "status" ? (
          <StatusTab status={status} onRefresh={() => void fetchToolsStatus().then(setStatus).catch(() => {})} />
        ) : null}
      </div>
    </section>
  );
}
