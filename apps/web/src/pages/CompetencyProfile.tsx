import { useEffect, useState } from 'react';
import Card from '../components/ui/Card';
import ProgressBar from '../components/ui/ProgressBar';
import { StatusBadge } from '../components/ui/Badge';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { getStudent } from '../data/mockApi';
import { useApp } from '../state/AppContext';
import type { AsyncState, Competency, Student } from '../types';
import './CompetencyProfile.css';

const TONE_BY_STATUS: Record<Competency['status'], 'primary' | 'warning' | 'danger' | 'success'> = {
  NOT_STARTED: 'primary',
  NEEDS_PRACTICE: 'danger',
  DEVELOPING: 'warning',
  DEMONSTRATED: 'success',
};

export default function CompetencyProfile() {
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
        message: err instanceof Error ? err.message : 'Could not load your competency profile.',
      });
    }
  }

  useEffect(() => {
    load();
    // Reload whenever the persisted student changes (e.g. after completing Review).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [student]);

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="page">
        <LoadingState message="Loading your competency profile…" />
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
  const demonstratedCount = s.competencies.filter((c) => c.status === 'DEMONSTRATED').length;

  return (
    <div className="page">
      <div className="competency-profile__header">
        <div>
          <h1 className="competency-profile__title">My Competencies</h1>
          <p className="muted">{s.course.code} — {s.course.title}</p>
        </div>
        <div className="competency-profile__summary">
          <span className="competency-profile__summary-count">
            {demonstratedCount}/{s.competencies.length}
          </span>
          <span className="muted">Demonstrated</span>
        </div>
      </div>

      <Card padding="lg">
        <ul className="competency-profile__list">
          {s.competencies.map((c) => (
            <li key={c.id} className="competency-profile__row">
              <div className="competency-profile__row-top">
                <span className="competency-profile__name">{c.name}</span>
                <StatusBadge status={c.status} />
              </div>
              <ProgressBar value={c.progress} showPercent={false} tone={TONE_BY_STATUS[c.status]} size="sm" />
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
