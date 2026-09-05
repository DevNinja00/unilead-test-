import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import { useApp } from '../state/AppContext';
import { verifyEmail, resendVerificationCode, getStudent } from '../data/mockApi';
import { ApiError } from '../data/apiClient';
import './SignUp.css';

const RESEND_COOLDOWN_SECONDS = 60;

export default function VerifyEmail() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setStudent, setSession } = useApp();
  const emailParam = searchParams.get('email') ?? '';

  const [email, setEmail] = useState(emailParam);
  const [code, setCode] = useState('');
  const [errors, setErrors] = useState<{ form?: string; code?: string }>({});
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(
    emailParam ? RESEND_COOLDOWN_SECONDS : 0
  );

  // Count down the resend cooldown that the backend just started for us.
  useEffect(() => {
    if (resendCountdown <= 0) return;
    const timer = setInterval(() => setResendCountdown((s) => s - 1), 1000);
    return () => clearInterval(timer);
  }, [resendCountdown]);

  async function handleVerify(e: FormEvent) {
    e.preventDefault();
    setErrors({});
    setInfo(null);
    if (!email.trim()) {
      setErrors({ form: 'Please enter your email.' });
      return;
    }
    if (!code.trim()) {
      setErrors({ code: 'Please enter the code from your email.' });
      return;
    }
    setLoading(true);
    try {
      const session = await verifyEmail({ email: email.trim(), code: code.trim() });
      setSession(session);

      // Load the freshly-seeded student state — verify is now what issues
      // the session, so onboarding starts here just like signup used to.
      const student = await getStudent();
      setStudent({ ...student, name: session.name, email: session.email });
      navigate('/onboarding');
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setErrors({ code: err.message.replace(/^Request failed \(\d+\):\s*/, '') });
      } else {
        setErrors({
          form: err instanceof Error ? err.message : 'Could not verify your email. Please try again.',
        });
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setErrors({});
    setInfo(null);
    if (!email.trim()) {
      setErrors({ form: 'Please enter your email.' });
      return;
    }
    setResending(true);
    try {
      const r = await resendVerificationCode(email.trim());
      setCode('');
      setInfo(`A new code was sent to ${r.email}.`);
      setResendCountdown(r.resendAfterSeconds + 1 || RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setErrors({ form: err.message.replace(/^Request failed \(\d+\):\s*/, '') });
      } else {
        setErrors({
          form:
            err instanceof Error ? err.message : 'Could not resend the code. Please try again.',
        });
      }
    } finally {
      setResending(false);
    }
  }

  const canResend = resendCountdown <= 0;

  return (
    <div className="signup">
      <div className="signup__panel">
        <div className="signup__brand">
          <span className="signup__brand-mark">◆</span> Compass
        </div>
        <h2 className="signup__headline">One more step.</h2>
        <p className="signup__subtext muted">
          We emailed a 6-digit verification code to your university address. Enter it below to
          activate your account — it's how we keep Compass open to students only.
        </p>
      </div>

      <div className="signup__form-side">
        <Card padding="lg" className="signup__card">
          <h1 className="signup__title">Verify your email</h1>
          <p className="muted signup__lede">
            Check your inbox (and spam folder) for the code.
          </p>

          {errors.form && <div className="signup__error">{errors.form}</div>}
          {info && <div className="signup__success">{info}</div>}

          <form onSubmit={handleVerify} className="signup__form" noValidate>
            <Input
              label="Email"
              type="email"
              placeholder="you@university.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Verification code"
              placeholder="6-digit code"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              error={errors.code}
            />
            <Button type="submit" fullWidth size="lg" loading={loading}>
              Verify & Continue
            </Button>
          </form>

          <p className="muted signup__alt" style={{ marginTop: 16 }}>
            {canResend ? (
              <>
                Didn't get it?{' '}
                <button
                  type="button"
                  className="signup__link-button"
                  onClick={handleResend}
                  disabled={resending}
                >
                  {resending ? 'Sending…' : 'Resend the code'}
                </button>
              </>
            ) : (
              <>Resend available in {resendCountdown}s</>
            )}
          </p>

          <p className="muted signup__alt">
            New here? <Link to="/signup">Create an account</Link>
          </p>
        </Card>
      </div>
    </div>
  );
}