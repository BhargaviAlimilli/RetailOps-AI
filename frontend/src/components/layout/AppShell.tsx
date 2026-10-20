import { useState } from 'react'
import { NavLink, useLocation } from 'react-router'
import {
  ArrowUpRight,
  BarChart3,
  Boxes,
  Building2,
  ChevronRight,
  FileText,
  LayoutDashboard,
  Menu,
  Package,
  Settings2,
  ShoppingCart,
  Sparkles,
  X,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '../ui/Button'
import { useAuth } from '../../features/auth/AuthProvider'

const upcoming = [
  { label: 'Sales Analytics', icon: BarChart3, path: '/sales' },
  { label: 'Inventory', icon: Boxes, path: '/inventory' },
  { label: 'Products', icon: Package, path: '/products' },
  { label: 'Suppliers', icon: Building2, path: '/suppliers' },
  { label: 'Purchase Orders', icon: ShoppingCart, path: '/purchase-orders' },
  { label: 'Documents', icon: FileText, path: '/documents' },
  { label: 'AI Companion', icon: Sparkles, path: '/assistant' },
  { label: 'Agent Workflows', icon: Sparkles, path: '/agents' },
  { label: 'Component Showcase', icon: LayoutDashboard, path: '/showcase' },
  { label: 'Settings', icon: Settings2, path: '/settings' },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth()
  const location = useLocation()
  const title = plannedTitle(location.pathname)
  const [navigationOpen, setNavigationOpen] = useState(false)
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="mobile-bar">
        <span className="mobile-brand">
          RetailOps<span> AI</span>
        </span>
        <Button
          aria-label={navigationOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={navigationOpen}
          aria-controls="sidebar"
          onClick={() => setNavigationOpen(!navigationOpen)}
        >
          {navigationOpen ? <X size={19} /> : <Menu size={19} />}
        </Button>
      </div>
      <aside
        id="sidebar"
        className={`sidebar ${navigationOpen ? 'is-open' : ''}`}
      >
        <NavLink
          className="brand"
          to="/"
          onClick={() => setNavigationOpen(false)}
        >
          <span className="brand-mark">
            <Boxes size={23} strokeWidth={1.6} />
          </span>
          <span>
            RetailOps<span className="brand-ai"> AI</span>
            <small>OPERATIONS WORKSPACE</small>
          </span>
        </NavLink>
        <div className="workspace-switch">
          <span className="workspace-avatar">R</span>
          <div>
            Retail workspace<small>Demo environment</small>
          </div>
          <ChevronRight size={16} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          <NavLink
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            to="/"
            end
            onClick={() => setNavigationOpen(false)}
          >
            <LayoutDashboard size={18} />
            Overview
            <span className="active-dot" />
          </NavLink>
          {upcoming.map(({ label, icon: Icon, path }) =>
            path ? (
              <NavLink
                key={label}
                to={path}
                className={({ isActive }) =>
                  `nav-item ${isActive ? 'active' : ''}`
                }
                onClick={() => setNavigationOpen(false)}
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ) : (
              <span
                key={label}
                className="nav-item planned"
                aria-disabled="true"
                title="Planned module"
              >
                <Icon size={18} />
                <span>{label}</span>
                <small>Planned</small>
              </span>
            ),
          )}
        </nav>
        <div className="sidebar-note">
          <span className="note-icon">
            <Sparkles size={17} />
          </span>
          <strong>Built for better decisions.</strong>
          <p>
            Sales, stock, and supplier knowledge in one connected workspace.
          </p>
          <span className="preview-label">
            Portfolio demonstration <ArrowUpRight size={13} />
          </span>
        </div>
        {user && (
          <div className="sidebar-account">
            <span className="workspace-avatar">{user.name.slice(0, 1)}</span>
            <div>
              <strong>{user.name}</strong>
              <small>{user.role}</small>
            </div>
            <button
              className="signout-button"
              onClick={() => {
                void signOut().catch(() => {})
              }}
            >
              Sign out
            </button>
          </div>
        )}
        <footer className="sidebar-footer">
          <span className="environment-dot" />
          Demo workspace<span>v0.1</span>
        </footer>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <strong>{title}</strong>
          </div>
          <span className="preview-badge">
            {user?.email.endsWith('@retailops.demo')
              ? 'SYNTHETIC DEMO'
              : 'DEVELOPMENT PREVIEW'}
          </span>
        </header>
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
        <footer className="main-footer">
          RetailOps AI<span>Evidence behind every decision.</span>
        </footer>
      </div>
    </div>
  )
}

function plannedTitle(path: string) {
  if (path === '/system') return 'Connection status'
  return upcoming.find((item) => item.path === path)?.label ?? 'Overview'
}
