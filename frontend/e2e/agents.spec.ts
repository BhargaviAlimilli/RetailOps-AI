import { existsSync, readFileSync } from 'node:fs'
import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from '@playwright/test'
import { z } from 'zod'
import {
  inventorySchema,
  purchaseOrderSchema,
  supplierSchema,
} from '../src/services/retail'
const envPath = new URL('../../backend/.env', import.meta.url)
const localEnv = existsSync(envPath) ? readFileSync(envPath, 'utf8') : ''
const password =
  process.env.RETAILOPS_DEMO_PASSWORD ??
  localEnv.match(/^RETAILOPS_DEMO_PASSWORD=(.+)$/m)?.[1]?.trim()
test.skip(
  !password,
  'Configure and seed the ignored local synthetic demo password before browser verification',
)
async function signIn(page: Page) {
  await page.goto('/login')
  await page.getByLabel('Work email').fill('manager@retailops.demo')
  await page.getByLabel('Password', { exact: true }).fill(password!)
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/auth/login') &&
      response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  const result = await response
  expect(result.status()).toBe(200)
  const session = await result.json()
  await expect(
    page.getByRole('heading', { name: 'Business overview', exact: true }),
  ).toBeVisible()
  return { Authorization: `Bearer ${session.access_token}` }
}
async function navigate(page: Page, name: string) {
  const toggle = page.getByRole('button', { name: 'Open navigation' })
  if (await toggle.isVisible()) await toggle.click()
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name, exact: true })
    .click()
}
async function prepareScreenshot(page: Page) {
  const close = page.getByRole('button', {
    name: 'Close navigation',
    exact: true,
  })
  if (await close.isVisible()) await close.click()
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur()
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  })
  await page.waitForFunction(() => {
    const sidebar = document.querySelector('#sidebar')
    return (
      scrollY === 0 &&
      (innerWidth > 700 ||
        !sidebar ||
        getComputedStyle(sidebar).position !== 'fixed' ||
        sidebar.getBoundingClientRect().right <= 0)
    )
  })
}
async function pages<T>(
  request: APIRequestContext,
  path: string,
  headers: Record<string, string>,
  schema: z.ZodType<T>,
) {
  const all: T[] = []
  for (let page = 1; page <= 1000; page++) {
    const response = await request.get(
      `${path}${path.includes('?') ? '&' : '?'}page_size=100&page=${page}`,
      { headers },
    )
    expect(response.status()).toBe(200)
    const result = z
      .object({ items: z.array(schema), total: z.number() })
      .parse(await response.json())
    all.push(...result.items)
    if (all.length >= result.total) return all
  }
  throw new Error('Unexpectedly large demo dataset')
}

test('manager reviews a real replenishment interrupt and explicitly approves its pending order', async ({
  page,
  request,
}, info) => {
  test.setTimeout(90000)
  const headers = await signIn(page)
  const status = await request.get('/api/v1/ai/status', { headers })
  expect(status.status()).toBe(200)
  expect(
    (await status.json()).document_retrieval,
    'This cost-free workflow check requires RAG disabled',
  ).toBe(false)
  const inventory = await pages(
    request,
    '/api/v1/inventory',
    headers,
    inventorySchema,
  )
  const pending = await pages(
    request,
    '/api/v1/purchase-orders?status=pending',
    headers,
    purchaseOrderSchema,
  )
  const approved = await pages(
    request,
    '/api/v1/purchase-orders?status=approved',
    headers,
    purchaseOrderSchema,
  )
  const supplierResponse = await request.get('/api/v1/suppliers', { headers })
  expect(supplierResponse.status()).toBe(200)
  const suppliers = z.array(supplierSchema).parse(await supplierResponse.json())
  const open = new Set(
    [...pending, ...approved].flatMap((order) =>
      order.items.map((item) => `${order.store_id}:${item.product_id}`),
    ),
  )
  const candidates = inventory
    .filter(
      (item) =>
        item.available < item.reorder_point &&
        !open.has(`${item.store_id}:${item.product_id}`),
    )
    .sort((a, b) => a.available - b.available)
  const balance = candidates.find((item) =>
    suppliers.some((supplier) =>
      supplier.terms.some((term) => term.product_id === item.product_id),
    ),
  )
  expect(
    balance,
    'Seeded low-stock balance without inbound orders is required; no stock is force-adjusted by this test',
  ).toBeTruthy()
  if (!balance) throw new Error('No eligible synthetic stock balance')
  const supplier = suppliers.find((item) =>
    item.terms.some((term) => term.product_id === balance.product_id),
  )!
  await navigate(page, 'Agent Workflows')
  await expect(
    page.getByRole('heading', { name: 'Replenishment agent', exact: true }),
  ).toBeVisible()
  await page
    .getByRole('combobox', { name: 'Store', exact: true })
    .selectOption(balance.store_id)
  await page
    .getByRole('combobox', { name: 'Product', exact: true })
    .selectOption(balance.product_id)
  await page
    .getByRole('combobox', { name: 'Supplier', exact: true })
    .selectOption(supplier.id)
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/agents/runs') &&
      response.request().method() === 'POST',
  )
  await page
    .getByRole('button', { name: 'Prepare proposal', exact: true })
    .click()
  const created = await createdResponse
  expect(created.status()).toBe(200)
  const run = await created.json()
  expect(run.status).toBe('awaiting_approval')
  expect(run.proposal.quantity).toBeGreaterThan(0)
  const awaitingOrders = await pages(
    request,
    '/api/v1/purchase-orders?status=pending',
    headers,
    purchaseOrderSchema,
  )
  const order = awaitingOrders.find((item) => item.id === run.purchase_order_id)
  expect(order?.status).toBe('pending')
  expect(order?.items[0]?.product_id).toBe(balance.product_id)
  expect(
    order?.approvals.filter((item) => item.decision === 'approved'),
  ).toHaveLength(0)
  await expect(
    page.getByRole('button', { name: 'Review approval', exact: true }),
  ).toBeVisible()
  await page
    .getByRole('button', { name: 'Review approval', exact: true })
    .click()
  await expect(
    page.getByRole('button', { name: 'Confirm approval', exact: true }),
  ).toBeDisabled()
  const beforeConfirm = await request.get(`/api/v1/agents/runs/${run.id}`, {
    headers,
  })
  expect((await beforeConfirm.json()).status).toBe('awaiting_approval')
  await page
    .getByLabel('Decision reason')
    .fill(
      'Reviewed live stock, supplier terms and budget in the synthetic browser demonstration',
    )
  const decisionResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/agents/runs/${run.id}/decision`) &&
      response.request().method() === 'POST',
  )
  await page
    .getByRole('button', { name: 'Confirm approval', exact: true })
    .click()
  const decided = await decisionResponse
  expect(decided.status()).toBe(200)
  expect((await decided.json()).status).toBe('approved')
  const approvedOrders = await pages(
    request,
    '/api/v1/purchase-orders?status=approved',
    headers,
    purchaseOrderSchema,
  )
  const approvedOrder = approvedOrders.find(
    (item) => item.id === run.purchase_order_id,
  )
  expect(approvedOrder?.status).toBe('approved')
  expect(
    approvedOrder?.approvals.filter((item) => item.decision === 'approved'),
  ).toHaveLength(1)
  const inventoryAfter = await pages(
    request,
    '/api/v1/inventory',
    headers,
    inventorySchema,
  )
  expect(inventoryAfter.find((item) => item.id === balance.id)?.on_hand).toBe(
    balance.on_hand,
  )
  const replay = await request.post(`/api/v1/agents/runs/${run.id}/decision`, {
    headers,
    data: decided.request().postDataJSON(),
  })
  expect(replay.status()).toBe(200)
  expect((await replay.json()).purchase_order_id).toBe(run.purchase_order_id)
  const analystLogin = await request.post('/api/v1/auth/login', {
    data: { email: 'analyst@retailops.demo', password },
  })
  expect(analystLogin.status()).toBe(200)
  const analystHeaders = {
    Authorization: `Bearer ${(await analystLogin.json()).access_token}`,
  }
  const denied = await request.post(`/api/v1/agents/runs/${run.id}/decision`, {
    headers: analystHeaders,
    data: {
      decision: 'approve',
      reason: 'Unauthorized approval probe',
      idempotency_key: crypto.randomUUID(),
    },
  })
  expect(denied.status()).toBe(403)
  const hidden = await request.get(`/api/v1/agents/runs/${run.id}`, {
    headers: analystHeaders,
  })
  expect(hidden.status()).toBe(404)
  await expect(page.locator('.agent-status')).toHaveText('approved')
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false)
  await prepareScreenshot(page)
  await page.screenshot({
    animations: 'disabled',
    path: `../docs/screenshots/agent-approved-${info.project.name}.png`,
    fullPage: true,
  })
})

test('documents show honest disabled-retrieval errors without embedding calls', async ({
  page,
  request,
}, info) => {
  const headers = await signIn(page)
  const status = await request.get('/api/v1/ai/status', { headers })
  expect(status.status()).toBe(200)
  expect(
    (await status.json()).document_retrieval,
    'This browser check deliberately requires RAG disabled',
  ).toBe(false)
  await navigate(page, 'Documents')
  await expect(
    page.getByRole('heading', { name: 'Knowledge library', exact: true }),
  ).toBeVisible()
  await page
    .getByLabel('Document title')
    .fill('Synthetic disabled-retrieval browser probe')
  await page
    .getByLabel('Document text')
    .fill(
      'This authored test fixture verifies that disabled retrieval is reported honestly.',
    )
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/documents') &&
      response.request().method() === 'POST',
  )
  await page
    .getByRole('button', { name: 'Add and index document', exact: true })
    .click()
  expect((await response).status()).toBe(503)
  await expect(page.getByRole('alert')).toContainText('Service is not ready.')
  await expect(page.getByText('Document indexed successfully.')).toHaveCount(0)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false)
  await prepareScreenshot(page)
  await page.screenshot({
    animations: 'disabled',
    path: `../docs/screenshots/documents-disabled-${info.project.name}.png`,
    fullPage: true,
  })
})
