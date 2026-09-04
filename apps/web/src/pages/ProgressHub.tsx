import PageHeader from '../components/ui/PageHeader';
import HubGrid from '../components/domain/HubGrid';

export default function ProgressHub() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="My Progress"
        title="Track your competency development"
        subtitle="See your overall progress and a breakdown by competency."
      />
      <HubGrid
        tiles={[
          {
            icon: '📈',
            title: 'Progress',
            description: 'Your overall course progress at a glance.',
            href: '/progress/overview',
          },
          {
            icon: '🏆',
            title: 'Competency Profile',
            description: 'Detailed mastery status for every competency.',
            href: '/progress/competency-profile',
          },
        ]}
      />
    </div>
  );
}
