/** Read-only visual QA: authenticates and selects an existing approved run. No workflow/model writes. */
import { existsSync, readFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
const envPath = new URL('../../backend/.env', import.meta.url)
const env = existsSync(envPath) ? readFileSync(envPath, 'utf8') : ''
const password =
  process.env.RETAILOPS_DEMO_PASSWORD ??
  env.match(/^RETAILOPS_DEMO_PASSWORD=(.+)$/m)?.[1]?.trim()
let browser
try {
  if (!password) throw new Error('demo_password_missing')
  browser = await chromium.launch()
  const context = await browser.newContext({
    baseURL: process.env.RETAILOPS_BASE_URL ?? 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 1000 },
  })
  const page = await context.newPage()
  await page.goto('/login')
  await page.getByLabel('Work email').fill('manager@retailops.demo')
  await page.getByLabel('Password', { exact: true }).fill(password)
  const login = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/auth/login') &&
      response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  if ((await login).status() !== 200) throw new Error('login_failed')
  await page
    .getByRole('heading', { name: 'Business overview', exact: true })
    .waitFor()
  const runResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/agents/runs') &&
      response.request().method() === 'GET',
  )
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Agent Workflows', exact: true })
    .click()
  const response = await runResponse
  if (!response.ok()) throw new Error('history_failed')
  const runs = await response.json()
  const approvedIndex = runs.findIndex((run) => run.status === 'approved')
  if (approvedIndex < 0) throw new Error('no_existing_approved_run')
  await page.locator('.agent-history > button').nth(approvedIndex).click()
  await page.locator('.agent-status').filter({ hasText: 'approved' }).waitFor()
  const directory = new URL('../../docs/screenshots/', import.meta.url)
  mkdirSync(directory, { recursive: true })
  for (const [name, viewport] of [
    ['desktop', { width: 1440, height: 1000 }],
    ['mobile', { width: 390, height: 844 }],
  ]) {
    await page.setViewportSize(viewport)
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
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw new Error('viewport_overflow')
    await page.screenshot({
      path: fileURLToPath(new URL(`agent-approved-${name}.png`, directory)),
      fullPage: true,
      animations: 'disabled',
    })
  }
  console.log(
    JSON.stringify({
      status: 'passed',
      screenshots: 2,
      workflow_writes: 0,
      model_calls: 0,
    }),
  )
} catch {
  console.error(
    JSON.stringify({
      status: 'failed',
      screenshots: 0,
      workflow_writes: 0,
      model_calls: 0,
    }),
  )
  process.exitCode = 1
} finally {
  await browser?.close()
}
