import PageHeader from '../components/ui/PageHeader';
import HubGrid from '../components/domain/HubGrid';

export default function ApplyReview() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="Apply & Review"
        title="Apply your knowledge"
        subtitle="Run simulations and review your performance evidence."
      />
      <HubGrid
        tiles={[
          {
            icon: '⚙️',
            title: 'Simulation',
            description: 'Run your controller against a real system and see the response.',
            href: '/apply-review/simulation',
          },
          {
            icon: '🔍',
            title: 'Review',
            description: 'See the evidence behind your competency status.',
            href: '/apply-review/review',
          },
        ]}
      />
    </div>
  );
}
