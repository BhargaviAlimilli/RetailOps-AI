import { Link, Route, Routes } from 'react-router'
import { AppShell } from '../components/layout/AppShell'
import { Overview } from '../features/dashboard/Overview'
import { LoginPage } from '../features/auth/LoginPage'
import { RequireAuth } from '../features/auth/RequireAuth'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/system"
        element={
          <AppShell>
            <Overview />
          </AppShell>
        }
      />
      <Route element={<RequireAuth />}>
        <Route
          path="/"
          element={
            <AppShell>
              <Overview />
            </AppShell>
          }
        />
      </Route>
      <Route
        path="*"
        element={
          <AppShell>
            <section className="not-found">
              <p className="eyebrow">PAGE NOT FOUND</p>
              <h1>This page is unavailable.</h1>
              <Link to="/">Return to overview</Link>
            </section>
          </AppShell>
        }
      />
    </Routes>
  )
}
