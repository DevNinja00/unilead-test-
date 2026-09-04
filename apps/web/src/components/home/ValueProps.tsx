import { useNavigate } from 'react-router-dom';
import Card from '../ui/Card';
import './ValueProps.css';

const ITEMS = [
  {
    icon: '📚',
    title: 'Learn',
    description: 'Personalized learning experiences that focus on what you need to improve.',
    href: '/my-learning/learning',
  },
  {
    icon: '💬',
    title: 'AI Coach',
    description: 'Get guided support, explanations, hints, and feedback while you learn.',
    href: '/my-learning/ai-coach',
  },
  {
    icon: '✏️',
    title: 'Practice & Apply',
    description: 'Practice your skills through realistic tasks and simulations.',
    href: '/my-learning/practice',
  },
];

export default function ValueProps() {
  const navigate = useNavigate();

  return (
    <section className="value-props">
      <div className="value-props__inner">
        <h2 className="value-props__title">Everything You Need to Learn Better</h2>

        <div className="value-props__grid">
          {ITEMS.map((item) => (
            <Card
              key={item.title}
              padding="lg"
              interactive
              className="value-props__card"
              onClick={() => navigate(item.href)}
            >
              <div className="value-props__icon">{item.icon}</div>
              <h3 className="value-props__card-title">{item.title}</h3>
              <p className="muted">{item.description}</p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
