import type { ReactNode } from 'react';
import { createContext, useContext, useMemo, useState } from 'react';
import type { Student, DiagnosticResult, OnboardingAnswers, JourneyFlags, AuthSession } from '../types';

interface AppState {
  student: Student | null;
  setStudent: (s: Student) => void;
  onboardingAnswers: OnboardingAnswers | null;
  setOnboardingAnswers: (a: OnboardingAnswers) => void;
  diagnosticResults: DiagnosticResult[] | null;
  setDiagnosticResults: (r: DiagnosticResult[]) => void;

  // NEW: auth session — stored in localStorage so refresh keeps you logged in
  session: AuthSession | null;
  setSession: (s: AuthSession | null) => void;

  // Journey progress — read by Home to decide what to recommend next.
  journey: JourneyFlags;
  markLearningComplete: () => void;
  markPracticeComplete: () => void;
  markSimulationComplete: () => void;
  markReviewComplete: () => void;
}

const AppContext = createContext<AppState | undefined>(undefined);

const SESSION_KEY = 'unilead_session';

function loadSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthSession;
  } catch {
    return null;
  }
}

function saveSession(s: AuthSession | null) {
  if (s) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(s));
  } else {
    localStorage.removeItem(SESSION_KEY);
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [student, setStudent] = useState<Student | null>(null);
  const [onboardingAnswers, setOnboardingAnswers] = useState<OnboardingAnswers | null>(null);
  const [diagnosticResults, setDiagnosticResults] = useState<DiagnosticResult[] | null>(null);
  const [session, setSessionState] = useState<AuthSession | null>(loadSession);

  const [hasCompletedLearning, setHasCompletedLearning] = useState(false);
  const [hasCompletedPractice, setHasCompletedPractice] = useState(false);
  const [hasCompletedSimulation, setHasCompletedSimulation] = useState(false);
  const [hasCompletedReview, setHasCompletedReview] = useState(false);

  const setSession = (s: AuthSession | null) => {
    setSessionState(s);
    saveSession(s);
  };

  const value = useMemo<AppState>(
    () => ({
      student,
      setStudent,
      onboardingAnswers,
      setOnboardingAnswers,
      diagnosticResults,
      setDiagnosticResults,
      session,
      setSession,
      journey: {
        hasCompletedOnboarding: onboardingAnswers !== null,
        hasCompletedDiagnostic: diagnosticResults !== null,
        hasCompletedLearning,
        hasCompletedPractice,
        hasCompletedSimulation,
        hasCompletedReview,
      },
      markLearningComplete: () => setHasCompletedLearning(true),
      markPracticeComplete: () => setHasCompletedPractice(true),
      markSimulationComplete: () => setHasCompletedSimulation(true),
      markReviewComplete: () => setHasCompletedReview(true),
    }),
    [
      student,
      onboardingAnswers,
      diagnosticResults,
      session,
      hasCompletedLearning,
      hasCompletedPractice,
      hasCompletedSimulation,
      hasCompletedReview,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
