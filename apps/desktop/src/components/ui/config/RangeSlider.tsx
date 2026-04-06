type RangeSliderProps = {
  min: number;
  max: number;
  step?: number;
  value: number;
  disabled?: boolean;
  className?: string;
  onChange: (value: number) => void;
};

export function RangeSlider({
  min,
  max,
  step = 1,
  value,
  disabled = false,
  className,
  onChange,
}: RangeSliderProps) {
  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(event) => onChange(Number.parseInt(event.target.value, 10))}
      disabled={disabled}
      className={className}
    />
  );
}
