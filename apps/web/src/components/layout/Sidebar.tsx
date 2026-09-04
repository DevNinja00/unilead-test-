import type { Competency } from '../../types';
import './Sidebar.css';

const STATUS_ICON: Record<Competency['status'], string> = {
  DEMONSTRATED: '✓',
  DEVELOPING: '◐',
  NEEDS_PRACTICE: '○',
  NOT_STARTED: '○',
};

export default function Sidebar({
  courseLabel,
  competencies,
  activeCompetencyId,
}: {
  courseLabel: string;
  competencies: Competency[];
  activeCompetencyId: string;
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar__course">{courseLabel}</div>
      <ul className="sidebar__list">
        {competencies.map((c) => (
          <li
            key={c.id}
            className={`sidebar__item ${c.id === activeCompetencyId ? 'sidebar__item--active' : ''}`}
          >
            <span
              className={`sidebar__icon sidebar__icon--${c.status.toLowerCase().replace('_', '-')}`}
            >
              {STATUS_ICON[c.status]}
            </span>
            {c.name}
          </li>
        ))}
      </ul>
    </aside>
  );
}
