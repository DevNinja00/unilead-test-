import { forwardRef } from 'react';
import './JourneySection.css';

const STEPS = [
  { number: '01', label: 'Diagnose', description: 'See what you already know and where to focus first.' },
  { number: '02', label: 'Learn', description: 'Study focused lessons built around your specific gaps.' },
  { number: '03', label: 'Practice', description: 'Apply new concepts to realistic, hands-on problems.' },
  { number: '04', label: 'Apply', description: 'Test your understanding in a real simulation, not a quiz.' },
  { number: '05', label: 'Review', description: 'See the evidence behind your progress, not just a score.' },
  { number: '06', label: 'Demonstrate', description: 'Prove mastery by transferring your skills to something new.' },
];

const JourneySection = forwardRef<HTMLElement>(function JourneySection(_props, ref) {
  return (
    <section className="journey" id="how-it-works" ref={ref}>
      <div className="journey__inner">
        <h2 className="journey__title">Your Learning Journey</h2>
        <p className="journey__subtitle muted">
          This isn't a list of videos to finish. Each step builds toward one goal: real,
          demonstrated competency.
        </p>

        <ol className="journey__timeline">
          {STEPS.map((step) => (
            <li key={step.number} className="journey__step">
              <div className="journey__marker">{step.number}</div>
              <div className="journey__step-body">
                <h3 className="journey__step-label">{step.label}</h3>
                <p className="muted journey__step-description">{step.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
});

export default JourneySection;
