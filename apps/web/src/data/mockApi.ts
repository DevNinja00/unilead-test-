// API layer for the app.
//
// This file is the ONLY place that knows the backend exists — every page
// imports from here exactly as it did when this was pure mock data, so
// nothing above this layer had to change when the FastAPI backend was
// added. Pages still never compute mastery/progress themselves; they just
// display what this layer returns.
//
// Field-name translation (backend is snake_case, frontend types are
// camelCase) happens once, right here.

import { apiGet, apiPost, setAuthToken, clearAuthToken } from './apiClient';
import type {
  Student,
  DiagnosticQuestion,
  DiagnosticAnswer,
  DiagnosticResult,
  Recommendation,
  LessonSection,
  PracticeTask,
  OnboardingAnswers,
  SimulationResult,
  ReviewData,
  JourneyFlags,
  CompetencyStatus,
  Competency,
  CoachMode,
  CoachResponse,
  RemediationPlan,
  TransferScenario,
  TransferEvaluation,
  InstructorStudentSummary,
  InstructorCompetencyAggregate,
  InstructorClassSummary,
  InstructorStudentDetail,
  EvidenceEvent,
  AuthSession,
  SignUpRequest,
  LoginRequest,
  MeResponse,
} from '../types';

function toFrontendStatus(status: string): CompetencyStatus {
  return status.toUpperCase() as CompetencyStatus;
}

// ---- Student / competencies -------------------------------------------

interface ApiCompetency {
  id: string;
  name: string;
  status: string;
  progress: number;
}

interface ApiProgress {
  overall_progress: number;
  competencies: { name: string; status: string }[];
  recommended_next_activity: string;
  course_code: string;
  course_title: string;
}

function mapCompetency(c: ApiCompetency): Competency {
  return { id: c.id, name: c.name, status: toFrontendStatus(c.status), progress: c.progress };
}

export async function getStudent(): Promise<Student> {
  const [competencies, progress, me] = await Promise.all([
    apiGet<ApiCompetency[]>('/competencies'),
    apiGet<ApiProgress>('/progress'),
    getMe(),
  ]);

  return {
    id: 'student-1',
    name: me.name,
    email: me.email,
    course: { id: 'mec271', code: progress.course_code, title: progress.course_title },
    overallProgress: progress.overall_progress,
    competencies: competencies.map(mapCompetency),
  };
}

// ---- Onboarding ---------------------------------------------------------

export async function submitOnboarding(answers: OnboardingAnswers): Promise<{ success: true }> {
  return apiPost('/onboarding', {
    learning_challenge: answers.learningChallenge,
    preferred_method: answers.preferredMethod,
    obstacle: answers.obstacle,
    goal: answers.goal,
  });
}

// ---- Diagnostic -----------------------------------------------------------

interface ApiDiagnosticQuestion {
  id: string;
  competency_id: string;
  prompt: string;
  options: { id: string; label: string }[];
}

interface ApiDiagnosticResult {
  competency_id: string;
  competency_name: string;
  status: string;
  misconceptions: string[];
  accuracy: number;
}

export async function getDiagnosticQuestions(): Promise<DiagnosticQuestion[]> {
  const questions = await apiGet<ApiDiagnosticQuestion[]>('/diagnostic/questions');
  return questions.map((q) => ({
    id: q.id,
    competencyId: q.competency_id,
    prompt: q.prompt,
    options: q.options,
  }));
}

export async function submitDiagnostic(answers: DiagnosticAnswer[]): Promise<DiagnosticResult[]> {
  const results = await apiPost<ApiDiagnosticResult[]>('/diagnostic', {
    answers: answers.map((a) => ({ question_id: a.questionId, option_id: a.optionId })),
  });
  return results.map((r) => ({
    competencyId: r.competency_id,
    competencyName: r.competency_name,
    status: toFrontendStatus(r.status),
    misconceptions: r.misconceptions ?? [],
    accuracy: r.accuracy ?? 0,
  }));
}

// ---- Learning / Practice content ------------------------------------------

export async function getLesson(competencyId: string): Promise<LessonSection[]> {
  return apiGet(`/learning/${competencyId}`);
}

export async function getPracticeTask(competencyId: string): Promise<PracticeTask> {
  return apiGet(`/practice/${competencyId}`);
}

// Marks a practice attempt as submitted. There's no backend endpoint for
// this yet (nothing downstream reads the result), so it resolves locally —
// keeping the same signature Practice.tsx already calls.
export async function submitPractice(_taskId: string): Promise<{ submitted: true }> {
  return { submitted: true };
}

// ---- Simulation -------------------------------------------------------------

interface ApiSimulationResult {
  stable: boolean;
  overshoot: number;
  settling_time: number;
  rise_time: number;
  steady_state_error: number;
  kp: number;
  ki: number;
  kd: number;
  requirements_met: boolean;
  result: 'PASS' | 'FAIL';
  attempt: number;
  competency_id: string;
  misconception: string | null;
}

export interface RunSimulationParams {
  kp: number;
  ki: number;
  kd: number;
  competencyId?: string;
  taskId?: string;
}

export async function runSimulation(params: RunSimulationParams): Promise<SimulationResult> {
  const r = await apiPost<ApiSimulationResult>('/simulation', {
    kp: params.kp,
    ki: params.ki,
    kd: params.kd,
    competency_id: params.competencyId ?? 'pid-tuning',
    task_id: params.taskId ?? 'pid-001',
  });
  return {
    stable: r.stable,
    overshoot: r.overshoot,
    settlingTime: r.settling_time,
    riseTime: r.rise_time,
    steadyStateError: r.steady_state_error,
    kp: r.kp,
    ki: r.ki,
    kd: r.kd,
    requirementsMet: r.requirements_met,
    result: r.result,
    attempt: r.attempt,
    competencyId: r.competency_id,
    misconception: r.misconception,
  };
}

// ---- Review / Evidence -----------------------------------------------------

interface ApiReviewResponse {
  competency_id: string;
  competency_name: string;
  status: string;
  progress: number;
  overall_progress: number;
  evidence: { id: string; label: string; met: boolean }[];
}

// Views the current evidence without changing anything server-side.
export async function getReview(competencyId: string): Promise<ReviewData> {
  const r = await apiPost<ApiReviewResponse>('/review', {
    competency_id: competencyId,
    finalize: false,
  });
  return {
    competencyId: r.competency_id,
    competencyName: r.competency_name,
    status: toFrontendStatus(r.status),
    evidence: r.evidence,
  };
}

// Finalizes the review: the backend folds the evidence back into the
// student's progress (this is the one place mastery numbers actually
// change), and we merge the result into the passed-in student object.
export async function completeReview(student: Student): Promise<Student> {
  const active =
    student.competencies.find((c) => c.status === 'DEVELOPING') ?? student.competencies[0];

  const r = await apiPost<ApiReviewResponse>('/review', {
    competency_id: active.id,
    finalize: true,
  });

  return {
    ...student,
    overallProgress: r.overall_progress,
    competencies: student.competencies.map((c) =>
      c.id === r.competency_id ? { ...c, status: toFrontendStatus(r.status), progress: r.progress } : c
    ),
  };
}

// ---- AI Coach ---------------------------------------------------------------

interface ApiCoachResponse {
  message: string;
  active_mode: CoachMode;
  target_competency_id: string | null;
  scaffolding_level: 'LOW' | 'MEDIUM' | 'HIGH' | null;
  suggested_actions: string[];
  turn_index: number;
  total_turns: number;
  finished: boolean;
}

export interface SendCoachMessageParams {
  message: string;
  mode?: CoachMode;
  competencyId?: string;
}

export async function sendCoachMessage(params: SendCoachMessageParams): Promise<CoachResponse> {
  const r = await apiPost<ApiCoachResponse>('/coach', {
    message: params.message,
    mode: params.mode ?? null,
    competency_id: params.competencyId ?? null,
  });
  return {
    message: r.message,
    activeMode: r.active_mode,
    targetCompetencyId: r.target_competency_id,
    scaffoldingLevel: r.scaffolding_level,
    suggestedActions: r.suggested_actions ?? [],
    turnIndex: r.turn_index,
    totalTurns: r.total_turns,
    finished: r.finished,
  };
}

// ---- Remediation ------------------------------------------------------------

interface ApiRemediationPlan {
  competency_id: string;
  detected_misconception: string | null;
  recommended_action: string;
  conceptual_focus: string;
  guided_question: string;
  remediation_steps: string[];
  consecutive_failures: number;
  total_attempts: number;
  summary_text: string;
}

export async function getRemediationPlan(competencyId: string): Promise<RemediationPlan> {
  const r = await apiGet<ApiRemediationPlan>(`/remediation/${competencyId}`);
  return {
    competencyId: r.competency_id,
    detectedMisconception: r.detected_misconception,
    recommendedAction: r.recommended_action,
    conceptualFocus: r.conceptual_focus,
    guidedQuestion: r.guided_question,
    remediationSteps: r.remediation_steps ?? [],
    consecutiveFailures: r.consecutive_failures,
    totalAttempts: r.total_attempts,
    summaryText: r.summary_text,
  };
}

// ---- Transfer ---------------------------------------------------------------

interface ApiTransferScenario {
  competency_id: string;
  scenario_id: string;
  title: string;
  domain: string;
  prompt: string;
  error_signal_meaning: string;
  control_output_meaning: string;
  system_inertia: string;
  conceptual_challenge: string;
}

interface ApiTransferEvaluation {
  competency_id: string;
  scenario_id: string;
  passed: boolean;
  matched_terms: string[];
  matched_count: number;
  min_required: number;
  feedback: string;
}

export async function getTransferScenario(
  competencyId: string,
  scenarioId?: string
): Promise<TransferScenario> {
  const qs = scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : '';
  const r = await apiGet<ApiTransferScenario>(`/transfer/${competencyId}${qs}`);
  return {
    competencyId: r.competency_id,
    scenarioId: r.scenario_id,
    title: r.title,
    domain: r.domain,
    prompt: r.prompt,
    errorSignalMeaning: r.error_signal_meaning,
    controlOutputMeaning: r.control_output_meaning,
    systemInertia: r.system_inertia,
    conceptualChallenge: r.conceptual_challenge,
  };
}

export async function submitTransferResponse(
  competencyId: string,
  responseText: string,
  scenarioId: string
): Promise<TransferEvaluation> {
  const r = await apiPost<ApiTransferEvaluation>(`/transfer/${competencyId}`, {
    response_text: responseText,
    scenario_id: scenarioId,
  });
  return {
    competencyId: r.competency_id,
    scenarioId: r.scenario_id,
    passed: r.passed,
    matchedTerms: r.matched_terms ?? [],
    matchedCount: r.matched_count,
    minRequired: r.min_required,
    feedback: r.feedback,
  };
}

// ---- Recommendation ------------------------------------------------------

// Derives what the student should do next based purely on client-side
// journey progress (which page they've completed) — this is UI navigation
// state, not mastery data, so it's kept here rather than in the backend.
export async function getRecommendation(
  flags: JourneyFlags,
  activeCompetencyName: string
): Promise<Recommendation> {
  let rec: Recommendation;

  if (!flags.hasCompletedDiagnostic) {
    rec = {
      id: 'rec-diagnostic',
      title: 'Start Diagnostic',
      reason: "Let's find out where you're already strong and where to focus first.",
      href: '/my-learning/diagnostic',
    };
  } else if (!flags.hasCompletedLearning) {
    rec = {
      id: 'rec-learning',
      title: 'Start Learning',
      reason: `Begin the ${activeCompetencyName} lesson to build your foundation.`,
      href: '/my-learning/learning',
    };
  } else if (!flags.hasCompletedPractice) {
    rec = {
      id: 'rec-practice',
      title: `Practice ${activeCompetencyName}`,
      reason: 'Apply what you just learned to a real task.',
      href: '/my-learning/practice',
    };
  } else if (!flags.hasCompletedSimulation) {
    rec = {
      id: 'rec-simulation',
      title: 'Launch Simulation',
      reason: 'See how your controller performs against the plant model.',
      href: '/apply-review/simulation',
    };
  } else if (!flags.hasCompletedReview) {
    rec = {
      id: 'rec-review',
      title: 'Review Your Evidence',
      reason: "See what you've demonstrated so far and what's still missing.",
      href: '/apply-review/review',
    };
  } else {
    rec = {
      id: 'rec-progress',
      title: 'View Your Progress',
      reason: 'Check your updated competency status.',
      href: '/progress/competency-profile',
    };
  }

  return rec;
}

// ---- Instructor (NEW) -----------------------------------------------------

interface ApiInstructorStudentSummary {
  student_id: string;
  display_name: string;
  course_code: string;
  course_title: string;
  overall_progress: number;
  competencies: ApiCompetency[];
}

interface ApiInstructorCompetencyAggregate {
  competency_id: string;
  competency_name: string;
  demonstrated: number;
  developing: number;
  needs_practice: number;
  not_started: number;
}

interface ApiInstructorClassSummary {
  total_students: number;
  average_overall_progress: number;
  students_demonstrated_all: number;
  students_with_failures: number;
}

interface ApiEvidenceEvent {
  timestamp: string;
  event_type: string;
  competency_id: string | null;
  title: string;
  detail: string;
  result: 'PASS' | 'FAIL' | 'INFO';
}

interface ApiInstructorStudentDetail extends ApiInstructorStudentSummary {
  evidence_timeline: ApiEvidenceEvent[];
}

function mapInstructorStudent(s: ApiInstructorStudentSummary): InstructorStudentSummary {
  return {
    studentId: s.student_id,
    displayName: s.display_name,
    courseCode: s.course_code,
    courseTitle: s.course_title,
    overallProgress: s.overall_progress,
    competencies: (s.competencies ?? []).map(mapCompetency),
  };
}

function mapEvidenceEvent(e: ApiEvidenceEvent): EvidenceEvent {
  return {
    timestamp: e.timestamp,
    eventType: e.event_type,
    competencyId: e.competency_id,
    title: e.title,
    detail: e.detail,
    result: e.result,
  };
}

export async function getInstructorClassSummary(): Promise<InstructorClassSummary> {
  const r = await apiGet<ApiInstructorClassSummary>('/instructor/summary');
  return {
    totalStudents: r.total_students,
    averageOverallProgress: r.average_overall_progress,
    studentsDemonstratedAll: r.students_demonstrated_all,
    studentsWithFailures: r.students_with_failures,
  };
}

export async function getInstructorCompetencyAggregate(): Promise<InstructorCompetencyAggregate[]> {
  const r = await apiGet<ApiInstructorCompetencyAggregate[]>('/instructor/aggregate');
  return r.map((c) => ({
    competencyId: c.competency_id,
    competencyName: c.competency_name,
    demonstrated: c.demonstrated,
    developing: c.developing,
    needsPractice: c.needs_practice,
    notStarted: c.not_started,
  }));
}

export async function getInstructorStudents(): Promise<InstructorStudentSummary[]> {
  const r = await apiGet<ApiInstructorStudentSummary[]>('/instructor/students');
  return r.map(mapInstructorStudent);
}

export async function getInstructorStudentDetail(
  studentId: string
): Promise<InstructorStudentDetail> {
  const r = await apiGet<ApiInstructorStudentDetail>(`/instructor/students/${studentId}`);
  return {
    ...mapInstructorStudent(r),
    evidenceTimeline: (r.evidence_timeline ?? []).map(mapEvidenceEvent),
  };
}

// ---- Evidence Timeline (NEW) -----------------------------------------------

export async function getMyEvidenceTimeline(): Promise<EvidenceEvent[]> {
  const r = await apiGet<ApiEvidenceEvent[]>('/evidence/me/timeline');
  return r.map(mapEvidenceEvent);
}

export async function getEvidenceTimeline(studentId: string): Promise<EvidenceEvent[]> {
  const r = await apiGet<ApiEvidenceEvent[]>(`/evidence/${studentId}/timeline`);
  return r.map(mapEvidenceEvent);
}

// ---- Auth (NEW) ------------------------------------------------------------
//
// signup/login/me — JWT-based auth. The token is stored in localStorage
// (see apiClient.ts) and automatically attached to every subsequent
// request via the Authorization header.

interface ApiAuthResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string;
  username: string;
  name: string;
  student_id: string;
  role: string;
}

function mapAuthResponse(r: ApiAuthResponse): AuthSession {
  // Persist the token immediately so subsequent requests are authenticated.
  setAuthToken(r.access_token);
  return {
    accessToken: r.access_token,
    tokenType: r.token_type as 'bearer',
    userId: r.user_id,
    email: r.email,
    username: r.username,
    name: r.name,
    studentId: r.student_id,
    role: (r.role === 'instructor' ? 'instructor' : 'student'),
  };
}

export async function signUp(req: SignUpRequest): Promise<AuthSession> {
  const r = await apiPost<ApiAuthResponse>('/auth/signup', {
    name: req.name,
    username: req.username,
    email: req.email,
    password: req.password,
  });
  return mapAuthResponse(r);
}

export async function login(req: LoginRequest): Promise<AuthSession> {
  const r = await apiPost<ApiAuthResponse>('/auth/login', {
    email: req.email,
    password: req.password,
  });
  return mapAuthResponse(r);
}

export async function getMe(): Promise<MeResponse> {
  const r = await apiGet<ApiMeResponse>('/auth/me');
  return {
    userId: r.user_id,
    email: r.email,
    username: r.username,
    name: r.name,
    studentId: r.student_id,
    studentDisplayName: r.student_display_name,
    role: (r.role === 'instructor' ? 'instructor' : 'student'),
  };
}

interface ApiMeResponse {
  user_id: number;
  email: string;
  username: string;
  name: string;
  student_id: string;
  student_display_name: string;
  role: string;
}

export function logout(): void {
  clearAuthToken();
}
