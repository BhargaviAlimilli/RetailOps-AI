import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Navigate, useNavigate } from 'react-router'
import { ArrowRight, Layers3, ShieldCheck } from 'lucide-react'
import { login, loginSchema, type LoginInput } from '../../services/auth'
import {
  selectUser,
  sessionEstablished,
  useAppDispatch,
  useAppSelector,
} from '../../store'
import './auth.css'

export function LoginPage() {
  const user = useAppSelector(selectUser)
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) })
  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (session) => {
      queryClient.clear()
      dispatch(sessionEstablished(session))
      navigate('/', { replace: true })
    },
  })
  if (user) return <Navigate to="/" replace />
  return (
    <main className="auth-page">
      <section className="auth-story" aria-label="RetailOps AI">
        <a className="auth-brand" href="/login">
          <Layers3 size={30} /> RetailOps <span>AI</span>
        </a>
        <div>
          <p className="auth-kicker">YOUR RETAIL OPERATING SYSTEM</p>
          <h1>
            Good decisions.
            <br />
            Better retail.
          </h1>
          <p>
            Bring your inventory, sales, and purchasing together. Get a clear
            view of your business and take the next step with confidence.
          </p>
        </div>
        <p className="auth-assurance">
          <ShieldCheck size={18} /> Role-based access. Your team, connected.
        </p>
      </section>
      <section className="auth-panel">
        <div className="auth-form-wrap">
          <p className="auth-kicker">WELCOME TO YOUR WORKSPACE</p>
          <h2>Sign in to RetailOps</h2>
          <p className="auth-intro">Your operations, all in one place.</p>
          <form
            onSubmit={handleSubmit((input) => mutation.mutate(input))}
            noValidate
          >
            <label htmlFor="email">Work email</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              placeholder="you@company.com"
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? 'email-error' : undefined}
              {...register('email')}
            />
            {errors.email && (
              <p className="auth-error" id="email-error">
                {errors.email.message}
              </p>
            )}
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              aria-describedby={errors.password ? 'password-error' : undefined}
              {...register('password')}
            />
            {errors.password && (
              <p className="auth-error" id="password-error">
                {errors.password.message}
              </p>
            )}
            {mutation.isError && (
              <p className="auth-error auth-banner" role="alert">
                {mutation.error.message}
              </p>
            )}
            <button
              className="auth-submit"
              type="submit"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? 'Signing in...' : 'Sign in'}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="auth-help">
            Use an account configured by your administrator. Demo accounts are
            provided separately by your administrator.
          </p>
          <a className="auth-status" href="/system">
            View system connection status <ArrowRight size={14} />
          </a>
        </div>
        <p className="auth-footer">
          RETAILOPS AI - A CLEARER VIEW OF YOUR BUSINESS
        </p>
      </section>
    </main>
  )
}
