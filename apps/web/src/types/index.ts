// Core domain types for the competency-based learning MVP.
// These mirror the "Data Contract" the real Education API will eventually return.

export type CompetencyStatus =
  | 'NOT_STARTED'
  | 'NEEDS_PRACTICE'
  | 'DEVELOPING'
  | 'DEMONSTRATED';

export interface Competency {
  id: string;
  name: string;
  status: CompetencyStatus;
  progress: number; // 0-100, derived from evidence — UI never invents this
}

export interface Course {
  id: string;
  code: string; // e.g. MEC271
  title: string; // e.g. Automatic Control
}

export interface Student {
  id: string;
  name: string;
  email: string;
  course: Course;
  overallProgress: number; // 0-100
  competencies: Competency[];
}

export interface OnboardingAnswers {
  learningChallenge: string;
  preferredMethod: string;
  obstacle: string;
  goal: string;
}

export interface DiagnosticQuestion {
  id: string;
  competencyId: string;
  prompt: string;
  options: { id: string; label: string }[];
}

export interface DiagnosticAnswer {
  questionId: string;
  optionId: string;
}

export interface DiagnosticResult {
  competencyId: string;
  competencyName: string;
  status: CompetencyStatus;
  // NEW (wired): misconceptions detected from incorrect answers on this
  // competency's diagnostic question.
  misconceptions: string[];
  // NEW (wired): raw correctness on this competency's question (0..1).
  accuracy: number;
}

export interface Recommendation {
  id: string;
  title: string;
  reason: string;
  href: string;
}

export interface LessonSection {
  id: string;
  heading: string;
  body: string;
}

export interface PracticeTask {
  id: string;
  title: string;
  objective: string;
  requirements: string[];
  hints: string[];
}

export interface SimulationResult {
  stable: boolean;
  overshoot: number; // percent
  settlingTime: number; // seconds
  riseTime: number; // seconds
  steadyStateError: number;
  // NEW (wired): which gains produced this run + evidence outcome.
  kp: number;
  ki: number;
  kd: number;
  requirementsMet: boolean;
  result: 'PASS' | 'FAIL';
  attempt: number;
  competencyId: string;
  misconception: string | null;
}

export interface EvidenceItem {
  id: string;
  label: string;
  met: boolean;
}

export interface ReviewData {
  competencyId: string;
  competencyName: string;
  status: CompetencyStatus;
  evidence: EvidenceItem[];
}

// The six AI Coach modes — mirrors ai_education.domain.enums.CoachMode.
export type CoachMode =
  | 'LEARN'
  | 'HINT'
  | 'PRACTICE'
  | 'REFLECT'
  | 'REMEDIATE'
  | 'TRANSFER';

export interface CoachMessage {
  id: string;
  sender: 'coach' | 'student';
  text: string;
  // NEW (wired): which mode produced this coach message.
  mode?: CoachMode;
}

// NEW (wired): the response shape from POST /api/coach.
export interface CoachResponse {
  message: string;
  activeMode: CoachMode;
  targetCompetencyId: string | null;
  scaffoldingLevel: 'LOW' | 'MEDIUM' | 'HIGH' | null;
  suggestedActions: string[];
  turnIndex: number;
  totalTurns: number;
  finished: boolean;
}

// NEW (wired): the response shape from GET /api/remediation/{id}.
export interface RemediationPlan {
  competencyId: string;
  detectedMisconception: string | null;
  recommendedAction: string;
  conceptualFocus: string;
  guidedQuestion: string;
  remediationSteps: string[];
  consecutiveFailures: number;
  totalAttempts: number;
  summaryText: string;
}

// NEW (wired): the response shape from GET /api/transfer/{id}.
export interface TransferScenario {
  competencyId: string;
  scenarioId: string;
  title: string;
  domain: string;
  prompt: string;
  errorSignalMeaning: string;
  controlOutputMeaning: string;
  systemInertia: string;
  conceptualChallenge: string;
}

// NEW (wired): the response shape from POST /api/transfer/{id}.
export interface TransferEvaluation {
  competencyId: string;
  scenarioId: string;
  passed: boolean;
  matchedTerms: string[];
  matchedCount: number;
  minRequired: number;
  feedback: string;
}

// Tracks how far the student has progressed through the core learning loop.
// The UI reads these flags to decide what to recommend next — it never
// invents progression logic of its own.
export interface JourneyFlags {
  hasCompletedOnboarding: boolean;
  hasCompletedDiagnostic: boolean;
  hasCompletedLearning: boolean;
  hasCompletedPractice: boolean;
  hasCompletedSimulation: boolean;
  hasCompletedReview: boolean;
}

// Async state wrapper every page uses for its data fetch.
export type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: T };

// ---- Instructor types (NEW) ------------------------------------------------

export interface InstructorStudentSummary {
  studentId: string;
  displayName: string;
  courseCode: string;
  courseTitle: string;
  overallProgress: number;
  competencies: Competency[];
}

export interface InstructorCompetencyAggregate {
  competencyId: string;
  competencyName: string;
  demonstrated: number;
  developing: number;
  needsPractice: number;
  notStarted: number;
}

export interface InstructorClassSummary {
  totalStudents: number;
  averageOverallProgress: number;
  studentsDemonstratedAll: number;
  studentsWithFailures: number;
}

export interface EvidenceEvent {
  timestamp: string;
  eventType:
    | 'diagnostic_submitted'
    | 'simulation_run'
    | 'remediation_completed'
    | 'transfer_evaluated'
    | 'coach_turn'
    | string;
  competencyId: string | null;
  title: string;
  detail: string;
  result: 'PASS' | 'FAIL' | 'INFO';
}

export interface InstructorStudentDetail extends InstructorStudentSummary {
  evidenceTimeline: EvidenceEvent[];
}

// ---- Auth types (NEW) ------------------------------------------------------

export interface AuthSession {
  accessToken: string;
  tokenType: 'bearer';
  userId: number;
  email: string;
  username: string;
  name: string;
  studentId: string;
}

export interface SignUpRequest {
  name: string;
  username: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface MeResponse {
  userId: number;
  email: string;
  username: string;
  name: string;
  studentId: string;
  studentDisplayName: string;
}
