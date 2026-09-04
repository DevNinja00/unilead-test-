import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { ErrorState } from '../components/ui/StateViews';
import { useApp } from '../state/AppContext';
import { getStudent, sendCoachMessage } from '../data/mockApi';
import type { CoachMessage, CoachMode, CoachResponse } from '../types';
import './AICoach.css';

let idCounter = 0;
function nextId() {
  idCounter += 1;
  return `msg-${idCounter}`;
}

// All six coach modes the backend supports — mirrors
// ai_education.domain.enums.CoachMode.
const MODES: { value: CoachMode; label: string; description: string }[] = [
  { value: 'LEARN', label: 'Learn', description: 'Explain the concept from first principles.' },
  { value: 'HINT', label: 'Hint', description: 'Give a hint, not the answer.' },
  { value: 'PRACTICE', label: 'Practice', description: 'Guide me while I work through a task.' },
  { value: 'REFLECT', label: 'Reflect', description: 'Ask me to explain my reasoning back.' },
  { value: 'REMEDIATE', label: 'Remediate', description: 'Targeted micro-lesson for my weak spot.' },
  { value: 'TRANSFER', label: 'Transfer', description: 'Apply my skill to a new domain.' },
];

export default function AICoach() {
  const navigate = useNavigate();
  const { student, setStudent } = useApp();

  const activeCompetency =
    student?.competencies.find((c) => c.status === 'DEVELOPING') ?? student?.competencies[0];

  const [messages, setMessages] = useState<CoachMessage[]>([]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const [started, setStarted] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [selectedMode, setSelectedMode] = useState<CoachMode | null>(null);
  const [activeMode, setActiveMode] = useState<CoachMode>('LEARN');
  const [scaffolding, setScaffolding] = useState<'LOW' | 'MEDIUM' | 'HIGH' | null>(null);
  const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
  const [finished, setFinished] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function startConversation() {
    setStarted(true);
    setLoadError('');
    setThinking(true);
    try {
      if (!student) {
        const s = await getStudent();
        setStudent(s);
      }
      // The coach starts the conversation: a LEARN turn on the active competency.
      const reply = await sendCoachMessage({
        message: "Let's begin. What should I focus on?",
        mode: 'LEARN',
        competencyId: activeCompetency?.id,
      });
      applyReply(reply);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'The AI Coach is unavailable right now.');
    } finally {
      setThinking(false);
    }
  }

  function applyReply(reply: CoachResponse) {
    setActiveMode(reply.activeMode);
    setScaffolding(reply.scaffoldingLevel);
    setSuggestedActions(reply.suggestedActions);
    setFinished(reply.finished);
    setMessages((prev) => [
      ...prev,
      { id: nextId(), sender: 'coach', text: reply.message, mode: reply.activeMode },
    ]);
  }

  useEffect(() => {
    if (!started) startConversation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || thinking || finished) return;

    setMessages((prev) => [...prev, { id: nextId(), sender: 'student', text }]);
    setInput('');
    setThinking(true);

    try {
      const reply = await sendCoachMessage({
        message: text,
        mode: selectedMode ?? undefined,
        competencyId: activeCompetency?.id,
      });
      applyReply(reply);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          sender: 'coach',
          text: `⚠️ ${err instanceof Error ? err.message : "Couldn't reach the coach — please try again."}`,
          mode: 'LEARN',
        },
      ]);
    } finally {
      setThinking(false);
    }
  }

  function handleModeChange(value: string) {
    setSelectedMode(value === '' ? null : (value as CoachMode));
  }

  return (
    <div className="page-narrow ai-coach">
      <div className="ai-coach__context">
        <Card padding="md" className="ai-coach__context-card">
          <div>
            <span className="ai-coach__context-label">Current competency</span>
            <span className="ai-coach__context-value">
              {activeCompetency?.name ?? 'PID Reasoning'}
            </span>
          </div>
          <div>
            <span className="ai-coach__context-label">Active mode</span>
            <span className="ai-coach__context-value">
              <Badge tone="primary">{activeMode}</Badge>
            </span>
          </div>
          <div>
            <span className="ai-coach__context-label">Scaffolding</span>
            <span className="ai-coach__context-value">{scaffolding ?? '—'}</span>
          </div>
        </Card>
      </div>

      <Card padding="lg" className="ai-coach__panel">
        <div className="ai-coach__header">
          <h1 className="ai-coach__title">AI Coach</h1>
          {finished && <Badge tone="success">Demonstrated</Badge>}
        </div>

        {/* NEW: Mode selector — lets the student pick the coaching mode, or
            let the reasoning engine pick one automatically (None = auto). */}
        <div className="ai-coach__mode-row">
          <label className="ai-coach__mode-label" htmlFor="coach-mode">
            Coach mode
          </label>
          <select
            id="coach-mode"
            className="ai-coach__mode-select"
            value={selectedMode ?? ''}
            onChange={(e) => handleModeChange(e.target.value)}
            disabled={thinking || finished}
          >
            <option value="">Auto (engine picks)</option>
            {MODES.map((m) => (
              <option key={m.value} value={m.value} title={m.description}>
                {m.label} — {m.description}
              </option>
            ))}
          </select>
        </div>

        {suggestedActions.length > 0 && (
          <div className="ai-coach__suggested">
            <span className="ai-coach__suggested-label">Suggested next steps:</span>
            <ul>
              {suggestedActions.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}

        {loadError ? (
          <ErrorState message={loadError} onRetry={startConversation} />
        ) : (
          <>
            <div className="ai-coach__messages">
              {messages.map((m) => (
                <div key={m.id} className={`ai-coach__bubble ai-coach__bubble--${m.sender}`}>
                  <span className="ai-coach__bubble-sender">
                    {m.sender === 'coach' ? `Coach · ${m.mode ?? activeMode}` : 'You'}
                  </span>
                  <p>{m.text}</p>
                </div>
              ))}
              {thinking && (
                <div className="ai-coach__bubble ai-coach__bubble--coach ai-coach__bubble--thinking">
                  <span className="ai-coach__bubble-sender">Coach</span>
                  <span className="ai-coach__typing" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                  </span>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {finished ? (
              <div className="ai-coach__finished">
                <p className="muted">
                  You've demonstrated this competency. Ready to put it into practice?
                </p>
                <Button onClick={() => navigate('/my-learning/practice')}>Continue to Practice</Button>
              </div>
            ) : (
              <form className="ai-coach__input-row" onSubmit={handleSend}>
                <input
                  className="ai-coach__input"
                  type="text"
                  placeholder="Ask the Coach…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={thinking}
                  aria-label="Message to AI Coach"
                />
                <Button type="submit" disabled={!input.trim() || thinking}>
                  Send
                </Button>
              </form>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
