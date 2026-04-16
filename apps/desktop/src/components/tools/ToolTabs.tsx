import { Tabs, TabsList, TabsTrigger } from "../ui";
import type { ToolTabType } from "./toolTypes";

type ToolTabsProps = {
  activeTab: ToolTabType;
  onTabChange: (tab: ToolTabType) => void;
};

const TABS: [ToolTabType, string, string][] = [
  ["execute", "⚡ 执行", "运行工具命令"],
  ["tools", "📋 工具", "浏览可用工具"],
  ["mcp", "🧩 MCP", "管理 MCP Server 配置"],
  ["skills", "🎯 Skills", "管理对话技能工作流"],
  ["files", "📁 文件", "文件浏览与搜索"],
  ["history", "📜 历史", "执行记录"],
  ["status", "📊 状态", "系统统计"],
  ["capabilities", "🧠 能力", "查看能力契约、审批与审计"],
];

export function ToolTabs({ activeTab, onTabChange }: ToolTabsProps) {
  return (
    <Tabs value={activeTab} onValueChange={(value) => onTabChange(value as ToolTabType)}>
      <TabsList className="tool-tabs">
      {TABS.map(([tabKey, label, hint]) => (
        <TabsTrigger
          key={tabKey}
          value={tabKey}
          className={`tool-tab ${activeTab === tabKey ? "tool-tab--active" : ""}`}
          title={hint}
        >
          {label}
        </TabsTrigger>
      ))}
      </TabsList>
    </Tabs>
  );
}
