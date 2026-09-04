import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';

export default function NotFound() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh', padding: '2rem' }}>
      <Card padding="lg" style={{ maxWidth: 480, textAlign: 'center' }}>
        <h1 style={{ fontSize: '3rem', marginBottom: '0.25rem' }}>404</h1>
        <h2 style={{ marginBottom: '0.5rem' }}>Page not found</h2>
        <p className="muted" style={{ marginBottom: '1.5rem' }}>
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Link to="/home">
          <Button variant="primary" size="lg">Back to Home</Button>
        </Link>
      </Card>
    </div>
  );
}
