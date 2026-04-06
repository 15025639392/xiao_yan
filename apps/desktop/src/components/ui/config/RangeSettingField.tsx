import type { ReactNode } from "react";
import { RangeSlider } from "./RangeSlider";

type RangePreset = {
  label: string;
  value: number;
};

type RangeSettingFieldProps = {
  label: ReactNode;
  description?: ReactNode;
  min: number;
  max: number;
  step?: number;
  value: number;
  disabled?: boolean;
  presets?: RangePreset[];
  classNamePrefix?: string;
  onChange: (value: number) => void;
};

export function RangeSettingField({
  label,
  description,
  min,
  max,
  step = 1,
  value,
  disabled = false,
  presets = [],
  classNamePrefix = "config-panel",
  onChange,
}: RangeSettingFieldProps) {
  const rootClass = classNamePrefix;

  return (
    <div className={`${rootClass}__section`}>
      <label className={`${rootClass}__label`}>{label}</label>
      {description ? <p className={`${rootClass}__description`}>{description}</p> : null}

      <div className={`${rootClass}__control`}>
        <RangeSlider
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(next) => {
            if (!disabled) {
              onChange(next);
            }
          }}
          disabled={disabled}
          className={`${rootClass}__slider`}
        />
        <span className={`${rootClass}__value`}>{value}</span>
      </div>

      {presets.length > 0 ? (
        <div className={`${rootClass}__presets`}>
          {presets.map((preset) => {
            const presetClasses = [
              `${rootClass}__preset`,
              value === preset.value ? `${rootClass}__preset--active` : null,
            ]
              .filter(Boolean)
              .join(" ");

            return (
              <button
                key={`${preset.value}-${preset.label}`}
                type="button"
                className={presetClasses}
                onClick={() => {
                  if (!disabled) {
                    onChange(preset.value);
                  }
                }}
                disabled={disabled}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
