import { useState } from 'react'
import { NavLink } from 'react-router'
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

const upcoming = [
  { label: 'Sales Analytics', icon: BarChart3 },
  { label: 'Inventory', icon: Boxes },
  { label: 'Products', icon: Package },
  { label: 'Suppliers', icon: Building2 },
  { label: 'Purchase Orders', icon: ShoppingCart },
  { label: 'Documents', icon: FileText },
  { label: 'AI Companion', icon: Sparkles },
  { label: 'Settings', icon: Settings2 },
]

export function AppShell({ children }: { children: ReactNode }) {
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
            Retail workspace<small>Local environment</small>
          </div>
          <ChevronRight size={16} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          <NavLink
            className="nav-item active"
            to="/"
            end
            onClick={() => setNavigationOpen(false)}
          >
            <LayoutDashboard size={18} />
            Overview
            <span className="active-dot" />
          </NavLink>
          {upcoming.map(({ label, icon: Icon }) => (
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
          ))}
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
            Development preview <ArrowUpRight size={13} />
          </span>
        </div>
        <footer className="sidebar-footer">
          <span className="environment-dot" />
          Local workspace<span>v0.1</span>
        </footer>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <strong>Overview</strong>
          </div>
          <span className="preview-badge">DEVELOPMENT PREVIEW</span>
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
