import Card from '../ui/Card';
import './Differentiators.css';

const TRADITIONAL = ['Course completion', 'Quiz scores', 'Passive learning'];
const PLATFORM = [
  'Competency development',
  'Evidence of performance',
  'Practice and application',
  'Personalized next steps',
];

export default function Differentiators() {
  return (
    <section className="differentiators">
      <div className="differentiators__inner">
        <h2 className="differentiators__title">More Than a Course. A Path to Competency.</h2>

        <div className="differentiators__grid">
          <Card padding="lg" className="differentiators__card differentiators__card--traditional">
            <h3 className="differentiators__card-title muted">Traditional Learning</h3>
            <ul className="differentiators__list">
              {TRADITIONAL.map((item) => (
                <li key={item}>
                  <span className="differentiators__icon differentiators__icon--muted">–</span>
                  {item}
                </li>
              ))}
            </ul>
          </Card>

          <Card padding="lg" className="differentiators__card differentiators__card--platform">
            <h3 className="differentiators__card-title">Our Platform</h3>
            <ul className="differentiators__list">
              {PLATFORM.map((item) => (
                <li key={item}>
                  <span className="differentiators__icon">✓</span>
                  {item}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </section>
  );
}
