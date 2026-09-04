import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/layout/Sidebar';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { useApp } from '../state/AppContext';
import { getLesson, getStudent } from '../data/mockApi';
import type { AsyncState, LessonSection, Student } from '../types';
import './Learning.css';

export default function Learning() {
  const navigate = useNavigate();
  const { student, setStudent, markLearningComplete } = useApp();
  const [state, setState] = useState<AsyncState<{ student: Student; sections: LessonSection[] }>>({
    status: 'loading',
  });

  async function load() {
    setState({ status: 'loading' });
    try {
      const s = student ?? (await getStudent());
      const activeCompetency = s.competencies.find((c) => c.status === 'DEVELOPING') ?? s.competencies[0]!;
      const sections = await getLesson(activeCompetency.id);
      if (!student) setStudent(s);
      setState({ status: 'success', data: { student: s, sections } });
    } catch (err) {
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not load this lesson.',
      });
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="page">
        <LoadingState message="Loading your lesson…" />
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

  const { student: s, sections } = state.data;
  const activeCompetency = s.competencies.find((c) => c.status === 'DEVELOPING') ?? s.competencies[0]!;

  return (
    <div className="page learning">
      <div className="learning__eyebrow">{s.course.code}</div>
      <h1 className="learning__title">{activeCompetency.name}</h1>

      <div className="learning__layout">
        <Sidebar
          courseLabel={`${s.course.code} — ${s.course.title}`}
          competencies={s.competencies}
          activeCompetencyId={activeCompetency.id}
        />

        <div className="learning__content">
          <Card padding="lg">
            {sections.map((sec) => (
              <div key={sec.id} className="learning__section">
                <h2 className="learning__section-heading">{sec.heading}</h2>
                <p className="learning__section-body muted">{sec.body}</p>
              </div>
            ))}
          </Card>

          <div className="learning__actions">
            <Button variant="secondary" onClick={() => navigate('/my-learning/ai-coach')}>
              Ask AI Coach
            </Button>
            <Button
              onClick={() => {
                markLearningComplete();
                navigate('/my-learning/practice');
              }}
            >
              Continue to Practice
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
