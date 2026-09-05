import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Navbar from './components/layout/Navbar';
import { ProtectedRoute, InstructorRoute } from './components/auth/ProtectedRoute';
import NotFound from './pages/NotFound';

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
        <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />

        {/* Protected routes — require authentication */}
        <Route path="/home" element={<ProtectedRoute><Home /></ProtectedRoute>} />

        <Route path="/my-learning" element={<ProtectedRoute><MyLearning /></ProtectedRoute>} />
        <Route path="/my-learning/diagnostic" element={<ProtectedRoute><Diagnostic /></ProtectedRoute>} />
        <Route path="/my-learning/diagnostic-results" element={<ProtectedRoute><DiagnosticResults /></ProtectedRoute>} />
        <Route path="/my-learning/learning" element={<ProtectedRoute><Learning /></ProtectedRoute>} />
        <Route path="/my-learning/ai-coach" element={<ProtectedRoute><AICoach /></ProtectedRoute>} />
        <Route path="/my-learning/practice" element={<ProtectedRoute><Practice /></ProtectedRoute>} />
        <Route path="/my-learning/remediation" element={<ProtectedRoute><Remediation /></ProtectedRoute>} />

        <Route path="/apply-review" element={<ProtectedRoute><ApplyReview /></ProtectedRoute>} />
        <Route path="/apply-review/simulation" element={<ProtectedRoute><Simulation /></ProtectedRoute>} />
        <Route path="/apply-review/transfer" element={<ProtectedRoute><Transfer /></ProtectedRoute>} />
        <Route path="/apply-review/evidence-timeline" element={<ProtectedRoute><EvidenceTimeline /></ProtectedRoute>} />
        <Route path="/apply-review/review" element={<ProtectedRoute><Review /></ProtectedRoute>} />

        <Route path="/progress" element={<ProtectedRoute><ProgressHub /></ProtectedRoute>} />
        <Route path="/progress/overview" element={<ProtectedRoute><ProgressOverview /></ProtectedRoute>} />
        <Route path="/progress/competency-profile" element={<ProtectedRoute><CompetencyProfile /></ProtectedRoute>} />

        <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />

        {/* Instructor-only views — require auth + instructor role */}
        <Route path="/instructor" element={<InstructorRoute><InstructorDashboard /></InstructorRoute>} />
        <Route path="/instructor/students/:studentId" element={<InstructorRoute><InstructorStudentDetail /></InstructorRoute>} />

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
