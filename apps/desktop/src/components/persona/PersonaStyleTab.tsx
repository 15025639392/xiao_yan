import type { ExpressionHabit, FormalLevel } from "../../lib/api";
import {
  EXPRESSION_HABIT_OPTIONS,
  FORMAL_LEVEL_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
} from "./personaConstants";

type PersonaStyleTabProps = {
  formalLevel: FormalLevel;
  expressionHabit: ExpressionHabit;
  responseLength: string;
  verbalTics: string;
  saving: boolean;
  onFormalLevelChange: (value: FormalLevel) => void;
  onExpressionHabitChange: (value: ExpressionHabit) => void;
  onResponseLengthChange: (value: string) => void;
  onVerbalTicsChange: (value: string) => void;
  onSave: () => void;
};

export function PersonaStyleTab({
  formalLevel,
  expressionHabit,
  responseLength,
  verbalTics,
  saving,
  onFormalLevelChange,
  onExpressionHabitChange,
  onResponseLengthChange,
  onVerbalTicsChange,
  onSave,
}: PersonaStyleTabProps) {
  return (
    <div className="persona-form">
      <div className="persona-form__section">
        <h4 className="persona-form__section-title">语言风格</h4>

        <div className="persona-form__field">
          <label className="persona-form__label">正式程度</label>
          <div className="style-options">
            {FORMAL_LEVEL_OPTIONS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`style-option ${formalLevel === value ? "style-option--active" : ""}`}
                onClick={() => onFormalLevelChange(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="persona-form__field">
          <label className="persona-form__label">表达习惯</label>
          <div className="style-options">
            {EXPRESSION_HABIT_OPTIONS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`style-option ${expressionHabit === value ? "style-option--active" : ""}`}
                onClick={() => onExpressionHabitChange(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="persona-form__field">
          <label className="persona-form__label">回复长度</label>
          <div className="style-options">
            {RESPONSE_LENGTH_OPTIONS.map((value) => (
              <button
                key={value}
                type="button"
                className={`style-option ${responseLength === value ? "style-option--active" : ""}`}
                onClick={() => onResponseLengthChange(value)}
              >
                {{ short: "简洁", mixed: "适中", long: "详细" }[value]}
              </button>
            ))}
          </div>
        </div>

        <div className="persona-form__field">
          <label className="persona-form__label" htmlFor="wb-persona-tics">
            口头禅
            <span className="persona-form__hint">常用语，用逗号或顿号分隔</span>
          </label>
          <input
            id="wb-persona-tics"
            type="text"
            className="persona-form__input"
            value={verbalTics}
            onChange={(e) => onVerbalTicsChange(e.target.value)}
            placeholder="说实话、我觉得、怎么说呢"
          />
        </div>
      </div>

      <div className="persona-form__actions">
        <button type="button" className="btn btn--primary" onClick={onSave} disabled={saving}>
          {saving ? "保存中..." : "保存风格"}
        </button>
      </div>
    </div>
  );
}

