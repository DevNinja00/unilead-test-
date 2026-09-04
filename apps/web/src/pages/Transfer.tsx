import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { useApp } from '../state/AppContext';
import { getStudent, getTransferScenario, submitTransferResponse } from '../data/mockApi';
import type { TransferScenario, TransferEvaluation } from '../types';
import './Transfer.css';

const SCENARIO_OPTIONS = [
  { id: 'industrial_oven', label: 'Industrial Oven (thermal)' },
  { id: 'water_tank_level', label: 'Water Tank Level (fluid)' },
  { id: 'quadrotor_pitch', label: 'Quadrotor Pitch (aerospace)' },
];

export default function Transfer() {
  const navigate = useNavigate();
  const { student, setStudent } = useApp();
  const [scenario, setScenario] = useState<TransferScenario | null>(null);
  const [phase, setPhase] = useState<'loading' | 'success' | 'error' | 'submitting' | 'evaluated'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [responseText, setResponseText] = useState('');
  const [evaluation, setEvaluation] = useState<TransferEvaluation | null>(null);
  const [scenarioId, setScenarioId] = useState('industrial_oven');

  const activeCompetency =
    student?.competencies.find((c) => c.status === 'DEVELOPING' || c.status === 'DEMONSTRATED') ??
    student?.competencies[0];

  async function loadScenario(sid: string = scenarioId) {
    setPhase('loading');
    setErrorMessage('');
    setEvaluation(null);
    setResponseText('');
    try {
      if (!student) {
        const s = await getStudent();
        setStudent(s);
      }
      const sc = await getTransferScenario(activeCompetency?.id ?? 'pid-tuning', sid);
      setScenario(sc);
      setScenarioId(sc.scenarioId);
      setPhase('success');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Could not load the transfer scenario.');
      setPhase('error');
    }
  }

  useEffect(() => {
    loadScenario();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit() {
    if (!scenario || !responseText.trim()) return;
    setPhase('submitting');
    try {
      const evalResult = await submitTransferResponse(
        scenario.competencyId,
        responseText,
        scenario.scenarioId
      );
      setEvaluation(evalResult);
      setPhase('evaluated');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Could not evaluate your response.');
      setPhase('error');
    }
  }

  function handleScenarioChange(value: string) {
    setScenarioId(value);
    loadScenario(value);
  }

  return (
    <div className="page-narrow transfer">
      <div className="transfer__eyebrow">Apply & Review</div>
      <h1 className="transfer__title">Transfer Task</h1>
      <p className="muted transfer__subtitle">
        Apply what you've learned to a <strong>new plant</strong> in a different domain. No
        step-by-step solution is provided — you must reason from first principles.
      </p>

      {/* Scenario picker */}
      <Card padding="md" className="transfer__scenario-picker">
        <label className="transfer__picker-label" htmlFor="scenario-select">
          Plant scenario
        </label>
        <select
          id="scenario-select"
          className="transfer__picker-select"
          value={scenarioId}
          onChange={(e) => handleScenarioChange(e.target.value)}
          disabled={phase === 'loading' || phase === 'submitting'}
        >
          {SCENARIO_OPTIONS.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </Card>

      {phase === 'loading' && <LoadingState message="Loading transfer scenario…" />}
      {phase === 'error' && <ErrorState message={errorMessage} onRetry={() => loadScenario()} />}

      {scenario && (phase === 'success' || phase === 'submitting' || phase === 'evaluated') && (
        <>
          <Card padding="lg" className="transfer__challenge-card">
            <div className="transfer__header">
              <h2 className="transfer__scenario-title">{scenario.title}</h2>
              <Badge tone="primary">{scenario.domain}</Badge>
            </div>
            <p className="transfer__prompt">{scenario.prompt}</p>

            <div className="transfer__domain-grid">
              <div>
                <span className="transfer__domain-label">Error signal</span>
                <p>{scenario.errorSignalMeaning}</p>
              </div>
              <div>
                <span className="transfer__domain-label">Control output</span>
                <p>{scenario.controlOutputMeaning}</p>
              </div>
              <div>
                <span className="transfer__domain-label">System inertia</span>
                <p>{scenario.systemInertia}</p>
              </div>
              <div>
                <span className="transfer__domain-label">Conceptual challenge</span>
                <p>{scenario.conceptualChallenge}</p>
              </div>
            </div>
          </Card>

          {phase !== 'evaluated' && (
            <Card padding="lg" className="transfer__response-card">
              <h3 className="transfer__section-title">Your Response</h3>
              <textarea
                className="transfer__textarea"
                placeholder="Explain how Kp, Ki, and Kd each behave under this plant's physics, and how you would tune them to meet typical overshoot/settling-time requirements…"
                value={responseText}
                onChange={(e) => setResponseText(e.target.value)}
                rows={6}
                disabled={phase === 'submitting'}
              />
              <div className="transfer__actions">
                <Button
                  onClick={handleSubmit}
                  disabled={!responseText.trim() || phase === 'submitting'}
                >
                  {phase === 'submitting' ? 'Evaluating…' : 'Submit Response'}
                </Button>
              </div>
              <p className="muted transfer__hint">
                Evaluation is deterministic — no LLM involved. Your response must mention enough
                expert terms from the {scenario.domain} domain to pass.
              </p>
            </Card>
          )}

          {phase === 'evaluated' && evaluation && (
            <Card padding="lg" className="transfer__result-card">
              <div className="transfer__result-header">
                <Badge tone={evaluation.passed ? 'success' : 'danger'}>
                  {evaluation.passed ? 'TRANSFER DEMONSTRATED' : 'TRANSFER NOT YET'}
                </Badge>
                <span className="muted">
                  {evaluation.matchedCount} / ≥{evaluation.minRequired} expert terms matched
                </span>
              </div>
              <p className="transfer__feedback">{evaluation.feedback}</p>

              <div className="transfer__result-actions">
                {!evaluation.passed && (
                  <Button variant="ghost" onClick={() => loadScenario()}>
                    Try Different Plant
                  </Button>
                )}
                <Button onClick={() => navigate('/progress/competency-profile')}>
                  View Competency Profile
                </Button>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
