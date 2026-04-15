import { useEffect, useMemo, useState } from "react";
import type { ChatSkillEntry } from "../../lib/api";
import { fetchChatSkills } from "../../lib/api";
import {
  clearChatToolboxSelectedSkills,
  loadChatToolboxSelectedSkills,
  saveChatToolboxSelectedSkills,
} from "../../lib/chatToolboxPreferences";

export function SkillsManageTab() {
  const [skills, setSkills] = useState<ChatSkillEntry[]>([]);
  const [selectedSkillNames, setSelectedSkillNames] = useState<string[]>(() => loadChatToolboxSelectedSkills());
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setIsLoading(true);
    setError("");
    fetchChatSkills()
      .then((payload) => {
        const nextSkills = Array.isArray(payload.skills) ? payload.skills : [];
        setSkills(nextSkills);
        setSelectedSkillNames((prev) => {
          const available = new Set(nextSkills.map((item) => item.name));
          const normalized = prev.filter((name) => available.has(name));
          saveChatToolboxSelectedSkills(normalized);
          return normalized;
        });
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "加载 skills 失败");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const filteredSkills = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return skills;
    }
    return skills.filter((skill) => {
      const haystack = `${skill.name} ${skill.description ?? ""} ${skill.path}`.toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [query, skills]);

  const selectedSet = useMemo(() => new Set(selectedSkillNames), [selectedSkillNames]);

  function persistNextSelection(nextSelection: string[]) {
    setSelectedSkillNames(nextSelection);
    saveChatToolboxSelectedSkills(nextSelection);
  }

  function toggleSkillSelection(skillName: string) {
    const current = new Set(selectedSkillNames);
    if (current.has(skillName)) {
      current.delete(skillName);
    } else {
      current.add(skillName);
    }
    const next = skills
      .map((skill) => skill.name)
      .filter((name) => current.has(name));
    persistNextSelection(next);
  }

  function selectAllVisibleSkills() {
    const current = new Set(selectedSkillNames);
    for (const skill of filteredSkills) {
      current.add(skill.name);
    }
    const next = skills
      .map((skill) => skill.name)
      .filter((name) => current.has(name));
    persistNextSelection(next);
  }

  function clearAllSkills() {
    setSelectedSkillNames([]);
    clearChatToolboxSelectedSkills();
  }

  return (
    <div className="tool-skill-tab">
      <div className="tool-config-card">
        <div className="tool-config-card__header">
          <div>
            <h4>Skills 管理</h4>
            <p>统一管理会随 `/chat` 请求附带的技能工作流清单。</p>
          </div>
          <span className="tool-config-card__badge">已选择 {selectedSkillNames.length}</span>
        </div>

        <div className="tool-config-actions">
          <input
            className="tool-config-input"
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索 skill 名称、描述或路径"
          />
          <button type="button" className="tool-config-btn" onClick={selectAllVisibleSkills} disabled={isLoading || filteredSkills.length === 0}>
            选择筛选结果
          </button>
          <button type="button" className="tool-config-btn tool-config-btn--danger" onClick={clearAllSkills} disabled={isLoading || selectedSkillNames.length === 0}>
            清空选择
          </button>
        </div>

        {isLoading ? <p className="tool-config-hint">加载 skills...</p> : null}
        {error ? <p className="tool-config-error">{error}</p> : null}
        {!isLoading && !error && skills.length === 0 ? <p className="tool-config-hint">未发现可用 skills。</p> : null}

        {!isLoading && !error && filteredSkills.length > 0 ? (
          <div className="tool-skill-list">
            {filteredSkills.map((skill) => (
              <label key={skill.name} className="tool-skill-item">
                <input
                  type="checkbox"
                  checked={selectedSet.has(skill.name)}
                  onChange={() => toggleSkillSelection(skill.name)}
                />
                <div className="tool-skill-item__content">
                  <div className="tool-skill-item__head">
                    <strong>{skill.name}</strong>
                    {skill.trigger_prefixes.length > 0 ? (
                      <span className="tool-skill-item__trigger">触发词: {skill.trigger_prefixes.join(" / ")}</span>
                    ) : null}
                  </div>
                  {skill.description ? <p>{skill.description}</p> : null}
                  <code>{skill.path}</code>
                </div>
              </label>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
