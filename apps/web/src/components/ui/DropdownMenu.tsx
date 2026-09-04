import type { ReactNode } from 'react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import './DropdownMenu.css';

export interface DropdownItem {
  label: string;
  description?: string;
  href: string;
  icon?: ReactNode;
}

interface DropdownMenuProps {
  label: string;
  items: DropdownItem[];
  active?: boolean;
}

export default function DropdownMenu({ label, items, active = false }: DropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape' && open) {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  return (
    <div className="dropdown" ref={ref}>
      <button
        ref={triggerRef}
        className={`dropdown__trigger ${active ? 'dropdown__trigger--active' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="true"
        aria-expanded={open}
      >
        {label}
        <span className={`dropdown__chevron ${open ? 'dropdown__chevron--open' : ''}`}>▾</span>
      </button>
      {open && (
        <div className="dropdown__menu" role="menu">
          {items.map((item) => (
            <Link
              key={item.href}
              to={item.href}
              className="dropdown__item"
              role="menuitem"
              onClick={() => setOpen(false)}
            >
              {item.icon && <span className="dropdown__item-icon">{item.icon}</span>}
              <span>
                <span className="dropdown__item-label">{item.label}</span>
                {item.description && (
                  <span className="dropdown__item-desc">{item.description}</span>
                )}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
