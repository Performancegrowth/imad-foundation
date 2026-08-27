// Auth screen — unified Login / Sign-up form backed by the JWT API.
import { useState } from 'react'
import { login, register } from '../platformApi.js'

export default function AuthWorkspace({ mode = 'login', onDone }) {
  const [mode_, setMode] = useState(mode) // switchable without remount
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const isLogin = mode_ === 'login'

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    if (!isLogin && !fullName.trim()) {
      setErr('Please enter your full name.')
      return
    }
    if (!email.trim() || !password) {
      setErr('Email and password are required.')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setErr('Please enter a valid email address.')
      return
    }
    if (!isLogin && password.length < 8) {
      setErr('Password must be at least 8 characters.')
      return
    }
    setBusy(true)
    try {
      if (isLogin) {
        await login(email.trim(), password) // platformApi stores the token
      } else {
        // Backend requires full_name and returns {token:{access_token}} —
        // platformApi.register normalizes it and stores the token for us.
        const data = await register({
          email: email.trim(),
          password,
          full_name: fullName.trim(),
        })
        if (!data?.access_token) throw new Error(data?.detail || 'Registration failed.')
      }
      onDone?.()
    } catch (ex) {
      setErr(ex.message || 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card" aria-labelledby="auth-heading">
        <h2 id="auth-heading">{isLogin ? 'Log in to Imad' : 'Create your Imad account'}</h2>
        <p className="muted">
          {isLogin
            ? 'Access your projects, analysis and BOQ tools.'
            : 'Free tier: one project to evaluate the full workflow.'}
        </p>
        {err && <p className="form-error" role="alert">{err}</p>}
        <form onSubmit={submit} noValidate>
          {!isLogin && (
            <div className="field">
              <label htmlFor="auth-name">Full name</label>
              <input
                id="auth-name" type="text" autoComplete="name" required
                value={fullName} onChange={(e) => setFullName(e.target.value)}
                placeholder="Eng. Your Name"
              />
            </div>
          )}
          <div className="field">
            <label htmlFor="auth-email">Email</label>
            <input
              id="auth-email" type="email" autoComplete="email" required
              value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </div>
          <div className="field">
            <label htmlFor="auth-pass">Password</label>
            <input
              id="auth-pass" type="password" required
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder={isLogin ? 'Your password' : 'At least 8 characters'}
            />
          </div>
          <div className="auth-actions-row">
            <button type="submit" className="btn primary" disabled={busy} aria-busy={busy}>
              {busy ? 'Please wait…' : isLogin ? 'Log in' : 'Create account'}
            </button>
          </div>
        </form>
        <p className="auth-alt">
          {isLogin ? "Don't have an account? " : 'Already have an account? '}
          <button type="button" onClick={() => { setErr(''); setMode(isLogin ? 'register' : 'login') }}>
            {isLogin ? 'Sign up free' : 'Log in'}
          </button>
        </p>
      </div>
    </div>
  )
}
