import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import QuestionCard from '../components/domain/QuestionCard';
import Button from '../components/ui/Button';
import ProgressBar from '../components/ui/ProgressBar';
import Card from '../components/ui/Card';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { getDiagnosticQuestions, submitDiagnostic } from '../data/mockApi';
import { useApp } from '../state/AppContext';
import type { AsyncState, DiagnosticQuestion, DiagnosticAnswer } from '../types';
import './Diagnostic.css';

type Phase = 'intro' | 'questions';

export default function Diagnostic() {
  const navigate = useNavigate();
  const { setDiagnosticResults } = useApp();
  const [phase, setPhase] = useState<Phase>('intro');
  const [state, setState] = useState<AsyncState<DiagnosticQuestion[]>>({ status: 'idle' });
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<DiagnosticAnswer[]>([]);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setState({ status: 'loading' });
    try {
      const questions = await getDiagnosticQuestions();
      setState({ status: 'success', data: questions });
    } catch (err) {
      setState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Could not load the diagnostic.',
      });
    }
  }

  useEffect(() => {
    if (phase === 'questions' && state.status === 'idle') {
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  if (phase === 'intro') {
    return (
      <div className="page-narrow diagnostic-intro">
        <Card padding="lg">
          <div className="diagnostic-intro__icon">🧭</div>
          <h1 className="diagnostic-intro__title">Let's find your starting point</h1>
          <p className="muted diagnostic-intro__text">
            This short diagnostic (5 questions, about 3 minutes) checks where you're already
            strong and where to focus first. There's no pass or fail — it just helps us
            personalize your path through MEC271.
          </p>
          <Button size="lg" onClick={() => setPhase('questions')}>
            Start Diagnostic
          </Button>
        </Card>
      </div>
    );
  }

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="page-narrow">
        <LoadingState message="Preparing your diagnostic…" />
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="page-narrow">
        <ErrorState message={state.message} onRetry={load} />
      </div>
    );
  }

  const questions = state.data;
  const current = questions[step]!;
  const isLast = step === questions.length - 1;
  const existingAnswer = answers.find((a) => a.questionId === current.id)?.optionId;

  function handleSelect(optionId: string) {
    setAnswers((prev) => {
      const rest = prev.filter((a) => a.questionId !== current.id);
      return [...rest, { questionId: current.id, optionId }];
    });
  }

  async function handleNext() {
    if (!isLast) {
      setStep((s) => s + 1);
      return;
    }
    setSubmitting(true);
    try {
      const results = await submitDiagnostic(answers);
      setDiagnosticResults(results);
      navigate('/my-learning/diagnostic-results');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-narrow diagnostic">
      <div className="diagnostic__progress">
        <ProgressBar value={((step + 1) / questions.length) * 100} showPercent={false} />
      </div>

      <QuestionCard
        stepLabel={`Question ${step + 1} of ${questions.length}`}
        prompt={current.prompt}
        options={current.options}
        selectedOptionId={existingAnswer}
        onSelect={handleSelect}
      />

      <div className="diagnostic__actions">
        {step > 0 ? (
          <Button variant="ghost" onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
        ) : (
          <span />
        )}
        <Button onClick={handleNext} disabled={!existingAnswer} loading={submitting}>
          {isLast ? 'Finish Diagnostic' : 'Next'}
        </Button>
      </div>
    </div>
  );
}
