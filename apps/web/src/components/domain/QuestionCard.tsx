import Card from '../ui/Card';
import './QuestionCard.css';

interface Option {
  id: string;
  label: string;
}

interface QuestionCardProps {
  prompt: string;
  options: Option[];
  selectedOptionId?: string;
  onSelect: (optionId: string) => void;
  stepLabel?: string;
}

export default function QuestionCard({
  prompt,
  options,
  selectedOptionId,
  onSelect,
  stepLabel,
}: QuestionCardProps) {
  return (
    <Card padding="lg" className="question-card">
      {stepLabel && <div className="question-card__step">{stepLabel}</div>}
      <h2 className="question-card__prompt">{prompt}</h2>
      <div className="question-card__options">
        {options.map((opt) => {
          const selected = opt.id === selectedOptionId;
          return (
            <button
              key={opt.id}
              className={`question-card__option ${selected ? 'question-card__option--selected' : ''}`}
              onClick={() => onSelect(opt.id)}
              aria-pressed={selected}
            >
              <span className="question-card__radio" aria-hidden="true" />
              {opt.label}
            </button>
          );
        })}
      </div>
    </Card>
  );
}
