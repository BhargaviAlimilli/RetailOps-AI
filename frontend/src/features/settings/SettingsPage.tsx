import { Link } from 'react-router'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { PageHeading, Panel } from '../retail/shared'
import '../retail/retail.css'

export function SettingsPage() {
  const { user } = useAuth()
  return (
    <>
      <PageHeading
        title="Settings"
        description="Your account and workspace access."
      />
      <Panel title="Signed-in account">
        <dl className="account-details">
          <dt>Name</dt>
          <dd>{user?.name}</dd>
          <dt>Email</dt>
          <dd>{user?.email}</dd>
          <dt>Role</dt>
          <dd>{user?.role}</dd>
        </dl>
        <p className="subheading">
          Your session is held in this browser tab. Refreshing the page requires
          signing in again.
        </p>
      </Panel>
      <Panel title="Team permissions">
        <p className="subheading">
          <ShieldCheck size={16} /> Analysts can view operational data. Managers
          and administrators can create products, adjust stock, and explicitly
          approve purchase orders.
        </p>
        <p className="subheading">
          Approval records and stock changes retain the responsible account and
          an audit history.
        </p>
      </Panel>
      <Panel title="Workspace availability">
        <p className="subheading">
          Review your operations service and business data connection.
        </p>
        <Link className="button" to="/system">
          View connection status
        </Link>
      </Panel>
    </>
  )
}
