import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import { useApp } from '../state/AppContext';
import { signUp, getStudent } from '../data/mockApi';
import './SignUp.css';

export default function SignUp() {
  const navigate = useNavigate();
  const { setStudent, setSession } = useApp();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string; form?: string }>({});
  const [loading, setLoading] = useState(false);

  function validate() {
    const next: typeof errors = {};
    if (!name.trim()) next.name = 'Please enter your name.';
    if (!email.trim()) next.email = 'Please enter your email.';
    else if (!/^\S+@\S+\.\S+$/.test(email)) next.email = 'Enter a valid email address.';
    if (password.length < 8) next.password = 'Password must be at least 8 characters.';
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setErrors({});
    try {
      // 1. Sign up via the real backend endpoint.
      const session = await signUp({
        name: name.trim(),
        email: email.trim(),
        password,
      });
      setSession(session);

      // 2. Load the freshly-seeded student state.
      const student = await getStudent();
      setStudent({ ...student, name: session.name, email: session.email });
      navigate('/onboarding');
    } catch (err) {
      setErrors({
        form: err instanceof Error ? err.message : 'Could not create account. Please try again.',
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="signup">
      <div className="signup__panel">
        <div className="signup__brand">
          <span className="signup__brand-mark">◆</span> Compass
        </div>
        <h2 className="signup__headline">Build real, demonstrated skill.</h2>
        <p className="signup__subtext muted">
          A competency-based way to learn — you move forward by showing what you can actually do,
          not just by finishing videos.
        </p>
      </div>

      <div className="signup__form-side">
        <Card padding="lg" className="signup__card">
          <h1 className="signup__title">Create your account</h1>
          <p className="muted signup__lede">Start your learning journey in under a minute.</p>

          {errors.form && <div className="signup__error">{errors.form}</div>}

          <form onSubmit={handleSubmit} className="signup__form" noValidate>
            <Input
              label="Full name"
              placeholder="e.g. Mariam Hassan"
              value={name}
              onChange={(e) => setName(e.target.value)}
              error={errors.name}
            />
            <Input
              label="Email"
              type="email"
              placeholder="you@university.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={errors.email}
            />
            <Input
              label="Password"
              type="password"
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={errors.password}
            />
            <Button type="submit" fullWidth size="lg" loading={loading}>
              Create Account
            </Button>
          </form>

          <p className="muted signup__alt">
            Already have an account? <Link to="/login">Log in</Link>
          </p>

          <p className="muted signup__demo-hint">
            Or try the demo: <code>mariam@student.aiu.edu.eg</code> / <code>demo1234</code>
          </p>
        </Card>
      </div>
    </div>
  );
}
