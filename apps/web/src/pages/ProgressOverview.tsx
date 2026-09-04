import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import ProgressBar from '../components/ui/ProgressBar';
import CompetencyCard from '../components/domain/CompetencyCard';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { getStudent } from '../data/mockApi';
import { useApp } from '../state/AppContext';
import type { AsyncState, Student } from '../types';
import './ProgressOverview.css';

export default function ProgressOverview() {
  const navigate = useNavigate();
  const { student, setStudent } = useApp();
  const [state, setState] = useState<AsyncState<Student>>({ status: 'loading' });

  async function load() {
    setState({ status: 'loading' });
    try {
      const s = student ?? (await getStudent());
      if (!student) setStudent(s);
      setState({ status: 'success', data: s });
    } catch (err) {
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not load your progress.',
      });
    }
  }

  useEffect(() => {
    load();
    // Reload whenever the persisted student changes (e.g. after completing Review),
    // so progress reflects the latest evidence-driven update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [student]);

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="page">
        <LoadingState message="Loading your progress…" />
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="page">
        <ErrorState message={state.message} onRetry={load} />
      </div>
    );
  }

  const s = state.data;

  return (
    <div className="page">
      <div className="progress-overview__header">
        <h1 className="progress-overview__title">Your Progress</h1>
        <p className="muted">{s.course.code} — {s.course.title}</p>
      </div>

      <Card padding="lg" className="progress-overview__summary">
        <ProgressBar value={s.overallProgress} label="Overall Course Progress" tone="primary" size="md" />
      </Card>

      <h2 className="progress-overview__subheading">Competencies</h2>
      <div className="grid grid-2 progress-overview__grid">
        {s.competencies.map((c) => (
          <CompetencyCard key={c.id} competency={c} />
        ))}
      </div>

      <div className="progress-overview__cta">
        <Button variant="secondary" onClick={() => navigate('/progress/competency-profile')}>
          View Full Competency Profile
        </Button>
      </div>
    </div>
  );
}
