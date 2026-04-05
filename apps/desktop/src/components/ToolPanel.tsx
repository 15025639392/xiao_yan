import { useState, useEffect } from "react";
import type {
  ToolInfo,
  ToolsListResponse,
  ToolExecutionResult,
  ToolHistoryEntry,
  ToolsStatusResponse,
  DirectoryEntry,
  SearchResult,
  FileReadResult,
} from "../lib/api";
import {
  executeTool,
  fetchTools,
  fetchToolHistory,
  clearToolHistory,
  fetchToolsStatus,
  listDirectory,
  readFile,
  searchFiles,
} from "../lib/api";

type TabType = "execute" | "tools" | "files" | "history" | "status";

// ══════════════════════════════════════════════
// 主面板组件
// ══════════════════════════════════════════════

export function ToolPanel() {
  const [activeTab, setActiveTab] = useState<TabType>("execute");
  const [tools, setTools] = useState<ToolsListResponse | null>(null);
  const [status, setStatus] = useState<ToolsStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);

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

        {/* 统计徽章 */}
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

      {/* 标签导航 */}
      <nav className="tool-tabs">
        {([
          ["execute", "⚡ 执行", "运行工具命令"],
          ["tools", "📋 工具", "浏览可用工具"],
          ["files", "📁 文件", "文件浏览与搜索"],
          ["history", "📜 历史", "执行记录"],
          ["status", "📊 状态", "系统统计"],
        ] as [TabType, string, string][]).map(([key, icon_label, hint]) => (
          <button
            key={key}
            type="button"
            className={`tool-tab ${activeTab === key ? "tool-tab--active" : ""}`}
            onClick={() => setActiveTab(key)}
            title={hint}
          >
            {icon_label}
          </button>
        ))}
      </nav>

      {/* 内容区 */}
      <div className="tool-panel__body">
        {activeTab === "execute" && <ExecuteTab tools={tools} onExecuted={() => fetchToolHistory().catch(() => {})} />}
        {activeTab === "tools" && <ToolsBrowseTab tools={tools} />}
        {activeTab === "files" && <FilesTab />}
        {activeTab === "history" && <HistoryTab />}
        {activeTab === "status" && <StatusTab status={status} onRefresh={() => fetchToolsStatus().then(setStatus).catch(() => {})} />}
      </div>
    </section>
  );
}

// ══════════════════════════════════════════════
// Tab: 命令执行
// ══════════════════════════════════════════════

function ExecuteTab({ tools, onExecuted }: { tools: ToolsListResponse | null; onExecuted?: () => void }) {
  const [command, setCommand] = useState("");
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<ToolExecutionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 常用快捷命令
  const quickCommands = [
    "pwd",
    "ls -la",
    'echo "hello"',
    "git log --oneline -5",
    "python --version",
    "date",
    "whoami",
    "uname -a",
  ];

  async function handleExecute() {
    const cmd = command.trim();
    if (!cmd) return;

    setExecuting(true);
    setError(null);
    setResult(null);

    try {
      const res = await executeTool(cmd);
      setResult(res);
      onExecuted?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "执行失败");
    } finally {
      setExecuting(false);
    }
  }

  async function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleExecute();
    }
  }

  return (
    <div className="execute-tab">
      {/* 输入区域 */}
      <div className="execute-input-group">
        <code className="execute-prompt">$</code>
        <textarea
          className="execute-textarea"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入要执行的命令... (Enter 执行, Shift+Enter 换行)"
          disabled={executing}
          rows={2}
          spellCheck={false}
        />
        <button
          type="button"
          className="btn btn--primary btn--sm"
          onClick={handleExecute}
          disabled={executing || !command.trim()}
          style={{ alignSelf: "flex-end" }}
        >
          {executing ? "⏳ 执行中..." : "▶ 执行"}
        </button>
      </div>

      {/* 快捷命令 */}
      <div className="quick-commands">
        <span className="quick-commands__label">快捷:</span>
        {quickCommands.map((cmd) => (
          <button
            key={cmd}
            type="button"
            className="quick-cmd-btn"
            onClick={() => setCommand(cmd)}
            title={`使用: ${cmd}`}
          >
            {cmd.split(" ")[0]}
          </button>
        ))}
      </div>

      {/* 错误提示 */}
      {error ? (
        <div className="tool-error">{error}</div>
      ) : null}

      {/* 结果展示 */}
      {result ? (
        <div className={`execute-result execute-result--${result.success ? "success" : "error"}`}>
          <div className="execute-result__header">
            <span className="execute-result__badge">
              {result.timed_out ? "TIMEOUT" : result.success ? `EXIT ${result.exit_code ?? 0}` : `ERR ${result.exit_code ?? -1}`}
            </span>
            <span className="execute-result__duration">
              {(result.duration_seconds ?? 0).toFixed(2)}s
            </span>
            {result.tool_name ? (
              <span className="execute-result__tool">{result.tool_name}</span>
            ) : null}
          </div>

          {/* stdout */}
          {result.output ? (
            <pre className="execute-result__output">{result.output}</pre>
          ) : (
            result.error ? (
              <pre className="execute-result__error-msg">{result.error}</pre>
            ) : (
              <p style={{ color: "var(--text-tertiary)", fontStyle: "italic" }}>无输出</p>
            )
          )}

          {/* stderr */}
          {result.stderr ? (
            <pre className="execute-result__stderr">{result.stderr}</pre>
          ) : null}

          {/* 截断提示 */}
          {result.truncated ? (
            <p className="execute-result__trunc-note">输出已截断 (显示前 2MB)</p>
          ) : null}

          {/* 完整命令 */}
          <p className="execute-result__full-cmd">
            $ {result.command}
          </p>
        </div>
      ) : null}

      {/* 空状态 */}
      {!result && !error && !executing ? (
        <p style={{
          textAlign: "center", color: "var(--text-tertiary)",
          padding: "var(--space-8) var(--space-4)",
          fontStyle: "italic",
        }}>
          输入命令后按 Enter 执行。所有命令都经过安全沙箱校验。
        </p>
      ) : null}
    </div>
  );
}

// ══════════════════════════════════════════════
// Tab: 工具浏览
// ══════════════════════════════════════════════

function ToolsBrowseTab({ tools }: { tools: ToolsListResponse | null }) {
  const [filter, setFilter] = useState("");

  if (!tools) {
    return <p style={{ color: "var(--text-tertiary)" }}>加载中...</p>;
  }

  const allTools: Array<{ info: ToolInfo; category: string }> = [];
  for (const [cat, items] of Object.entries(tools.by_category)) {
    for (const item of items) {
      allTools.push({ info: item, category: cat });
    }
  }

  const filtered = filter
    ? allTools.filter(
        (t) =>
          t.info.name.includes(filter) ||
          t.info.description.includes(filter) ||
          t.category.includes(filter)
      )
    : allTools;

  const levelColor: Record<string, string> = {
    safe: "var(--success)",
    restricted: "var(--info)",
    dangerous: "var(--warning)",
    blocked: "var(--danger)",
  };

  const levelLabel: Record<string, string> = {
    safe: "安全",
    restricted: "受限",
    dangerous: "危险",
    blocked: "禁止",
  };

  return (
    <div className="tools-browse-tab">
      {/* 搜索过滤 */}
      <input
        type="text"
        className="tools-search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="搜索工具..."
      />

      {/* 分类列表 */}
      {Object.entries(tools.by_category).map(([category, categoryTools]) => {
        const visibleItems = filter
          ? categoryTools.filter(
              (t) =>
                t.name.includes(filter) ||
                t.description.includes(filter)
            )
          : categoryTools;
        if (visibleItems.length === 0) return null;

        return (
          <div key={category} className="tools-category">
            <h4 className="tools-category__title">
              {getCategoryIcon(category)}
              {getCategoryName(category)}
              <span className="tools-category__count">{visibleItems.length}</span>
            </h4>
            <div className="tools-grid">
              {visibleItems.map((tool) => (
                <div key={tool.name} className="tool-card">
                  <div className="tool-card__header">
                    <code className="tool-card__name">{tool.name}</code>
                    <span
                      className="tool-card__level"
                      style={{ color: levelColor[tool.safety_level] || "inherit" }}
                      title={levelLabel[tool.safety_level]}
                    >
                      {levelLabel[tool.safety_level]}
                    </span>
                  </div>
                  <p className="tool-card__desc">{tool.description}</p>
                  {tool.examples.length > 0 ? (
                    <div className="tool-card__examples">
                      {tool.examples.slice(0, 3).map((ex) => (
                        <button
                          key={ex}
                          type="button"
                          className="tool-example-btn"
                          title="点击填入执行框"
                          // 这里可以后续接入全局事件总线来切换 tab 并填充命令
                        >
                          {ex.length > 40 ? ex.slice(0, 40) + "..." : ex}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function getCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    info: "ℹ️",
    filesystem: "📂",
    dev: "💻",
    system: "⚙️",
    network: "🌐",
  };
  return icons[category] || "🔧";
}

function getCategoryName(category: string): string {
  const names: Record<string, string> = {
    info: "信息查询",
    filesystem: "文件系统",
    dev: "开发工具",
    system: "系统操作",
    network: "网络工具",
  };
  return names[category] || category;
}

// ══════════════════════════════════════════════
// Tab: 文件操作
// ══════════════════════════════════════════════

function FilesTab() {
  const [currentPath, setCurrentPath] = useState(".");
  const [entries, setEntries] = useState<DirectoryEntry[] | null>(null);
  const [fileContent, setFileContent] = useState<FileReadResult | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadDir(path: string) {
    setLoading(true);
    try {
      const res = await listDirectory(path);
      setEntries(res.entries);
      setCurrentPath(path);
      setFileContent(null);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { loadDir("."); }, []);

  async function handleReadFile(relPath: string) {
    setLoading(true);
    try {
      const res = await readFile(relPath);
      setFileContent(res);
    } catch {}
    setLoading(false);
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const res = await searchFiles(searchQuery, currentPath);
      setSearchResult(res);
    } catch {}
    setLoading(false);
  }

  function navigateUp() {
    const parts = currentPath.replace(/\/$/, "").split("/");
    parts.pop();
    loadDir(parts.join("/") || ".");
  }

  function handleClickEntry(entry: DirectoryEntry) {
    if (entry.type === "dir") {
      loadDir(`${currentPath}/${entry.path}`);
    } else {
      handleReadFile(`${currentPath}/${entry.path}`);
    }
  }

  return (
    <div className="files-tab">
      {/* 路径导航栏 */}
      <div className="files-nav">
        <button
          type="button"
          className="btn btn--sm"
          onClick={navigateUp}
          disabled={currentPath === "."}
        >
          ↑ ..
        </button>
        <code className="files-current-path">{currentPath}</code>
        <button
          type="button"
          className="btn btn--sm"
          onClick={() => loadDir(currentPath)}
        >
          🔄 刷新
        </button>
      </div>

      {/* 搜索栏 */}
      <div className="files-search-bar">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="搜索文件内容..."
          className="files-search-input"
        />
        <button
          type="button"
          className="btn btn--primary btn--sm"
          onClick={handleSearch}
          disabled={!searchQuery.trim()}
        >
          搜索
        </button>
      </div>

      {/* 文件内容查看器（当选中文件时） */}
      {fileContent ? (
        <div className="file-viewer">
          <div className="file-viewer__header">
            <code>{fileContent.path}</code>
            <button
              type="button"
              className="btn btn--sm"
              onClick={() => setFileContent(null)}
            >
              ✕ 关闭
            </button>
          </div>
          <div className="file-viewer__meta">
            {fileContent.line_count} 行 · {formatBytes(fileContent.size_bytes)}
            {fileContent.truncated ? " · 已截断" : ""}
            {fileContent.mime_type ? ` · ${fileContent.mime_type}` : ""}
          </div>
          <pre className="file-viewer__content">{fileContent.content}</pre>
        </div>
      ) : searchResult ? (
        /* 搜索结果 */
        <div className="search-results">
          <h4>搜索 "{searchQuery}" — {searchResult.total_matches} 条匹配 ({searchResult.search_duration_seconds}s)</h4>
          {searchResult.matches.length > 0 ? (
            <table className="search-results-table">
              <thead>
                <tr>
                  <th>文件</th>
                  <th>行号</th>
                  <th>内容</th>
                </tr>
              </thead>
              <tbody>
                {searchResult.matches.map((m, i) => (
                  <tr key={i}>
                    <td>
                      <button
                        type="button"
                        className="search-file-link"
                        onClick={() => handleReadFile(m.file)}
                      >
                        {m.file}
                      </button>
                    </td>
                    <td>{m.line}</td>
                    <td className="search-context"><code>{m.context}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ color: "var(--text-tertiary)" }}>未找到匹配结果</p>
          )}
          <button type="button" className="btn btn--sm" onClick={() => setSearchResult(null)}>
            返回目录
          </button>
        </div>
      ) : (
        /* 目录列表 */
        <div className="dir-list">
          {loading ? (
            <p style={{ color: "var(--text-tertiary)" }}>加载中...</p>
          ) : entries ? (
            entries.length > 0 ? (
              entries.map((entry) => (
                <div
                  key={`${entry.type}-${entry.path}`}
                  className={`dir-entry dir-entry--${entry.type}`}
                  onClick={() => handleClickEntry(entry)}
                >
                  <span className="dir-entry__icon">
                    {entry.type === "dir" ? "📁" : entry.type === "symlink" ? "🔗" : "📄"}
                  </span>
                  <span className="dir-entry__name">{entry.name}</span>
                  <span className="dir-entry__size">
                    {entry.type === "file" ? formatBytes(entry.size_bytes) : ""}
                  </span>
                </div>
              ))
            ) : (
              <p style={{ color: "var(--text-tertiary)" }}>空目录</p>
            )
          ) : null}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════
// Tab: 执行历史
// ══════════════════════════════════════════════

function HistoryTab() {
  const [history, setHistory] = useState<ToolHistoryEntry[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetchToolHistory(50)
      .then((res) => {
        setHistory(res.entries);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  async function handleClear() {
    await clearToolHistory();
    setHistory([]);
  }

  if (!loaded) {
    return <p style={{ color: "var(--text-tertiary)" }}>加载历史...</p>;
  }

  return (
    <div className="history-tab">
      <div className="history-tab__actions">
        <span className="history-count">{history.length} 条记录</span>
        {history.length > 0 ? (
          <button type="button" className="btn btn--sm" onClick={handleClear}>
            🗑 清空历史
          </button>
        ) : null}
      </div>

      {history.length > 0 ? (
        <div className="history-list">
          {history.map((entry, i) => (
            <div
              key={entry.id || i}
              className={`history-item history-item--${entry.success ? "ok" : "fail"}`}
            >
              <div className="history-item__main">
                <code className="history-item__cmd">{entry.command}</code>
                <span className="history-item__time">{entry.created_at?.slice(11, 19)}</span>
              </div>
              <div className="history-item__meta">
                <span className={`history-badge history-badge--${entry.success ? "ok" : "fail"}`}>
                  {entry.exit_code === -1 ? "ERR" : `exit ${entry.exit_code}`}
                </span>
                <span>{entry.duration_seconds?.toFixed(1) ?? "?"}s</span>
                {entry.tool_name ? (
                  <span className="history-tool-name">{entry.tool_name}</span>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ color: "var(--text-tertiary)", padding: "var(--space-6)", textAlign: "center" }}>
          暂无执行记录
        </p>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════
// Tab: 系统状态
// ══════════════════════════════════════════════

function StatusTab({ status, onRefresh }: { status: ToolsStatusResponse | null; onRefresh?: () => void }) {
  if (!status) {
    return <p style={{ color: "var(--text-tertiary)" }}>加载中...</p>;
  }

  const stat = status.statistics;
  const rateColor =
    stat.success_rate >= 0.8
      ? "var(--success)"
      : stat.success_rate >= 0.5
        ? "var(--warning)"
        : "var(--danger)";

  return (
    <div className="status-tab">
      {/* 核心统计 */}
      <div className="status-grid">
        <div className="status-metric">
          <p className="status-metric__value">{stat.total_executions}</p>
          <p className="status-metric__label">总执行次数</p>
        </div>
        <div className="status-metric">
          <p className="status-metric__value" style={{ color: rateColor }}>{Math.round(stat.success_rate * 100)}%</p>
          <p className="status-metric__label">成功率</p>
        </div>
        <div className="status-metric">
          <p className="status-metric__value" style={{ color: stat.failed_count > 0 ? "var(--danger)" : undefined }}>{stat.failed_count}</p>
          <p className="status-metric__label">失败</p>
        </div>
        <div className="status-metric">
          <p className="status-metric__value" style={{ color: stat.timeout_count > 0 ? "var(--warning)" : undefined }}>{stat.timeout_count}</p>
          <p className="status-metric__label">超时</p>
        </div>
      </div>

      {/* 配置信息 */}
      <div className="status-config">
        <h4>配置</h4>
        <dl className="status-dl">
          <dt>安全级别</dt><dd>{status.safety_filter}</dd>
          <dt>可用命令数</dt><dd>{status.allowed_command_count} 个</dd>
          <dt>工作目录</dt><dd><code>{status.working_directory}</code></dd>
          <dt>超时限制</dt><dd>{status.timeout_seconds}s</dd>
          <dt>沙箱</dt><dd>{status.sandbox_enabled ? "已启用" : "未启用"}</dd>
          <dt>历史记录</dt><dd>{status.history_size} 条</dd>
        </dl>
      </div>

      {/* 最近使用的工具 */}
      {status.recently_used_tools.length > 0 ? (
        <div className="status-recent-tools">
          <h4>最近使用的工具</h4>
          <div className="recent-tools-list">
            {status.recently_used_tools.map(([name, count]) => (
              <div key={name} className="recent-tool-item">
                <code>{name}</code>
                <span className="recent-tool-count">{count} 次</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <button type="button" className="btn btn--sm" onClick={onRefresh} style={{ marginTop: "var(--space-4)" }}>
        🔄 刷新状态
      </button>
    </div>
  );
}

// ══════════════════════════════════════════════
// 辅助函数
// ══════════════════════════════════════════════

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}
