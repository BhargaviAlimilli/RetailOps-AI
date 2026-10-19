import { readFileSync, existsSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

const envPath = new URL('../../backend/.env', import.meta.url)
const localEnv = existsSync(envPath) ? readFileSync(envPath, 'utf8') : ''
const password =
  process.env.RETAILOPS_DEMO_PASSWORD ??
  localEnv.match(/^RETAILOPS_DEMO_PASSWORD=(.+)$/m)?.[1]?.trim()

test.skip(
  !password,
  'Configure the ignored local demo password and seed before retail browser verification',
)

async function signIn(page: Page, role: 'manager' | 'analyst') {
  await page.goto('/login')
  await page.getByLabel('Work email').fill(`${role}@retailops.demo`)
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
  return session.access_token as string
}
async function navigate(page: Page, title: string) {
  const toggle = page.getByRole('button', { name: 'Open navigation' })
  if (await toggle.isVisible()) await toggle.click()
  await page
    .getByRole('navigation')
    .getByRole('link', { name: title, exact: true })
    .click()
}

test('manager verifies live reporting, purchase approval and audited stock', async ({
  page,
  request,
}, info) => {
  const token = await signIn(page, 'manager')
  const headers = { Authorization: `Bearer ${token}` }
  const start = await page.getByLabel('From', { exact: true }).inputValue()
  const end = await page.getByLabel('To', { exact: true }).inputValue()
  const metrics = await request.get(
    `/api/v1/dashboard?start_date=${start}&end_date=${end}`,
    { headers },
  )
  expect(metrics.status()).toBe(200)
  const revenue = (await metrics.json()).revenue
  const display = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(revenue))
  await expect(
    page
      .locator('.retail-kpi')
      .filter({ hasText: 'Total revenue' })
      .locator('strong'),
  ).toHaveText(display)
  await expect(page.getByRole('alert')).toHaveCount(0)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false)
  await page.screenshot({
    path: `../docs/screenshots/retail-dashboard-${info.project.name}.png`,
    fullPage: true,
  })

  const stores = await (await request.get('/api/v1/stores', { headers })).json()
  const suppliers = await (
    await request.get('/api/v1/suppliers', { headers })
  ).json()
  const store = stores[0]
  const supplier = suppliers[0]
  const term = supplier.terms[0]
  const quantity =
    Math.ceil(term.minimum_order_quantity / term.pack_size) * term.pack_size
  const before = await (
    await request.get(
      `/api/v1/inventory?store_id=${store.id}&q=${encodeURIComponent(term.product_name)}`,
      { headers },
    )
  ).json()
  const balance = before.items.find(
    (item: { product_id: string }) => item.product_id === term.product_id,
  )
  expect(balance).toBeTruthy()

  await navigate(page, 'Purchase Orders')
  await page
    .getByRole('button', { name: 'Create purchase order', exact: true })
    .click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Store', { exact: true }).selectOption(store.id)
  await dialog.getByLabel('Supplier', { exact: true }).selectOption(supplier.id)
  await dialog
    .getByLabel('Product', { exact: true })
    .selectOption(term.product_id)
  await dialog.getByLabel('Quantity', { exact: true }).fill(String(quantity))
  const draftResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/purchase-orders') &&
      response.request().method() === 'POST',
  )
  await dialog
    .getByRole('button', { name: 'Create draft', exact: true })
    .click()
  const created = await draftResponse
  expect(created.status()).toBe(201)
  const order = await created.json()
  await expect(dialog).toHaveCount(0)
  const orderButton = page.getByRole('button', {
    name: new RegExp(order.id.slice(0, 8), 'i'),
  })

  for (const [action, label, status] of [
    ['submit', 'Submit for review', 'pending'],
    ['approve', 'Approve order', 'approved'],
    ['receive', 'Confirm delivery received', 'received'],
  ]) {
    await orderButton.click()
    const review = page.getByRole('dialog')
    await review
      .getByLabel('Decision note')
      .fill('Explicitly reviewed in the local browser demonstration')
    const transitionResponse = page.waitForResponse((response) =>
      response.url().endsWith(`/api/v1/purchase-orders/${order.id}/${action}`),
    )
    await review.getByRole('button', { name: label, exact: true }).click()
    const completed = await transitionResponse
    expect(completed.status()).toBe(200)
    expect((await completed.json()).status).toBe(status)
    await expect(review).toHaveCount(0)
  }
  const after = await (
    await request.get(
      `/api/v1/inventory?store_id=${store.id}&q=${encodeURIComponent(term.product_name)}`,
      { headers },
    )
  ).json()
  expect(
    after.items.find((item: { id: string }) => item.id === balance.id).on_hand,
  ).toBe(balance.on_hand + quantity)
  await orderButton.click()
  await expect(
    page.getByRole('heading', { name: 'Approval history' }),
  ).toBeVisible()
  await page.screenshot({
    path: `../docs/screenshots/purchase-received-${info.project.name}.png`,
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Close dialog' }).click()

  await navigate(page, 'Inventory')
  await page.getByLabel('Filter by store').selectOption(store.id)
  await page.getByLabel('Search inventory').fill(balance.sku)
  await page
    .getByRole('button', { name: new RegExp(term.product_name) })
    .click()
  const stock = page.getByRole('dialog')
  await stock.getByLabel('Quantity change').fill('1')
  await stock
    .getByLabel('Reason', { exact: true })
    .fill('Browser verified cycle count')
  const stockResponse = page.waitForResponse((response) =>
    response.url().endsWith(`/api/v1/inventory/${balance.id}/adjust`),
  )
  await stock.getByRole('button', { name: 'Record adjustment' }).click()
  const adjusted = await stockResponse
  expect(adjusted.status()).toBe(200)
  expect((await adjusted.json()).on_hand).toBe(balance.on_hand + quantity + 1)
  await expect(stock.getByText('Inventory adjustment recorded.')).toBeVisible()
})

test('analyst sees read-only screens and direct writes are forbidden', async ({
  page,
  request,
}) => {
  const token = await signIn(page, 'analyst')
  await navigate(page, 'Products')
  await expect(
    page.getByRole('heading', { name: 'Products', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Add product', exact: true }),
  ).toHaveCount(0)
  await navigate(page, 'Purchase Orders')
  await expect(
    page.getByRole('button', { name: 'Create purchase order', exact: true }),
  ).toHaveCount(0)
  const list = await (
    await request.get('/api/v1/inventory', {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json()
  const denied = await request.post(
    `/api/v1/inventory/${list.items[0].id}/adjust`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Idempotency-Key': crypto.randomUUID(),
      },
      data: { delta: 1, reason: 'Unauthorized browser write probe' },
    },
  )
  expect(denied.status()).toBe(403)
})
