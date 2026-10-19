import { existsSync, readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

const envPath = new URL('../../backend/.env', import.meta.url)
const localEnv = existsSync(envPath) ? readFileSync(envPath, 'utf8') : ''
const password =
  process.env.RETAILOPS_DEMO_PASSWORD ??
  localEnv.match(/^RETAILOPS_DEMO_PASSWORD=(.+)$/m)?.[1]?.trim()
test.skip(
  !password,
  'Configure and seed the local synthetic accounts before this browser check',
)

test('private conversation persists and disabled Gemini never fabricates a reply', async ({
  page,
  request,
}, info) => {
  await page.goto('/login')
  await page.getByLabel('Work email').fill('manager@retailops.demo')
  await page.getByLabel('Password', { exact: true }).fill(password!)
  const sessionResponse = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/auth/login'),
  )
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  const loginResponse = await sessionResponse
  expect(loginResponse.status()).toBe(200)
  const session = await loginResponse.json()
  await expect(
    page.getByRole('heading', { name: 'Business overview', exact: true }),
  ).toBeVisible()
  const headers = { Authorization: `Bearer ${session.access_token}` }
  const status = await request.get('/api/v1/ai/status', { headers })
  expect(status.status()).toBe(200)
  const availability = await status.json()
  // This test must never call a configured model or incur API charges.
  test.skip(
    availability.configured,
    'This browser case deliberately verifies only a disabled provider',
  )
  const toggle = page.getByRole('button', { name: 'Open navigation' })
  if (await toggle.isVisible()) await toggle.click()
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'AI Companion', exact: true })
    .click()
  await expect(
    page.getByRole('heading', { name: /AI Companion/ }),
  ).toBeVisible()
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/conversations') &&
      response.request().method() === 'POST',
  )
  await page.getByLabel('New conversation', { exact: true }).click()
  const created = await createdResponse
  expect(created.status()).toBe(201)
  const conversation = await created.json()
  await expect(
    page
      .getByRole('navigation', { name: 'Conversation history' })
      .getByRole('button', { name: 'New conversation', exact: true })
      .first(),
  ).toBeVisible()
  await page
    .getByRole('textbox', { name: 'Message your retail companion' })
    .fill('Explain safety stock in general terms.')
  const disabledResponse = page.waitForResponse(
    (response) =>
      response
        .url()
        .endsWith(`/api/v1/conversations/${conversation.id}/messages`) &&
      response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Send message' }).click()
  expect((await disabledResponse).status()).toBe(503)
  await expect(page.getByRole('alert')).toContainText(
    'AI Companion is unavailable',
  )
  const messages = await request.get(
    `/api/v1/conversations/${conversation.id}/messages`,
    { headers },
  )
  expect(messages.status()).toBe(200)
  expect(await messages.json()).toEqual([])
  const saved = await (
    await request.get('/api/v1/conversations', { headers })
  ).json()
  expect(
    saved.some((item: { id: string }) => item.id === conversation.id),
  ).toBe(true)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false)
  await page.screenshot({
    path: `../docs/screenshots/assistant-unconfigured-${info.project.name}.png`,
    fullPage: true,
  })
})
