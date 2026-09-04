import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/StateViews';
import { getMyEvidenceTimeline } from '../data/mockApi';
import type { EvidenceEvent } from '../types';
import './InstructorStudentDetail.css';

const EVENT_TYPE_LABELS: Record<string, string> = {
  diagnostic_submitted: 'Diagnostic submitted',
  simulation_run: 'Simulation run',
  remediation_completed: 'Remediation completed',
  transfer_evaluated: 'Transfer evaluated',
  coach_turn: 'Coach turn',
};

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function EventRow({ event }: { event: EvidenceEvent }) {
  const tone =
    event.result === 'PASS' ? 'success' : event.result === 'FAIL' ? 'danger' : 'neutral';
  const dotTone =
    event.result === 'PASS' ? 'success' : event.result === 'FAIL' ? 'danger' : 'neutral';
  return (
    <li className={`evidence-timeline__row evidence-timeline__row--${tone.toLowerCase()}`}>
      <span className={`evidence-timeline__dot evidence-timeline__dot--${dotTone}`} aria-hidden="true" />
      <div className="evidence-timeline__row-main">
        <div className="evidence-timeline__row-header">
          <span className="evidence-timeline__row-title">{event.title}</span>
          <span className="evidence-timeline__row-time">{formatTimestamp(event.timestamp)}</span>
        </div>
        <p className="evidence-timeline__row-detail">{event.detail}</p>
        <div className="evidence-timeline__row-meta">
          <Badge tone={tone}>{event.result}</Badge>
          <span className="muted">{EVENT_TYPE_LABELS[event.eventType] ?? event.eventType}</span>
          {event.competencyId && (
            <span className="muted evidence-timeline__row-comp">· {event.competencyId}</span>
          )}
        </div>
      </div>
    </li>
  );
}

export default function EvidenceTimeline() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<EvidenceEvent[]>([]);
  const [phase, setPhase] = useState<'loading' | 'success' | 'error' | 'empty'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  async function load() {
    setPhase('loading');
    try {
      const evs = await getMyEvidenceTimeline();
      setEvents(evs);
      setPhase(evs.length === 0 ? 'empty' : 'success');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Could not load the timeline.');
      setPhase('error');
    }
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const evs = await getMyEvidenceTimeline();
        if (cancelled) return;
        setEvents(evs);
        setPhase(evs.length === 0 ? 'empty' : 'success');
      } catch (err) {
        if (cancelled) return;
        setErrorMessage(err instanceof Error ? err.message : 'Could not load the timeline.');
        setPhase('error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page-narrow evidence-timeline-page">
      <div className="evidence-timeline-page__eyebrow">Apply & Review</div>
      <h1 className="evidence-timeline-page__title">Evidence Timeline</h1>
      <p className="muted evidence-timeline-page__subtitle">
        A chronological feed of every event that produced evidence for your profile. The
        simulation, transfer, diagnostic, and coach engines all write here — the timeline never
        invents events.
      </p>

      {phase === 'loading' && <LoadingState message="Loading your evidence timeline…" />}
      {phase === 'error' && <ErrorState message={errorMessage} onRetry={load} />}

      {phase === 'empty' && (
        <EmptyState
          title="No evidence yet"
          message="Once you run a simulation, take the diagnostic, or talk to the coach, events will appear here in chronological order."
          action={<Button onClick={() => navigate('/my-learning/diagnostic')}>Start Diagnostic</Button>}
        />
      )}

      {phase === 'success' && (
        <Card padding="lg" className="evidence-timeline-page__card">
          <ul className="evidence-timeline">
            {events.map((e, i) => (
              <EventRow key={`${e.timestamp}-${i}`} event={e} />
            ))}
          </ul>
        </Card>
      )}

      <div className="evidence-timeline-page__actions">
        <Button variant="ghost" onClick={() => navigate('/home')}>
          Back to Home
        </Button>
        <Button onClick={() => navigate('/progress/competency-profile')}>
          View Competency Profile
        </Button>
      </div>
    </div>
  );
}
