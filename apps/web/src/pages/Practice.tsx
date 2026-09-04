import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { getPracticeTask, submitPractice } from '../data/mockApi';
import { useApp } from '../state/AppContext';
import type { AsyncState, PracticeTask } from '../types';
import './Practice.css';

export default function Practice() {
  const navigate = useNavigate();
  const { student, markPracticeComplete } = useApp();
  const [state, setState] = useState<AsyncState<PracticeTask>>({ status: 'loading' });
  const [showHints, setShowHints] = useState(false);
  const [launching, setLaunching] = useState(false);

  async function load() {
    setState({ status: 'loading' });
    try {
      const competencyId =
        student?.competencies.find((c) => c.status === 'DEVELOPING')?.id ?? 'pid-reasoning';
      const task = await getPracticeTask(competencyId);
      setState({ status: 'success', data: task });
    } catch (err) {
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not load this practice task.',
      });
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="page-narrow">
        <LoadingState message="Loading your practice task…" />
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

  const task = state.data;

  async function handleLaunchSimulation() {
    setLaunching(true);
    try {
      await submitPractice(task.id);
      markPracticeComplete();
      navigate('/apply-review/simulation');
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div className="page-narrow practice">
      <div className="practice__eyebrow">Practice Task</div>
      <h1 className="practice__title">{task.title}</h1>

      <Card padding="lg" className="practice__section">
        <h3 className="practice__section-title">Objective</h3>
        <p className="muted">{task.objective}</p>
      </Card>

      <Card padding="lg" className="practice__section">
        <h3 className="practice__section-title">Requirements</h3>
        <ul className="practice__list">
          {task.requirements.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </Card>

      <Card padding="lg" className="practice__section">
        <div className="practice__hints-header">
          <h3 className="practice__section-title">Hints</h3>
          <Button variant="ghost" size="sm" onClick={() => setShowHints((h) => !h)}>
            {showHints ? 'Hide Hints' : 'Show Hints'}
          </Button>
        </div>
        {showHints && (
          <ul className="practice__list">
            {task.hints.map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ul>
        )}
      </Card>

      <div className="practice__actions">
        <Button variant="secondary" onClick={() => navigate('/my-learning/ai-coach')}>
          Ask AI Coach
        </Button>
        <Button onClick={handleLaunchSimulation} loading={launching}>
          Launch Simulation
        </Button>
      </div>
    </div>
  );
}
