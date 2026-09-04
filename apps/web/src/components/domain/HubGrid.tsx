import { useNavigate } from 'react-router-dom';
import Card from '../ui/Card';
import { Badge } from '../ui/Badge';
import './HubGrid.css';

export interface HubTile {
  icon: string;
  title: string;
  description: string;
  href: string;
  comingSoon?: boolean;
}

export default function HubGrid({ tiles }: { tiles: HubTile[] }) {
  const navigate = useNavigate();

  return (
    <div className="grid grid-2 hub-grid">
      {tiles.map((tile) => (
        <Card
          key={tile.href}
          padding="lg"
          interactive
          className="hub-tile"
          onClick={() => navigate(tile.href)}
        >
          <div className="hub-tile__icon">{tile.icon}</div>
          <div className="hub-tile__top">
            <h3>{tile.title}</h3>
            {tile.comingSoon && <Badge tone="accent">Coming Soon</Badge>}
          </div>
          <p className="muted">{tile.description}</p>
        </Card>
      ))}
    </div>
  );
}
