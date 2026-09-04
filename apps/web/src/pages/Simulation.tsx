import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { useApp } from '../state/AppContext';
import { runSimulation } from '../data/mockApi';
import type { SimulationResult } from '../types';
import './Simulation.css';

type Phase = 'ready' | 'running' | 'done' | 'error';

// Thresholds shown to the student as the task requirements. They mirror the
// backend's TelemetryThresholds defaults (overshoot < 10%, settling < 2s, SSE < 0.02).
const REQUIREMENTS = [
  { id: 'overshoot', label: 'Overshoot', limit: '< 10 %' },
  { id: 'settling', label: 'Settling Time', limit: '< 2.0 s' },
  { id: 'sse', label: 'Steady-State Error', limit: '< 0.02' },
  { id: 'stable', label: 'Stability', limit: 'stable' },
];

export default function Simulation() {
  const navigate = useNavigate();
  const { student, markSimulationComplete } = useApp();
  const [phase, setPhase] = useState<Phase>('ready');
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState('');

  // NEW: gain sliders. Defaults chosen to make a decent starting point
  // (not the optimal solution — students still need to reason about them).
  const [kp, setKp] = useState(2.0);
  const [ki, setKi] = useState(0.5);
  const [kd, setKd] = useState(0.1);

  const activeCompetency =
    student?.competencies.find((c) => c.status === 'DEVELOPING') ?? student?.competencies[0];

  async function handleRun() {
    setPhase('running');
    try {
      const r = await runSimulation({
        kp,
        ki,
        kd,
        competencyId: activeCompetency?.id ?? 'pid-tuning',
      });
      setResult(r);
      setPhase('done');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'The simulation could not be run.');
      setPhase('error');
    }
  }

  function handleContinue() {
    markSimulationComplete();
    navigate('/apply-review/review');
  }

  // Helper: did the latest run meet each individual requirement?
  function metricMet(id: string): boolean {
    if (!result) return false;
    if (id === 'overshoot') return result.overshoot < 10;
    if (id === 'settling') return result.settlingTime < 2;
    if (id === 'sse') return result.steadyStateError < 0.02;
    if (id === 'stable') return result.stable;
    return false;
  }

  return (
    <div className="page-narrow simulation">
      <div className="simulation__eyebrow">Apply & Review</div>
      <h1 className="simulation__title">PID Simulation</h1>
      <p className="muted simulation__subtitle">
        Tune your controller for <strong>{activeCompetency?.name ?? 'PID Tuning'}</strong> and run it
        against the plant model. The simulator measures overshoot, settling time, rise time, and
        steady-state error — objectively, with no AI in the loop.
      </p>

      {/* NEW: Plant diagram showing the feedback loop. */}
      <Card padding="md" className="simulation__diagram-card">
        <svg
          className="simulation__diagram"
          viewBox="0 0 600 120"
          role="img"
          aria-label="Closed-loop PID control feedback diagram"
        >
          {/* Reference */}
          <text x="10" y="40" fontSize="12" fontWeight="700" fill="currentColor">
            Reference
          </text>
          <circle cx="60" cy="60" r="6" fill="var(--color-primary)" />
          <line x1="60" y1="60" x2="120" y2="60" stroke="currentColor" strokeWidth="2" />

          {/* Summing junction */}
          <circle cx="130" cy="60" r="10" fill="none" stroke="currentColor" strokeWidth="2" />
          <text x="125" y="65" fontSize="14" fill="currentColor">+</text>
          <text x="125" y="45" fontSize="14" fill="currentColor">−</text>

          {/* PID block */}
          <line x1="140" y1="60" x2="200" y2="60" stroke="currentColor" strokeWidth="2" />
          <rect x="200" y="40" width="100" height="40" rx="6" fill="var(--color-primary-light)" stroke="currentColor" strokeWidth="2" />
          <text x="225" y="65" fontSize="14" fontWeight="700" fill="currentColor">PID</text>

          {/* Plant block */}
          <line x1="300" y1="60" x2="360" y2="60" stroke="currentColor" strokeWidth="2" />
          <rect x="360" y="40" width="100" height="40" rx="6" fill="var(--color-primary-light)" stroke="currentColor" strokeWidth="2" />
          <text x="385" y="65" fontSize="14" fontWeight="700" fill="currentColor">Plant</text>

          {/* Output */}
          <line x1="460" y1="60" x2="560" y2="60" stroke="currentColor" strokeWidth="2" />
          <text x="510" y="40" fontSize="12" fontWeight="700" fill="currentColor">
            Output
          </text>
          <circle cx="560" cy="60" r="4" fill="var(--color-primary)" />

          {/* Feedback loop */}
          <path d="M 510 60 L 510 100 L 130 100 L 130 70" stroke="currentColor" strokeWidth="2" fill="none" />
          <text x="300" y="118" fontSize="11" fill="var(--color-text-faint)">feedback</text>
        </svg>
      </Card>

      {/* NEW: Kp / Ki / Kd sliders. */}
      <Card padding="lg" className="simulation__gains-card">
        <h2 className="simulation__section-title">Controller Gains</h2>
        <div className="simulation__sliders">
          <label className="simulation__slider">
            <span className="simulation__slider-label">
              <strong>Kp</strong> — Proportional
            </span>
            <input
              type="range"
              min="0"
              max="15"
              step="0.1"
              value={kp}
              onChange={(e) => setKp(parseFloat(e.target.value))}
              disabled={phase === 'running'}
            />
            <span className="simulation__slider-value">{kp.toFixed(2)}</span>
          </label>
          <label className="simulation__slider">
            <span className="simulation__slider-label">
              <strong>Ki</strong> — Integral
            </span>
            <input
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={ki}
              onChange={(e) => setKi(parseFloat(e.target.value))}
              disabled={phase === 'running'}
            />
            <span className="simulation__slider-value">{ki.toFixed(2)}</span>
          </label>
          <label className="simulation__slider">
            <span className="simulation__slider-label">
              <strong>Kd</strong> — Derivative
            </span>
            <input
              type="range"
              min="0"
              max="5"
              step="0.05"
              value={kd}
              onChange={(e) => setKd(parseFloat(e.target.value))}
              disabled={phase === 'running'}
            />
            <span className="simulation__slider-value">{kd.toFixed(2)}</span>
          </label>
        </div>
      </Card>

      {/* Requirements the simulator evaluates against. */}
      <Card padding="md" className="simulation__requirements-card">
        <h3 className="simulation__subsection-title">Task Requirements</h3>
        <ul className="simulation__requirements">
          {REQUIREMENTS.map((r) => (
            <li key={r.id} className={phase === 'done' && result ? (metricMet(r.id) ? 'met' : 'missed') : ''}>
              <span>{r.label}</span>
              <span className="simulation__req-limit">{r.limit}</span>
              {phase === 'done' && result && (
                <Badge tone={metricMet(r.id) ? 'success' : 'danger'}>
                  {metricMet(r.id) ? '✓' : '✗'}
                </Badge>
              )}
            </li>
          ))}
        </ul>
      </Card>

      <Card padding="lg" className="simulation__card">
        {phase === 'ready' && (
          <div className="simulation__ready">
            <div className="simulation__icon">⚙️</div>
            <p className="muted">
              Run with Kp = <strong>{kp.toFixed(2)}</strong>, Ki = <strong>{ki.toFixed(2)}</strong>, Kd ={' '}
              <strong>{kd.toFixed(2)}</strong>.
            </p>
            <Button size="lg" onClick={handleRun}>
              Run Simulation
            </Button>
          </div>
        )}

        {phase === 'running' && <LoadingState message="Running simulation…" />}

        {phase === 'error' && <ErrorState message={errorMessage} onRetry={handleRun} />}

        {phase === 'done' && result && (
          <div className="simulation__result">
            <div className="simulation__status">
              <Badge tone={result.result === 'PASS' ? 'success' : 'danger'}>
                {result.result} · {result.stable ? 'Stable' : 'Unstable'}
              </Badge>
              {result.misconception && (
                <Badge tone="warning">Detected: {result.misconception.replace(/_/g, ' ').toLowerCase()}</Badge>
              )}
              <span className="muted">Attempt #{result.attempt}</span>
            </div>

            <div className="simulation__metrics">
              <div className="simulation__metric">
                <span className="simulation__metric-label">Overshoot</span>
                <span className="simulation__metric-value">{result.overshoot.toFixed(2)}%</span>
              </div>
              <div className="simulation__metric">
                <span className="simulation__metric-label">Settling Time</span>
                <span className="simulation__metric-value">{result.settlingTime.toFixed(2)}s</span>
              </div>
              <div className="simulation__metric">
                <span className="simulation__metric-label">Rise Time</span>
                <span className="simulation__metric-value">{result.riseTime.toFixed(2)}s</span>
              </div>
              <div className="simulation__metric">
                <span className="simulation__metric-label">Steady-State Error</span>
                <span className="simulation__metric-value">{result.steadyStateError.toFixed(4)}</span>
              </div>
            </div>

            {result.result === 'FAIL' && result.misconception && (
              <div className="simulation__failure-hint">
                <strong>Failed.</strong>{' '}
                <Button variant="ghost" size="sm" onClick={() => navigate('/my-learning/remediation')}>
                  Get Remediation Plan
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>

      {phase === 'done' && (
        <div className="simulation__actions">
          <Button variant="ghost" onClick={handleRun}>
            Run Again
          </Button>
          <Button onClick={handleContinue}>Continue to Review</Button>
        </div>
      )}
    </div>
  );
}
