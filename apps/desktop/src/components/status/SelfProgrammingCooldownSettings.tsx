import { useEffect, useState } from "react";
import {
  fetchSelfProgrammingConfig,
  updateSelfProgrammingConfig,
  type SelfProgrammingRuntimeConfig,
} from "../../lib/api";

export function SelfProgrammingCooldownSettings() {
  const [config, setConfig] = useState<SelfProgrammingRuntimeConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  useEffect(() => {
    fetchSelfProgrammingConfig()
      .then(setConfig)
      .catch((e) => setError(e instanceof Error ? e.message : "加载冷却配置失败"));
  }, []);

  async function save() {
    if (!config || saving) return;
    setSaving(true);
    setError(null);
    setOk(null);
    try {
      const updated = await updateSelfProgrammingConfig(config);
      setConfig(updated);
      setOk("冷却配置已保存");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (!config) {
    return null;
  }

  return (
    <section className="si-section" style={{ marginTop: "var(--space-3)" }}>
      <h4 className="si-section__title">自我编程冷却设置（分钟）</h4>
      <div className="si-grid">
        <label className="si-field">
          <span className="si-field__label">硬故障冷却</span>
          <input
            type="number"
            min={1}
            value={config.hard_failure_cooldown_minutes}
            onChange={(event) =>
              setConfig({
                ...config,
                hard_failure_cooldown_minutes: Number(event.target.value || 1),
              })
            }
          />
        </label>
        <label className="si-field">
          <span className="si-field__label">主动优化冷却</span>
          <input
            type="number"
            min={1}
            value={config.proactive_cooldown_minutes}
            onChange={(event) =>
              setConfig({
                ...config,
                proactive_cooldown_minutes: Number(event.target.value || 1),
              })
            }
          />
        </label>
      </div>
      <button type="button" className="btn btn--ghost" disabled={saving} onClick={save}>
        保存冷却配置
      </button>
      {ok ? <p className="si-section__text">{ok}</p> : null}
      {error ? <p className="si-section__text" style={{ color: "var(--danger)" }}>{error}</p> : null}
    </section>
  );
}
