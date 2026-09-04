import { useNavigate } from 'react-router-dom';
import Card from '../ui/Card';
import Button from '../ui/Button';
import type { Recommendation } from '../../types';
import './RecommendationCard.css';

export default function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  const navigate = useNavigate();

  return (
    <Card padding="lg" className="recommendation-card">
      <div className="recommendation-card__icon">🎯</div>
      <div className="recommendation-card__body">
        <span className="recommendation-card__eyebrow">Recommended Next Step</span>
        <h3 className="recommendation-card__title">{recommendation.title}</h3>
        <p className="recommendation-card__reason muted">{recommendation.reason}</p>
      </div>
      <Button variant="accent" onClick={() => navigate(recommendation.href)}>
        Start Now
      </Button>
    </Card>
  );
}
