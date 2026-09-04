import type { ReactNode } from 'react';
import { useEffect, useRef, useState, useCallback } from 'react';
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
  const menuRef = useRef<HTMLDivElement>(null);

  const focusItem = useCallback((index: number) => {
    const links = menuRef.current?.querySelectorAll<HTMLAnchorElement>('.dropdown__item');
    links?.[index]?.focus();
  }, []);

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
    function handleKeyDown(e: KeyboardEvent) {
      if (!open) return;
      const links = menuRef.current?.querySelectorAll<HTMLAnchorElement>('.dropdown__item');
      const count = links?.length ?? 0;
      if (count === 0) return;
      const currentIndex = Array.from(links ?? []).indexOf(document.activeElement as HTMLAnchorElement);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        focusItem(currentIndex < count - 1 ? currentIndex + 1 : 0);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        focusItem(currentIndex > 0 ? currentIndex - 1 : count - 1);
      } else if (e.key === 'Home') {
        e.preventDefault();
        focusItem(0);
      } else if (e.key === 'End') {
        e.preventDefault();
        focusItem(count - 1);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, focusItem]);

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
        <div className="dropdown__menu" ref={menuRef} role="menu">
          {items.map((item) => (
            <Link
              key={item.href}
              to={item.href}
              className="dropdown__item"
              role="menuitem"
              tabIndex={0}
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
