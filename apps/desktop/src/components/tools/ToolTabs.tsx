import { Tabs, TabsList, TabsTrigger } from "../ui";
import type { ToolTabType } from "./toolTypes";

type ToolTabsProps = {
  activeTab: ToolTabType;
  onTabChange: (tab: ToolTabType) => void;
};

const DEFAULT_TABS: [ToolTabType, string, string][] = [
  ["execute", "⚡ 执行", "运行工具命令"],
  ["files", "📁 文件", "文件浏览与搜索"],
];

export function ToolTabs({ activeTab, onTabChange }: ToolTabsProps) {
  return (
    <Tabs value={activeTab} onValueChange={(value) => onTabChange(value as ToolTabType)}>
      <TabsList className="tool-tabs">
      {DEFAULT_TABS.map(([tabKey, label, hint]) => (
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
