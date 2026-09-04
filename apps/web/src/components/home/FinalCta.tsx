import { useNavigate } from 'react-router-dom';
import Button from '../ui/Button';
import './FinalCta.css';

export default function FinalCta({ href }: { href: string }) {
  const navigate = useNavigate();

  return (
    <section className="final-cta">
      <div className="final-cta__inner">
        <h2 className="final-cta__title">Ready to Build Real Competencies?</h2>
        <p className="final-cta__subtext">Learn, practice, apply, and prove what you can do.</p>
        <Button variant="accent" size="lg" onClick={() => navigate(href)}>
          Start Learning →
        </Button>
      </div>
    </section>
  );
}
