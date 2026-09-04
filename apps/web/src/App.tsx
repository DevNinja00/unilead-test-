import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Navbar from './components/layout/Navbar';

import SignUp from './pages/SignUp';
import Login from './pages/Login';
import Onboarding from './pages/Onboarding';
import Home from './pages/Home';
import MyLearning from './pages/MyLearning';
import Diagnostic from './pages/Diagnostic';
import DiagnosticResults from './pages/DiagnosticResults';
import Learning from './pages/Learning';
import AICoach from './pages/AICoach';
import Practice from './pages/Practice';
import Remediation from './pages/Remediation';
import ApplyReview from './pages/ApplyReview';
import Simulation from './pages/Simulation';
import Review from './pages/Review';
import Transfer from './pages/Transfer';
import EvidenceTimeline from './pages/EvidenceTimeline';
import ProgressHub from './pages/ProgressHub';
import ProgressOverview from './pages/ProgressOverview';
import CompetencyProfile from './pages/CompetencyProfile';
import Profile from './pages/Profile';
import InstructorDashboard from './pages/InstructorDashboard';
import InstructorStudentDetail from './pages/InstructorStudentDetail';

// Routes that render full-bleed, without the main Navbar (auth/onboarding flow).
const NO_NAVBAR_ROUTES = ['/', '/signup', '/login', '/onboarding'];

function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const showNavbar = !NO_NAVBAR_ROUTES.includes(location.pathname);

  return (
    <>
      {showNavbar && <Navbar />}
      {children}
    </>
  );
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/signup" replace />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/login" element={<Login />} />
        <Route path="/onboarding" element={<Onboarding />} />

        <Route path="/home" element={<Home />} />

        <Route path="/my-learning" element={<MyLearning />} />
        <Route path="/my-learning/diagnostic" element={<Diagnostic />} />
        <Route path="/my-learning/diagnostic-results" element={<DiagnosticResults />} />
        <Route path="/my-learning/learning" element={<Learning />} />
        <Route path="/my-learning/ai-coach" element={<AICoach />} />
        <Route path="/my-learning/practice" element={<Practice />} />
        <Route path="/my-learning/remediation" element={<Remediation />} />

        <Route path="/apply-review" element={<ApplyReview />} />
        <Route path="/apply-review/simulation" element={<Simulation />} />
        <Route path="/apply-review/transfer" element={<Transfer />} />
        <Route path="/apply-review/evidence-timeline" element={<EvidenceTimeline />} />
        <Route path="/apply-review/review" element={<Review />} />

        <Route path="/progress" element={<ProgressHub />} />
        <Route path="/progress/overview" element={<ProgressOverview />} />
        <Route path="/progress/competency-profile" element={<CompetencyProfile />} />

        <Route path="/profile" element={<Profile />} />

        {/* Instructor-only views */}
        <Route path="/instructor" element={<InstructorDashboard />} />
        <Route path="/instructor/students/:studentId" element={<InstructorStudentDetail />} />

        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
    </Layout>
  );
}
