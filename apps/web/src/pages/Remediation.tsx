import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/StateViews';
import { useApp } from '../state/AppContext';
import { getRemediationPlan, getStudent } from '../data/mockApi';
import type { RemediationPlan } from '../types';
import './Remediation.css';

export default function Remediation() {
  const navigate = useNavigate();
  const { student, setStudent } = useApp();
  const [plan, setPlan] = useState<RemediationPlan | null>(null);
  const [phase, setPhase] = useState<'loading' | 'success' | 'error' | 'empty'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const activeCompetency =
    student?.competencies.find((c) => c.status === 'DEVELOPING' || c.status === 'NEEDS_PRACTICE') ??
    student?.competencies[0];

  async function loadPlan() {
    setPhase('loading');
    setErrorMessage('');
    try {
      if (!student) {
        const s = await getStudent();
        setStudent(s);
      }
      const competencyId = activeCompetency?.id ?? 'pid-tuning';
      const p = await getRemediationPlan(competencyId);
      setPlan(p);
      setPhase('success');
    } catch (err) {
      // 409 means there's no evidence to remediate — show EmptyState instead of error
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409') || msg.includes('No simulation evidence')) {
        setPhase('empty');
      } else {
        setErrorMessage(msg);
        setPhase('error');
      }
    }
  }

  useEffect(() => {
    loadPlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="page-narrow remediation">
      <div className="remediation__eyebrow">My Learning</div>
      <h1 className="remediation__title">Remediation Plan</h1>
      <p className="muted remediation__subtitle">
        Targeted micro-lesson for <strong>{activeCompetency?.name ?? 'your weak competency'}</strong>.
        Built from your recent failing simulation attempts — no LLM involved.
      </p>

      {phase === 'loading' && <LoadingState message="Building your remediation plan…" />}

      {phase === 'error' && <ErrorState message={errorMessage} onRetry={loadPlan} />}

      {phase === 'empty' && (
        <EmptyState
          title="No remediation needed yet"
          message="Run a simulation first. If you fail it, the engine will build a targeted micro-lesson based on your misconception."
          action={
            <Button onClick={() => navigate('/apply-review/simulation')}>Go to Simulation</Button>
          }
        />
      )}

      {phase === 'success' && plan && (
        <>
          <Card padding="lg" className="remediation__summary-card">
            <div className="remediation__summary-row">
              <span className="remediation__summary-label">Detected misconception</span>
              <span className="remediation__summary-value">
                {plan.detectedMisconception ? (
                  <Badge tone="warning">
                    {plan.detectedMisconception.replace(/_/g, ' ').toLowerCase()}
                  </Badge>
                ) : (
                  <span className="muted">none</span>
                )}
              </span>
            </div>
            <div className="remediation__summary-row">
              <span className="remediation__summary-label">Recommended action</span>
              <span className="remediation__summary-value">
                <Badge tone="primary">{plan.recommendedAction.replace(/_/g, ' ').toLowerCase()}</Badge>
              </span>
            </div>
            <div className="remediation__summary-row">
              <span className="remediation__summary-label">Recent failures</span>
              <span className="remediation__summary-value">
                {plan.consecutiveFailures} consecutive / {plan.totalAttempts} total attempts
              </span>
            </div>
            {plan.summaryText && (
              <p className="remediation__summary-text">{plan.summaryText}</p>
            )}
          </Card>

          <Card padding="lg" className="remediation__focus-card">
            <h2 className="remediation__section-title">Conceptual Focus</h2>
            <p className="remediation__focus-text">{plan.conceptualFocus}</p>
          </Card>

          <Card padding="lg" className="remediation__question-card">
            <h2 className="remediation__section-title">Guided Question</h2>
            <p className="remediation__question-text">{plan.guidedQuestion}</p>
            <p className="muted remediation__question-hint">
              Think about it before moving on — the coach will not give you the answer directly.
            </p>
          </Card>

          <Card padding="lg" className="remediation__steps-card">
            <h2 className="remediation__section-title">Micro-Lesson Steps</h2>
            <ol className="remediation__steps">
              {plan.remediationSteps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </Card>

          <div className="remediation__actions">
            <Button variant="ghost" onClick={() => navigate('/apply-review/simulation')}>
              Retry Simulation
            </Button>
            <Button
              variant="ghost"
              onClick={() =>
                navigate('/my-learning/ai-coach', { state: { mode: 'REMEDIATE' } })
              }
            >
              Ask Coach to Remediate
            </Button>
            <Button onClick={() => navigate('/apply-review/review')}>Continue to Review</Button>
          </div>
        </>
      )}
    </div>
  );
}
