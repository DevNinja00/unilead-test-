import { useEffect, useRef, useState } from 'react';
import Hero from '../components/home/Hero';
import ValueProps from '../components/home/ValueProps';
import JourneySection from '../components/home/JourneySection';
import Differentiators from '../components/home/Differentiators';
import PersonalizedSection from '../components/home/PersonalizedSection';
import FinalCta from '../components/home/FinalCta';
import HomeFooter from '../components/home/HomeFooter';
import { useApp } from '../state/AppContext';
import { getStudent, getRecommendation } from '../data/mockApi';
import type { AsyncState, Recommendation, Student } from '../types';

const FALLBACK_HREF = '/my-learning';

export default function Home() {
  const { student, setStudent, journey } = useApp();
  const [state, setState] = useState<AsyncState<{ student: Student; recommendation: Recommendation }>>({
    status: 'loading',
  });
  const journeySectionRef = useRef<HTMLElement>(null);

  async function load() {
    setState({ status: 'loading' });
    try {
      const s = student ?? (await getStudent());
      if (!student) setStudent(s);
      const activeCompetency = s.competencies.find((c) => c.status === 'DEVELOPING') ?? s.competencies[0]!;
      const rec = await getRecommendation(journey, activeCompetency.name);
      setState({ status: 'success', data: { student: s, recommendation: rec } });
    } catch (err) {
      setState({ status: 'error', message: err instanceof Error ? err.message : 'Failed to load your dashboard.' });
    }
  }

  useEffect(() => {
    load();
    // Reload whenever journey progress changes, so the recommendation stays current.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journey]);

  const primaryHref = state.status === 'success' ? state.data.recommendation.href : FALLBACK_HREF;

  function scrollToJourney() {
    journeySectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <div className="home">
      <Hero primaryHref={primaryHref} onExploreClick={scrollToJourney} />
      <ValueProps />
      <JourneySection ref={journeySectionRef} />
      <Differentiators />
      <PersonalizedSection state={state} onRetry={load} />
      <FinalCta href={primaryHref} />
      <HomeFooter />
    </div>
  );
}
