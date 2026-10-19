import {
  ArrowDownUp,
  ArrowRight,
  Check,
  CircleAlert,
  Database,
  Layers3,
  Radio,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { useHealth, useReadiness } from '../../services/health'
import { Button } from '../../components/ui/Button'

export function Overview() {
  const health = useHealth()
  const readiness = useReadiness()
  const checking = health.isFetching || readiness.isFetching
  const date = new Intl.DateTimeFormat(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date())

  return (
    <>
      <section className="page-heading">
        <div>
          <p className="eyebrow">YOUR OPERATIONS, CONNECTED</p>
          <h1>Workspace overview</h1>
          <p className="subheading">
            A clearer view of your retail business starts here.
          </p>
        </div>
        <span className="date-label">{date}</span>
      </section>
      <section className="welcome-panel" aria-labelledby="welcome-title">
        <div className="welcome-copy">
          <span className="pill">
            <span />
            WORKSPACE FOUNDATION
          </span>
          <h2 id="welcome-title">
            Everything you need.
            <br />
            One operational view.
          </h2>
          <p>
            Bring your stores, inventory, and sales together. Then turn real
            business evidence into informed action.
          </p>
          <div className="welcome-caption">
            <ShieldCheck size={16} />
            Real data. Clear evidence. Human approval.
          </div>
        </div>
        <div className="connection-map" aria-hidden="true">
          <div className="map-node">
            <Database size={24} />
            <span>Business data</span>
          </div>
          <div className="map-connector">
            <ArrowRight size={20} />
          </div>
          <div className="map-node map-center">
            <BoxesIcon />
            <span>RetailOps AI</span>
          </div>
          <div className="map-connector">
            <ArrowRight size={20} />
          </div>
          <div className="map-node">
            <Sparkles size={24} />
            <span>Better decisions</span>
          </div>
        </div>
      </section>
      <div className="section-heading">
        <div>
          <h2>Workspace connections</h2>
          <p>Live availability of your local services.</p>
        </div>
        <Button
          disabled={checking}
          onClick={() => {
            void health.refetch()
            void readiness.refetch()
          }}
        >
          <RefreshCw size={15} className={checking ? 'spin' : ''} />
          {checking ? 'Checking' : 'Refresh status'}
        </Button>
      </div>
      <div className="connection-grid" aria-live="polite">
        <ConnectionCard
          title="Operations service"
          icon="service"
          pending={health.isPending}
          available={health.isSuccess}
          description={
            health.isPending
              ? 'Checking service availability...'
              : health.isSuccess
                ? 'Connected and responding to requests.'
                : 'Unable to reach the operations service. Start the backend and refresh.'
          }
        />
        <ConnectionCard
          title="Business data"
          icon="database"
          pending={readiness.isPending}
          available={readiness.isSuccess}
          description={
            readiness.isPending
              ? 'Checking the data connection...'
              : readiness.isSuccess
                ? 'Database connection verified.'
                : 'Database connection unavailable. Operational data is not ready yet.'
          }
        />
        <article className="connection-card muted-card">
          <div className="card-top">
            <span className="card-icon">
              <Sparkles size={20} />
            </span>
            <span className="status-badge neutral">Not configured</span>
          </div>
          <h3>AI Companion</h3>
          <p>
            AI integration will be available after the core operations workspace
            is ready.
          </p>
          <span className="card-footnote">No model connected</span>
        </article>
      </div>
      <section className="operations-panel">
        <div className="operations-icon">
          <Layers3 size={24} />
        </div>
        <div>
          <p className="eyebrow">OPERATIONS AT A GLANCE</p>
          <h2>Your business view is taking shape.</h2>
          <p>
            Retail reporting is not available in this foundation release.
            Revenue, inventory, and purchasing metrics will appear when their
            database workflows are implemented.
          </p>
          <span className="empty-caption">
            <CircleAlert size={14} />
            No operational metrics are displayed yet.
          </span>
        </div>
      </section>
    </>
  )
}

function BoxesIcon() {
  return <Layers3 size={27} />
}

function ConnectionCard({
  title,
  description,
  pending,
  available,
  icon,
}: {
  title: string
  description: string
  pending: boolean
  available: boolean
  icon: 'service' | 'database'
}) {
  return (
    <article className="connection-card">
      <div className="card-top">
        <span className="card-icon">
          {icon === 'service' ? <Radio size={20} /> : <Database size={20} />}
        </span>
        <span
          className={`status-badge ${pending ? 'neutral' : available ? 'success' : 'warning'}`}
        >
          {pending ? (
            <RefreshCw size={11} className="spin" />
          ) : available ? (
            <Check size={11} />
          ) : (
            <CircleAlert size={11} />
          )}
          {pending ? 'Checking' : available ? 'Connected' : 'Unavailable'}
        </span>
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      <span className="card-footnote">
        <ArrowDownUp size={12} />
        Live service check
      </span>
    </article>
  )
}
