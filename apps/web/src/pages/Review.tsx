import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { StatusBadge } from '../components/ui/Badge';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { useApp } from '../state/AppContext';
import { getReview, getStudent, completeReview } from '../data/mockApi';
import type { AsyncState, ReviewData } from '../types';
import './Review.css';

export default function Review() {
  const navigate = useNavigate();
  const { student, setStudent, markReviewComplete } = useApp();
  const [state, setState] = useState<AsyncState<ReviewData>>({ status: 'loading' });
  const [continuing, setContinuing] = useState(false);

  async function load() {
    setState({ status: 'loading' });
    try {
      const s = student ?? (await getStudent());
      if (!student) setStudent(s);
      const activeCompetency = s.competencies.find((c) => c.status === 'DEVELOPING') ?? s.competencies[0]!;
      const review = await getReview(activeCompetency.id);
      setState({ status: 'success', data: review });
    } catch (err) {
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not load your evidence.',
      });
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleContinue() {
    setContinuing(true);
    try {
      const s = student ?? (await getStudent());
      const updated = await completeReview(s);
      setStudent(updated);
      markReviewComplete();
      navigate('/progress/competency-profile');
    } finally {
      setContinuing(false);
    }
  }

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="page-narrow">
        <LoadingState message="Gathering your evidence…" />
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

  const review = state.data;

  return (
    <div className="page-narrow review">
      <div className="review__eyebrow">Apply & Review</div>
      <h1 className="review__title">Your Evidence</h1>
      <p className="muted review__subtitle">
        Instead of a single score, here's what you've actually demonstrated for{' '}
        <strong>{review.competencyName}</strong>.
      </p>

      <Card padding="lg" className="review__card">
        <ul className="review__list">
          {review.evidence.map((item) => (
            <li key={item.id} className={`review__item ${item.met ? 'review__item--met' : 'review__item--unmet'}`}>
              <span className="review__icon" aria-hidden="true">
                {item.met ? '✓' : '✗'}
              </span>
              {item.label}
            </li>
          ))}
        </ul>

        <div className="review__status">
          <span className="review__status-label">Competency Status</span>
          <StatusBadge status={review.status} />
        </div>
      </Card>

      <div className="review__actions">
        <Button size="lg" onClick={handleContinue} loading={continuing}>
          Continue to Progress
        </Button>
      </div>
    </div>
  );
}
