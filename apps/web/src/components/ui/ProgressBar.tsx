import './ProgressBar.css';

interface ProgressBarProps {
  value: number; // 0-100
  label?: string;
  showPercent?: boolean;
  tone?: 'primary' | 'accent' | 'success' | 'warning' | 'danger';
  size?: 'sm' | 'md';
}

export default function ProgressBar({
  value,
  label,
  showPercent = true,
  tone = 'primary',
  size = 'md',
}: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="progress">
      {(label || showPercent) && (
        <div className="progress__meta">
          {label && <span className="progress__label">{label}</span>}
          {showPercent && <span className="progress__percent">{clamped}%</span>}
        </div>
      )}
      <div
        className={`progress__track progress__track--${size}`}
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? `${clamped}% complete`}
      >
        <div
          className={`progress__fill progress__fill--${tone}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
