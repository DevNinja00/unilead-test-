import type { ReactNode } from 'react';
import Button from './Button';
import './StateViews.css';

export function LoadingState({ message = 'Loading…' }: { message?: string }) {
  return (
    <div className="state-view">
      <span className="state-view__spinner" aria-hidden="true" />
      <p className="state-view__text muted">{message}</p>
    </div>
  );
}

export function ErrorState({
  message = 'Something went wrong. Please try again.',
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="state-view">
      <span className="state-view__icon state-view__icon--danger">!</span>
      <p className="state-view__text">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action,
  icon = '📭',
}: {
  title: string;
  message?: string;
  action?: ReactNode;
  icon?: string;
}) {
  return (
    <div className="state-view">
      <span className="state-view__icon">{icon}</span>
      <p className="state-view__title">{title}</p>
      {message && <p className="state-view__text muted">{message}</p>}
      {action}
    </div>
  );
}
