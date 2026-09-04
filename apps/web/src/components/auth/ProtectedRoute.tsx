import { Navigate, useLocation } from 'react-router-dom';
import { useApp } from '../../state/AppContext';

/**
 * Wraps routes that require authentication. If no session is present,
 * redirects to /login preserving the intended destination in state.
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session } = useApp();
  const location = useLocation();

  if (!session) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}

/**
 * Wraps routes that require the instructor role. If the user is not an
 * instructor, redirects to /home.
 */
export function InstructorRoute({ children }: { children: React.ReactNode }) {
  const { session } = useApp();

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  if (session.role !== 'instructor') {
    return <Navigate to="/home" replace />;
  }

  return <>{children}</>;
}
