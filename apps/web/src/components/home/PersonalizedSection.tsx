import { useNavigate } from 'react-router-dom';
import Card from '../ui/Card';
import Button from '../ui/Button';
import ProgressBar from '../ui/ProgressBar';
import { LoadingState, ErrorState } from '../ui/StateViews';
import type { AsyncState, Recommendation, Student } from '../../types';
import './PersonalizedSection.css';

interface PersonalizedSectionProps {
  state: AsyncState<{ student: Student; recommendation: Recommendation }>;
  onRetry: () => void;
}

export default function PersonalizedSection({ state, onRetry }: PersonalizedSectionProps) {
  return (
    <section className="personalized">
      <div className="personalized__inner">
        <h2 className="personalized__title">Your Learning Journey</h2>

        {(state.status === 'loading' || state.status === 'idle') && (
          <Card padding="lg">
            <LoadingState message="Loading your progress…" />
          </Card>
        )}

        {state.status === 'error' && (
          <Card padding="lg">
            <ErrorState message={state.message} onRetry={onRetry} />
          </Card>
        )}

        {state.status === 'success' && (
          <PersonalizedContent student={state.data.student} recommendation={state.data.recommendation} />
        )}
      </div>
    </section>
  );
}

function PersonalizedContent({
  student,
  recommendation,
}: {
  student: Student;
  recommendation: Recommendation;
}) {
  const navigate = useNavigate();
  const currentCompetency =
    student.competencies.find((c) => c.status === 'DEVELOPING') ?? student.competencies[0]!;

  return (
    <Card padding="lg" className="personalized__card">
      <div className="personalized__top">
        <div>
          <span className="personalized__course-code">{student.course.code}</span>
          <h3 className="personalized__course-title">{student.course.title}</h3>
        </div>
        <div className="personalized__progress-figure">
          <span className="personalized__progress-number">{student.overallProgress}%</span>
          <span className="muted personalized__progress-label">Progress</span>
        </div>
      </div>

      <ProgressBar value={student.overallProgress} showPercent={false} tone="primary" />

      <div className="personalized__grid">
        <div className="personalized__field">
          <span className="personalized__field-label">Current Focus</span>
          <span className="personalized__field-value">{currentCompetency.name}</span>
        </div>
        <div className="personalized__field">
          <span className="personalized__field-label">Recommended Next Step</span>
          <span className="personalized__field-value">{recommendation.title}</span>
        </div>
      </div>

      <p className="personalized__reason">
        <span className="personalized__reason-label">Reason: </span>
        {recommendation.reason}
      </p>

      <Button size="lg" onClick={() => navigate(recommendation.href)}>
        Continue Learning →
      </Button>
    </Card>
  );
}
