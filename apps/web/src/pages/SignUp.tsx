import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import { signUp } from '../data/mockApi';
import './SignUp.css';

export default function SignUp() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ name?: string; username?: string; email?: string; password?: string; form?: string }>({});
  const [loading, setLoading] = useState(false);

  // Mirror the backend rule in schemas/auth.py (UNIVERSITY_EMAIL_DOMAIN_RE):
  // the domain must end with .edu, .edu.<cc>, or .ac.<cc> and nothing else.
  function isUniversityEmail(value: string): boolean {
    const domain = value.split('@').pop()?.toLowerCase() ?? '';
    return /^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.(?:edu|edu\.[a-z]{2}|ac\.[a-z]{2})$/.test(domain);
  }

  function validate() {
    const next: typeof errors = {};
    if (!name.trim()) next.name = 'Please enter your name.';
    else if (name.trim().length > 255) next.name = 'Name must be 255 characters or fewer.';
    else if (!/\p{L}/u.test(name.trim())) next.name = 'Name must contain at least one letter.';
    if (!username.trim()) next.username = 'Please enter a username.';
    else if (username.length < 3) next.username = 'Username must be at least 3 characters.';
    else if (username.length > 50) next.username = 'Username must be 50 characters or fewer.';
    else if (!/^[a-zA-Z0-9_]+$/.test(username)) next.username = 'Only letters, numbers, and underscores allowed.';
    if (!email.trim()) next.email = 'Please enter your email.';
    else if (!/^\S+@\S+\.\S+$/.test(email)) next.email = 'Enter a valid email address.';
    else if (!isUniversityEmail(email)) next.email = 'Use your university email (e.g. you@university.edu, you@cu.edu.eg, or you@university.ac.uk).';
    if (password.length < 8) next.password = 'Password must be at least 8 characters.';
    else {
      // Mirror the backend policy in schemas/auth.py so validation fails fast
      // with a friendly message instead of a generic 422.
      const missing: string[] = [];
      if (!/[A-Z]/.test(password)) missing.push('an uppercase letter');
      if (!/[a-z]/.test(password)) missing.push('a lowercase letter');
      if (!/\d/.test(password)) missing.push('a digit');
      if (!/[!@#$%^&*()_+\-=[\]{}|;:,.<>?]/.test(password)) missing.push('a special character');
      if (missing.length) next.password = `Password must contain ${missing.join(', ')}.`;
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setErrors({});
    try {
      // 1. Sign up via the real backend endpoint — this returns a
      // "verification required" result (no JWT yet); a 6-digit code is
      // emailed to the address and must be entered on the verify page.
      const result = await signUp({
        name: name.trim(),
        username: username.trim(),
        email: email.trim(),
        password,
      });

      // 2. Route to the verification screen; no session exists until the
      // code is entered there.
      navigate(`/verify-email?email=${encodeURIComponent(result.email)}`);
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
              label="Username"
              placeholder="e.g. mariam_h"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              error={errors.username}
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
        </Card>
      </div>
    </div>
  );
}
