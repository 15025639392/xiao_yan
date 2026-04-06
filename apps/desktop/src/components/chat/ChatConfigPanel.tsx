import type { AppConfig } from "../../lib/api";

type ChatConfigPanelProps = {
  config: AppConfig;
  isUpdating: boolean;
  error: string;
  onUpdate: (config: Partial<AppConfig>) => void;
  onClose: () => void;
};

export function ChatConfigPanel({ config, isUpdating, error, onUpdate, onClose }: ChatConfigPanelProps) {
  return (
    <div className="config-panel-overlay" onClick={onClose}>
      <div className="config-panel" onClick={(e) => e.stopPropagation()}>
        <div className="config-panel__header">
          <h3 className="config-panel__title">配置</h3>
          <button type="button" className="config-panel__close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="config-panel__body">
          <div className="config-panel__section">
            <label className="config-panel__label">聊天上下文限制</label>
            <p className="config-panel__description">
              每次聊天时携带的相关事件数量。值越小响应越快，但连贯性可能降低；值越大对话越连贯，但响应可能变慢。
            </p>
            <div className="config-panel__control">
              <input
                type="range"
                min="1"
                max="20"
                value={config.chat_context_limit}
                onChange={(e) => {
                  const value = parseInt(e.target.value, 10);
                  if (!isUpdating) {
                    onUpdate({ chat_context_limit: value });
                  }
                }}
                disabled={isUpdating}
                className="config-panel__slider"
              />
              <span className="config-panel__value">{config.chat_context_limit}</span>
            </div>
            <div className="config-panel__presets">
              <button
                type="button"
                className={`config-panel__preset ${config.chat_context_limit === 3 ? "config-panel__preset--active" : ""}`}
                onClick={() => !isUpdating && onUpdate({ chat_context_limit: 3 })}
                disabled={isUpdating}
              >
                保守 (3)
              </button>
              <button
                type="button"
                className={`config-panel__preset ${config.chat_context_limit === 6 ? "config-panel__preset--active" : ""}`}
                onClick={() => !isUpdating && onUpdate({ chat_context_limit: 6 })}
                disabled={isUpdating}
              >
                默认 (6)
              </button>
              <button
                type="button"
                className={`config-panel__preset ${config.chat_context_limit === 10 ? "config-panel__preset--active" : ""}`}
                onClick={() => !isUpdating && onUpdate({ chat_context_limit: 10 })}
                disabled={isUpdating}
              >
                开放 (10)
              </button>
            </div>
          </div>
        </div>

        {error ? <div className="config-panel__error">{error}</div> : null}

        <div className="config-panel__footer">
          <button type="button" className="config-panel__btn config-panel__btn--primary" onClick={onClose}>
            完成
          </button>
        </div>
      </div>
    </div>
  );
}

