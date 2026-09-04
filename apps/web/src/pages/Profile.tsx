import { useEffect, useState } from 'react';
import Card from '../components/ui/Card';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import ProgressBar from '../components/ui/ProgressBar';
import { getStudent } from '../data/mockApi';
import { useApp } from '../state/AppContext';
import type { AsyncState, Student } from '../types';
import './Profile.css';

export default function Profile() {
  const { student: cachedStudent, setStudent } = useApp();
  const [state, setState] = useState<AsyncState<Student>>({ status: 'loading' });

  async function load() {
    setState({ status: 'loading' });
    try {
      const s = cachedStudent ?? (await getStudent());
      if (!cachedStudent) setStudent(s);
      setState({ status: 'success', data: s });
    } catch (err) {
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not load your profile.',
      });
    }
  }

  useEffect(() => {
    load();
    // Reload whenever the persisted student changes (e.g. after completing Review).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cachedStudent]);

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="page-narrow">
        <LoadingState message="Loading your profile…" />
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="page-narrow">
        <ErrorState message={state.message} onRetry={load} />
      </div>
    );
  }

  const s = state.data;
  const initials = s.name
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className="page-narrow profile">
      <h1 className="profile__title">Profile</h1>

      <Card padding="lg" className="profile__card">
        <div className="profile__avatar">{initials}</div>
        <div>
          <h2 className="profile__name">{s.name}</h2>
          <p className="muted">{s.email}</p>
        </div>
      </Card>

      <Card padding="lg" className="profile__card">
        <h3 className="profile__section-title">Course</h3>
        <p className="muted">{s.course.code} — {s.course.title}</p>
      </Card>

      <Card padding="lg" className="profile__card">
        <h3 className="profile__section-title">Overall Progress</h3>
        <ProgressBar value={s.overallProgress} showPercent tone="primary" />
      </Card>
    </div>
  );
}
