import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Badge, StatusBadge } from '../components/ui/Badge';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/StateViews';
import { getInstructorStudentDetail } from '../data/mockApi';
import type { InstructorStudentDetail, EvidenceEvent } from '../types';
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

export default function InstructorStudentDetailPage() {
  const { studentId } = useParams<{ studentId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<InstructorStudentDetail | null>(null);
  const [phase, setPhase] = useState<'loading' | 'success' | 'error' | 'empty'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  async function load() {
    setPhase('loading');
    if (!studentId) {
      setPhase('empty');
      return;
    }
    try {
      const d = await getInstructorStudentDetail(studentId);
      setDetail(d);
      setPhase('success');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Could not load student detail.');
      setPhase('error');
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentId]);

  return (
    <div className="page-narrow instructor-student-detail">
      <div className="instructor-student-detail__eyebrow">Instructor</div>
      <h1 className="instructor-student-detail__title">
        {detail?.displayName ?? 'Student Detail'}
      </h1>
      <p className="muted instructor-student-detail__subtitle">
        Per-competency status + chronological evidence timeline. No LLM in this view — just
        objective evidence the simulation/transfer engines produced.
      </p>

      {phase === 'loading' && <LoadingState message="Loading student detail…" />}
      {phase === 'error' && <ErrorState message={errorMessage} onRetry={load} />}
      {phase === 'empty' && (
        <EmptyState
          title="No student selected"
          message="Go back to the instructor dashboard and pick a student."
          action={<Button onClick={() => navigate('/instructor')}>Back to Dashboard</Button>}
        />
      )}

      {phase === 'success' && detail && (
        <>
          <Card padding="md" className="instructor-student-detail__summary-card">
            <div className="instructor-student-detail__summary-row">
              <span className="instructor-student-detail__summary-label">Student ID</span>
              <span className="instructor-student-detail__summary-value">{detail.studentId}</span>
            </div>
            <div className="instructor-student-detail__summary-row">
              <span className="instructor-student-detail__summary-label">Course</span>
              <span className="instructor-student-detail__summary-value">
                {detail.courseCode} — {detail.courseTitle}
              </span>
            </div>
            <div className="instructor-student-detail__summary-row">
              <span className="instructor-student-detail__summary-label">Overall Progress</span>
              <span className="instructor-student-detail__summary-value">
                <Badge tone={detail.overallProgress >= 70 ? 'success' : detail.overallProgress >= 40 ? 'warning' : 'danger'}>
                  {detail.overallProgress}%
                </Badge>
              </span>
            </div>
          </Card>

          <Card padding="lg" className="instructor-student-detail__competencies-card">
            <h2 className="instructor-student-detail__section-title">Competency Status</h2>
            <ul className="instructor-student-detail__competencies">
              {detail.competencies.map((c) => (
                <li key={c.id} className="instructor-student-detail__competency-row">
                  <span className="instructor-student-detail__competency-name">{c.name}</span>
                  <StatusBadge status={c.status} />
                </li>
              ))}
            </ul>
          </Card>

          <Card padding="lg" className="instructor-student-detail__timeline-card">
            <h2 className="instructor-student-detail__section-title">Evidence Timeline</h2>
            <p className="muted instructor-student-detail__section-hint">
              Newest first — chronological feed of every event that produced evidence.
            </p>
            {detail.evidenceTimeline.length === 0 ? (
              <EmptyState
                title="No evidence yet"
                message="Once this student runs a simulation, takes a diagnostic, or talks to the coach, events will appear here in order."
              />
            ) : (
              <ul className="evidence-timeline">
                {detail.evidenceTimeline.map((e, i) => (
                  <EventRow key={`${e.timestamp}-${i}`} event={e} />
                ))}
              </ul>
            )}
          </Card>

          <div className="instructor-student-detail__actions">
            <Button variant="ghost" onClick={() => navigate('/instructor')}>
              Back to Dashboard
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
