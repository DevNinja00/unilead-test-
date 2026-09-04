import type { ReactNode } from 'react';
import type { CompetencyStatus } from '../../types';
import './Badge.css';

type BadgeTone = 'success' | 'warning' | 'danger' | 'neutral' | 'primary' | 'accent';

interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
}

export function Badge({ children, tone = 'neutral' }: BadgeProps) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

const STATUS_CONFIG: Record<CompetencyStatus, { label: string; tone: BadgeTone }> = {
  NOT_STARTED: { label: 'Not Started', tone: 'neutral' },
  NEEDS_PRACTICE: { label: 'Needs Practice', tone: 'danger' },
  DEVELOPING: { label: 'Developing', tone: 'warning' },
  DEMONSTRATED: { label: 'Demonstrated', tone: 'success' },
};

export function StatusBadge({ status }: { status: CompetencyStatus }) {
  const config = STATUS_CONFIG[status];
  return <Badge tone={config.tone}>{config.label}</Badge>;
}
