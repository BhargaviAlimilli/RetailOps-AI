import { lazy, Suspense } from 'react'
import { Link, Outlet, Route, Routes } from 'react-router'
import { AppShell } from '../components/layout/AppShell'
import { Overview } from '../features/dashboard/Overview'
import { LoginPage } from '../features/auth/LoginPage'
import { RequireAuth } from '../features/auth/RequireAuth'
const AssistantPage = lazy(() => import('../features/assistant/AssistantPage'))
const RetailDashboard = lazy(() =>
  import('../features/retail/Dashboard').then((module) => ({
    default: module.RetailDashboard,
  })),
)
const SalesPage = lazy(() =>
  import('../features/retail/Sales').then((module) => ({
    default: module.SalesPage,
  })),
)
const ProductsPage = lazy(() =>
  import('../features/retail/Catalog').then((module) => ({
    default: module.ProductsPage,
  })),
)
const SuppliersPage = lazy(() =>
  import('../features/retail/Catalog').then((module) => ({
    default: module.SuppliersPage,
  })),
)
const InventoryPage = lazy(() =>
  import('../features/retail/Inventory').then((module) => ({
    default: module.InventoryPage,
  })),
)
const PurchaseOrdersPage = lazy(() =>
  import('../features/retail/PurchaseOrders').then((module) => ({
    default: module.PurchaseOrdersPage,
  })),
)
import { SettingsPage } from '../features/settings/SettingsPage'

function WorkspaceLayout() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <p role="status" className="retail-state">
            Opening workspace...
          </p>
        }
      >
        <Outlet />
      </Suspense>
    </AppShell>
  )
}

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
        <Route element={<WorkspaceLayout />}>
          <Route path="/" element={<RetailDashboard />} />
          <Route path="/sales" element={<SalesPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/assistant" element={<AssistantPage />} />
        </Route>
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
