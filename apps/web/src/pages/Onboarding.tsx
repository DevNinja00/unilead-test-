import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import QuestionCard from '../components/domain/QuestionCard';
import Button from '../components/ui/Button';
import ProgressBar from '../components/ui/ProgressBar';
import { useApp } from '../state/AppContext';
import { submitOnboarding } from '../data/mockApi';
import type { OnboardingAnswers } from '../types';
import './Onboarding.css';

const QUESTIONS: {
  key: keyof OnboardingAnswers;
  prompt: string;
  options: { id: string; label: string }[];
}[] = [
  {
    key: 'learningChallenge',
    prompt: "What's your biggest challenge when learning something technical?",
    options: [
      { id: 'a', label: 'Staying consistent over time' },
      { id: 'b', label: 'Understanding the "why" behind concepts' },
      { id: 'c', label: 'Applying theory to real problems' },
      { id: 'd', label: 'Knowing what to focus on' },
    ],
  },
  {
    key: 'preferredMethod',
    prompt: 'How do you learn best?',
    options: [
      { id: 'a', label: 'Reading clear explanations' },
      { id: 'b', label: 'Hands-on practice' },
      { id: 'c', label: 'Talking it through with a coach' },
      { id: 'd', label: 'A mix of everything' },
    ],
  },
  {
    key: 'obstacle',
    prompt: 'What usually gets in the way of your progress?',
    options: [
      { id: 'a', label: 'Not enough time' },
      { id: 'b', label: 'Losing motivation' },
      { id: 'c', label: 'Getting stuck with no help nearby' },
      { id: 'd', label: 'Not sure if I actually understand it' },
    ],
  },
  {
    key: 'goal',
    prompt: 'What do you want to walk away with?',
    options: [
      { id: 'a', label: 'Confidence I can apply what I learn' },
      { id: 'b', label: 'A strong grade in the course' },
      { id: 'c', label: 'Real, demonstrable skills' },
      { id: 'd', label: 'Just to keep up with class' },
    ],
  },
];

export default function Onboarding() {
  const navigate = useNavigate();
  const { setOnboardingAnswers } = useApp();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const current = QUESTIONS[step];
  const isLast = step === QUESTIONS.length - 1;
  const selected = answers[current.key];

  async function handleNext() {
    if (!isLast) {
      setStep((s) => s + 1);
      return;
    }
    setSubmitting(true);
    const finalAnswers = answers as unknown as OnboardingAnswers;
    try {
      await submitOnboarding(finalAnswers);
      setOnboardingAnswers(finalAnswers);
      navigate('/home');
    } finally {
      setSubmitting(false);
    }
  }

  function handleSelect(optionId: string) {
    setAnswers((prev) => ({ ...prev, [current.key]: optionId }));
  }

  return (
    <div className="page-narrow onboarding">
      <div className="onboarding__progress">
        <ProgressBar
          value={((step + 1) / QUESTIONS.length) * 100}
          showPercent={false}
          tone="accent"
        />
      </div>

      <QuestionCard
        stepLabel={`Question ${step + 1} of ${QUESTIONS.length}`}
        prompt={current.prompt}
        options={current.options}
        selectedOptionId={selected}
        onSelect={handleSelect}
      />

      <div className="onboarding__actions">
        {step > 0 ? (
          <Button variant="ghost" onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
        ) : (
          <span />
        )}
        <Button onClick={handleNext} disabled={!selected} loading={submitting}>
          {isLast ? 'Finish' : 'Next'}
        </Button>
      </div>
    </div>
  );
}
