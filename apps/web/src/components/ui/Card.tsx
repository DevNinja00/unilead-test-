import type { HTMLAttributes, KeyboardEvent, MouseEvent, ReactNode } from 'react';
import './Card.css';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: 'sm' | 'md' | 'lg';
  interactive?: boolean;
}

export default function Card({
  children,
  padding = 'md',
  interactive = false,
  className = '',
  onClick,
  onKeyDown,
  ...rest
}: CardProps) {
  // Interactive cards are activated by click everywhere else in the app,
  // but a <div onClick> is invisible to keyboard and screen-reader users.
  // Giving it a button role + tabIndex + Enter/Space handling fixes that
  // without changing how any page uses this component.
  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    onKeyDown?.(e);
    if (!interactive || !onClick) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick(e as unknown as MouseEvent<HTMLDivElement>);
    }
  }

  return (
    <div
      className={`card card--${padding} ${interactive ? 'card--interactive' : ''} ${className}`}
      onClick={onClick}
      onKeyDown={interactive ? handleKeyDown : onKeyDown}
      role={interactive && onClick ? 'button' : undefined}
      tabIndex={interactive && onClick ? 0 : undefined}
      {...rest}
    >
      {children}
    </div>
  );
}
