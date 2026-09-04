import { useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Badge, StatusBadge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/StateViews';
import { useApp } from '../state/AppContext';
import './DiagnosticResults.css';

// Human-readable labels for each misconception tag returned by the backend.
const MISCONCEPTION_LABELS: Record<string, string> = {
  feedback_purpose_misunderstood: 'Misunderstands the purpose of feedback',
  derivative_role_misunderstood: 'Confuses which term responds to error rate',
  kp_overshoot_relationship_misunderstood: 'Misjudges how Kp affects overshoot',
  tuning_objective_misunderstood: 'Misunderstands the tuning objective',
  rise_time_definition_misunderstood: 'Misremembers the rise-time definition',
};

export default function DiagnosticResults() {
  const navigate = useNavigate();
  const { diagnosticResults } = useApp();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  if (!diagnosticResults) {
    return (
      <div className="page-narrow">
        <EmptyState
          icon="🧭"
          title="No diagnostic results yet"
          message="Take the diagnostic first to see your competency profile."
          action={
            <Button onClick={() => navigate('/my-learning/diagnostic')}>Start Diagnostic</Button>
          }
        />
      </div>
    );
  }

  const anyMisconceptions = diagnosticResults.some((r) => r.misconceptions && r.misconceptions.length > 0);

  return (
    <div className="page-narrow diagnostic-results">
      <div className="diagnostic-results__header">
        <h1 className="diagnostic-results__title">Your Competency Profile</h1>
        <p className="muted">
          Here's where you stand today. This shapes what we recommend you learn next.
        </p>
      </div>

      <Card padding="lg">
        <ul className="diagnostic-results__list">
          {diagnosticResults.map((r) => {
            const acc = Math.round((r.accuracy ?? 0) * 100);
            return (
              <li key={r.competencyId} className="diagnostic-results__row">
                <div className="diagnostic-results__row-main">
                  <span className="diagnostic-results__name">{r.competencyName}</span>
                  <span className="diagnostic-results__accuracy muted">Accuracy: {acc}%</span>
                </div>
                <div className="diagnostic-results__row-side">
                  <StatusBadge status={r.status} />
                </div>
                {/* NEW: show misconceptions when present */}
                {r.misconceptions && r.misconceptions.length > 0 && (
                  <ul className="diagnostic-results__misconceptions">
                    {r.misconceptions.map((m) => (
                      <li key={m}>
                        <Badge tone="warning">
                          {MISCONCEPTION_LABELS[m] ?? m.replace(/_/g, ' ')}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </Card>

      {anyMisconceptions && (
        <div className="diagnostic-results__hint">
          <p className="muted">
            Some misconceptions were detected. The AI Coach will adjust its strategy to target them
            automatically — or you can request a Remediation plan after running a simulation.
          </p>
        </div>
      )}

      <div className="diagnostic-results__cta">
        <Button size="lg" onClick={() => navigate('/my-learning/learning')}>
          Continue to Recommended Learning
        </Button>
      </div>
    </div>
  );
}
