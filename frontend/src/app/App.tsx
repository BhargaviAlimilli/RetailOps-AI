import { Link, Route, Routes } from 'react-router'
import { AppShell } from '../components/layout/AppShell'
import { Overview } from '../features/dashboard/Overview'

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route
          path="*"
          element={
            <section className="not-found">
              <p className="eyebrow">PAGE NOT FOUND</p>
              <h1>This page is unavailable.</h1>
              <Link to="/">Return to overview</Link>
            </section>
          }
        />
      </Routes>
    </AppShell>
  )
}
