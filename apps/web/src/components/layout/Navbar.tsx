import { Link, useLocation, useNavigate } from 'react-router-dom';
import DropdownMenu from '../ui/DropdownMenu';
import { useApp } from '../../state/AppContext';
import { logout } from '../../data/mockApi';
import './Navbar.css';

export default function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { student, session, setSession, setStudent } = useApp();

  const isActive = (prefix: string) => location.pathname.startsWith(prefix);

  const initials = session?.name
    ? session.name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : student?.name
    ? student.name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'S';

  function handleLogout() {
    logout();
    setSession(null);
    setStudent(null as never); // clear student too
    navigate('/login');
  }

  return (
    <header className="navbar">
      <div className="navbar__inner">
        <Link to="/home" className="navbar__brand">
          <span className="navbar__brand-mark">◆</span>
          Compass
        </Link>

        <nav className="navbar__links">
          <Link
            to="/home"
            className={`navbar__link ${location.pathname === '/home' ? 'navbar__link--active' : ''}`}
          >
            Home
          </Link>

          <DropdownMenu
            label="My Learning"
            active={isActive('/my-learning')}
            items={[
              { label: 'Overview', description: 'Everything in My Learning', href: '/my-learning', icon: '📋' },
              { label: 'Diagnostic', description: 'Find your starting point', href: '/my-learning/diagnostic', icon: '🧭' },
              { label: 'Learning', description: 'Study the current lesson', href: '/my-learning/learning', icon: '📚' },
              { label: 'AI Coach', description: 'Talk through your reasoning', href: '/my-learning/ai-coach', icon: '💬' },
              { label: 'Practice', description: 'Apply what you learned', href: '/my-learning/practice', icon: '✏️' },
              { label: 'Remediation', description: 'Targeted micro-lesson for your weak spot', href: '/my-learning/remediation', icon: '🩹' },
            ]}
          />

          <DropdownMenu
            label="Apply & Review"
            active={isActive('/apply-review')}
            items={[
              { label: 'Overview', description: 'Everything in Apply & Review', href: '/apply-review', icon: '📋' },
              { label: 'Simulation', description: 'Run your controller', href: '/apply-review/simulation', icon: '⚙️' },
              { label: 'Transfer', description: 'Apply your skill to a new plant', href: '/apply-review/transfer', icon: '🔄' },
              { label: 'Evidence Timeline', description: 'Chronological feed of your events', href: '/apply-review/evidence-timeline', icon: '🕐' },
              { label: 'Review', description: 'See your evidence', href: '/apply-review/review', icon: '🔍' },
            ]}
          />

          <DropdownMenu
            label="My Progress"
            active={isActive('/progress')}
            items={[
              { label: 'Overview', description: 'Everything in My Progress', href: '/progress', icon: '📋' },
              { label: 'Progress', description: 'Overall course progress', href: '/progress/overview', icon: '📈' },
              { label: 'Competency Profile', description: 'Your mastery by skill', href: '/progress/competency-profile', icon: '🏆' },
            ]}
          />

          {session?.role === 'instructor' && (
            <DropdownMenu
              label="Instructor"
              active={isActive('/instructor')}
              items={[
                { label: 'Class Dashboard', description: 'Aggregate view of all students', href: '/instructor', icon: '👨‍🏫' },
              ]}
            />
          )}
        </nav>

        <div className="navbar__auth">
          {session && (
            <button className="navbar__logout" onClick={handleLogout} aria-label="Log out">
              Log out
            </button>
          )}
          <button className="navbar__avatar" onClick={() => navigate('/profile')} aria-label="View profile">
            {initials}
          </button>
        </div>
      </div>
    </header>
  );
}
