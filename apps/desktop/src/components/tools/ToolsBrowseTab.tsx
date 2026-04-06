import { useMemo, useState } from "react";
import type { ToolInfo, ToolsListResponse } from "../../lib/api";
import { getCategoryIcon, getCategoryName, getSafetyLevelColor, getSafetyLevelLabel } from "./toolUtils";

type ToolsBrowseTabProps = {
  tools: ToolsListResponse | null;
};

export function ToolsBrowseTab({ tools }: ToolsBrowseTabProps) {
  const [filter, setFilter] = useState("");

  const filteredByCategory = useMemo(() => {
    if (!tools) return [] as Array<[string, ToolInfo[]]>;
    return Object.entries(tools.by_category)
      .map(([category, categoryTools]) => {
        const visible = filter
          ? categoryTools.filter((tool) => tool.name.includes(filter) || tool.description.includes(filter))
          : categoryTools;
        return [category, visible] as [string, ToolInfo[]];
      })
      .filter(([, visible]) => visible.length > 0);
  }, [tools, filter]);

  if (!tools) {
    return <p style={{ color: "var(--text-tertiary)" }}>加载中...</p>;
  }

  return (
    <div className="tools-browse-tab">
      <input
        type="text"
        className="tools-search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="搜索工具..."
      />

      {filteredByCategory.map(([category, categoryTools]) => (
        <div key={category} className="tools-category">
          <h4 className="tools-category__title">
            {getCategoryIcon(category)}
            {getCategoryName(category)}
            <span className="tools-category__count">{categoryTools.length}</span>
          </h4>
          <div className="tools-grid">
            {categoryTools.map((tool) => (
              <div key={tool.name} className="tool-card">
                <div className="tool-card__header">
                  <code className="tool-card__name">{tool.name}</code>
                  <span
                    className="tool-card__level"
                    style={{ color: getSafetyLevelColor(tool.safety_level) }}
                    title={getSafetyLevelLabel(tool.safety_level)}
                  >
                    {getSafetyLevelLabel(tool.safety_level)}
                  </span>
                </div>
                <p className="tool-card__desc">{tool.description}</p>
                {tool.examples.length > 0 ? (
                  <div className="tool-card__examples">
                    {tool.examples.slice(0, 3).map((example) => (
                      <button
                        key={example}
                        type="button"
                        className="tool-example-btn"
                        title="点击填入执行框"
                      >
                        {example.length > 40 ? example.slice(0, 40) + "..." : example}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
