import Card from '../ui/Card';
import ProgressBar from '../ui/ProgressBar';
import { StatusBadge } from '../ui/Badge';
import type { Competency } from '../../types';
import './CompetencyCard.css';

const TONE_BY_STATUS: Record<Competency['status'], 'primary' | 'warning' | 'danger' | 'success'> = {
  NOT_STARTED: 'primary',
  NEEDS_PRACTICE: 'danger',
  DEVELOPING: 'warning',
  DEMONSTRATED: 'success',
};

export default function CompetencyCard({ competency }: { competency: Competency }) {
  return (
    <Card padding="md" className="competency-card">
      <div className="competency-card__top">
        <h3 className="competency-card__name">{competency.name}</h3>
        <StatusBadge status={competency.status} />
      </div>
      <ProgressBar value={competency.progress} tone={TONE_BY_STATUS[competency.status]} showPercent={false} />
    </Card>
  );
}
