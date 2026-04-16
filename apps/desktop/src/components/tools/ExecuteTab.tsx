import { useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import type { ToolExecutionResult, ToolsListResponse } from "../../lib/api";
import { executeTool } from "../../lib/api";
import { Button, Textarea } from "../ui";

type ExecuteTabProps = {
  tools: ToolsListResponse | null;
  onExecuted?: () => void;
};

const QUICK_COMMANDS = [
  "pwd",
  "ls -la",
  'echo "hello"',
  "git log --oneline -5",
  "python --version",
  "date",
  "whoami",
  "uname -a",
];

export function ExecuteTab({ tools, onExecuted }: ExecuteTabProps) {
  const [command, setCommand] = useState("");
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<ToolExecutionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExecute() {
    const trimmed = command.trim();
    if (!trimmed) return;

    setExecuting(true);
    setError(null);
    setResult(null);

    try {
      const res = await executeTool(trimmed);
      setResult(res);
      onExecuted?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "执行失败");
    } finally {
      setExecuting(false);
    }
  }

  function handleKeyDown(e: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleExecute();
    }
  }

  return (
    <div className="execute-tab">
      <div className="execute-input-group">
        <code className="execute-prompt">$</code>
        <Textarea
          className="execute-textarea"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入要执行的命令... (Enter 执行, Shift+Enter 换行)"
          disabled={executing}
          rows={2}
          spellCheck={false}
        />
        <Button
          type="button"
          variant="default"
          size="sm"
          onClick={() => void handleExecute()}
          disabled={executing || !command.trim()}
          style={{ alignSelf: "flex-end" }}
        >
          {executing ? "⏳ 执行中..." : "▶ 执行"}
        </Button>
      </div>

      <div className="quick-commands">
        <span className="quick-commands__label">快捷:</span>
        {QUICK_COMMANDS.map((quickCommand) => (
          <button
            key={quickCommand}
            type="button"
            className="quick-cmd-btn"
            onClick={() => setCommand(quickCommand)}
            title={`使用: ${quickCommand}`}
          >
            {quickCommand.split(" ")[0]}
          </button>
        ))}
      </div>

      {error ? <div className="tool-error">{error}</div> : null}

      {result ? (
        <div className={`execute-result execute-result--${result.success ? "success" : "error"}`}>
          <div className="execute-result__header">
            <span className="execute-result__badge">
              {result.timed_out ? "TIMEOUT" : result.success ? `EXIT ${result.exit_code ?? 0}` : `ERR ${result.exit_code ?? -1}`}
            </span>
            <span className="execute-result__duration">{(result.duration_seconds ?? 0).toFixed(2)}s</span>
            {result.tool_name ? <span className="execute-result__tool">{result.tool_name}</span> : null}
          </div>

          {result.output ? (
            <pre className="execute-result__output">{result.output}</pre>
          ) : result.error ? (
            <pre className="execute-result__error-msg">{result.error}</pre>
          ) : (
            <p style={{ color: "var(--text-tertiary)", fontStyle: "italic" }}>无输出</p>
          )}

          {result.stderr ? <pre className="execute-result__stderr">{result.stderr}</pre> : null}
          {result.truncated ? <p className="execute-result__trunc-note">输出已截断 (显示前 2MB)</p> : null}
          <p className="execute-result__full-cmd">$ {result.command}</p>
        </div>
      ) : null}

      {!result && !error && !executing ? (
        <p
          style={{
            textAlign: "center",
            color: "var(--text-tertiary)",
            padding: "var(--space-8) var(--space-4)",
            fontStyle: "italic",
          }}
        >
          输入命令后按 Enter 执行。所有命令都经过安全沙箱校验。
        </p>
      ) : null}
    </div>
  );
}
