import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import Button from './Button';
import Card from './Card';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh', padding: '2rem' }}>
          <Card padding="lg" style={{ maxWidth: 480, textAlign: 'center' }}>
            <h2 style={{ marginBottom: '0.5rem' }}>Something went wrong</h2>
            <p className="muted" style={{ marginBottom: '1rem' }}>
              An unexpected error occurred. You can try reloading this page.
            </p>
            {this.state.error && (
              <pre style={{ fontSize: '0.75rem', color: 'var(--danger, #dc3545)', textAlign: 'left', overflow: 'auto', maxHeight: 120, marginBottom: '1rem', padding: '0.5rem', background: 'var(--surface-alt, #f5f5f5)', borderRadius: 6 }}>
                {this.state.error.message}
              </pre>
            )}
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
              <Button onClick={this.handleReset} variant="secondary">Try Again</Button>
              <Button onClick={() => window.location.reload()} variant="primary">Reload Page</Button>
            </div>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
