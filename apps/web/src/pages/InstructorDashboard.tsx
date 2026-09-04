import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import {
  getInstructorClassSummary,
  getInstructorCompetencyAggregate,
  getInstructorStudents,
} from '../data/mockApi';
import type {
  InstructorClassSummary,
  InstructorCompetencyAggregate,
  InstructorStudentSummary,
} from '../types';
import './InstructorDashboard.css';

type Phase = 'loading' | 'success' | 'error';

export default function InstructorDashboard() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [summary, setSummary] = useState<InstructorClassSummary | null>(null);
  const [aggregate, setAggregate] = useState<InstructorCompetencyAggregate[]>([]);
  const [students, setStudents] = useState<InstructorStudentSummary[]>([]);

  async function loadData() {
    setPhase('loading');
    try {
      const [s, a, stu] = await Promise.all([
        getInstructorClassSummary(),
        getInstructorCompetencyAggregate(),
        getInstructorStudents(),
      ]);
      setSummary(s);
      setAggregate(a);
      setStudents(stu);
      setPhase('success');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Could not load instructor data.');
      setPhase('error');
    }
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [s, a, stu] = await Promise.all([
          getInstructorClassSummary(),
          getInstructorCompetencyAggregate(),
          getInstructorStudents(),
        ]);
        if (cancelled) return;
        setSummary(s);
        setAggregate(a);
        setStudents(stu);
        setPhase('success');
      } catch (err) {
        if (cancelled) return;
        setErrorMessage(err instanceof Error ? err.message : 'Could not load instructor data.');
        setPhase('error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page-wide instructor-dashboard">
      <div className="instructor-dashboard__eyebrow">Instructor</div>
      <h1 className="instructor-dashboard__title">Class Dashboard</h1>
      <p className="muted instructor-dashboard__subtitle">
        Aggregate view of every student's competency status — no LLM, just evidence-driven numbers.
      </p>

      {phase === 'loading' && <LoadingState message="Loading class data…" />}
      {phase === 'error' && <ErrorState message={errorMessage} onRetry={loadData} />}

      {phase === 'success' && summary && (
        <>
          {/* Top-level class stats */}
          <div className="instructor-dashboard__stats">
            <Card padding="md">
              <span className="instructor-dashboard__stat-label">Total Students</span>
              <span className="instructor-dashboard__stat-value">{summary.totalStudents}</span>
            </Card>
            <Card padding="md">
              <span className="instructor-dashboard__stat-label">Avg. Progress</span>
              <span className="instructor-dashboard__stat-value">
                {summary.averageOverallProgress}%
              </span>
            </Card>
            <Card padding="md">
              <span className="instructor-dashboard__stat-label">Demonstrated All</span>
              <span className="instructor-dashboard__stat-value">
                {summary.studentsDemonstratedAll}
              </span>
            </Card>
            <Card padding="md">
              <span className="instructor-dashboard__stat-label">With Failures</span>
              <span className="instructor-dashboard__stat-value instructor-dashboard__stat-value--warning">
                {summary.studentsWithFailures}
              </span>
            </Card>
          </div>

          {/* Per-competency aggregate */}
          <Card padding="lg" className="instructor-dashboard__aggregate-card">
            <h2 className="instructor-dashboard__section-title">Competency Aggregate</h2>
            <p className="muted instructor-dashboard__section-hint">
              For each competency, how many students are at each status.
            </p>
            <div className="instructor-dashboard__aggregate-table">
              <div className="instructor-dashboard__aggregate-row instructor-dashboard__aggregate-row--head">
                <span>Competency</span>
                <span>Demonstrated</span>
                <span>Developing</span>
                <span>Needs Practice</span>
                <span>Not Started</span>
              </div>
              {aggregate.map((c) => (
                <div key={c.competencyId} className="instructor-dashboard__aggregate-row">
                  <span className="instructor-dashboard__aggregate-name">{c.competencyName}</span>
                  <span className="instructor-dashboard__aggregate-count">{c.demonstrated}</span>
                  <span className="instructor-dashboard__aggregate-count">{c.developing}</span>
                  <span className="instructor-dashboard__aggregate-count">{c.needsPractice}</span>
                  <span className="instructor-dashboard__aggregate-count">{c.notStarted}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Roster */}
          <Card padding="lg" className="instructor-dashboard__roster-card">
            <h2 className="instructor-dashboard__section-title">Student Roster</h2>
            <p className="muted instructor-dashboard__section-hint">
              Click any student to view their evidence timeline.
            </p>
            <ul className="instructor-dashboard__roster">
              {students.map((s) => (
                <li
                  key={s.studentId}
                  className="instructor-dashboard__roster-row"
                  onClick={() => navigate(`/instructor/students/${s.studentId}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      navigate(`/instructor/students/${s.studentId}`);
                    }
                  }}
                >
                  <div className="instructor-dashboard__roster-main">
                    <span className="instructor-dashboard__roster-name">{s.displayName}</span>
                    <span className="muted instructor-dashboard__roster-id">{s.studentId}</span>
                  </div>
                  <div className="instructor-dashboard__roster-progress">
                    <Badge tone={s.overallProgress >= 70 ? 'success' : s.overallProgress >= 40 ? 'warning' : 'danger'}>
                      {s.overallProgress}%
                    </Badge>
                  </div>
                  <div className="instructor-dashboard__roster-competencies">
                    {s.competencies.map((c) => {
                      const tone =
                        c.status === 'DEMONSTRATED'
                          ? 'success'
                          : c.status === 'DEVELOPING'
                          ? 'warning'
                          : c.status === 'NEEDS_PRACTICE'
                          ? 'danger'
                          : 'neutral';
                      const label =
                        c.status === 'DEMONSTRATED'
                          ? '✓'
                          : c.status === 'DEVELOPING'
                          ? '◐'
                          : c.status === 'NEEDS_PRACTICE'
                          ? '!'
                          : '○';
                      return (
                        <span
                          key={c.id}
                          className={`instructor-dashboard__roster-dot instructor-dashboard__roster-dot--${tone.toLowerCase()}`}
                          title={`${c.name}: ${c.status}`}
                        >
                          {label}
                        </span>
                      );
                    })}
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          <div className="instructor-dashboard__actions">
            <Button variant="ghost" onClick={() => navigate('/home')}>
              Back to Home
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
