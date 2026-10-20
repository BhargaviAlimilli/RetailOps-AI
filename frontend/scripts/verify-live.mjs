/** Opt-in real-provider verification. Never imported by CI or regular test commands.
 * One source search, one new chat turn, and only a persisted idempotent replay.
 * The server must enforce <=2 generation attempts and <=3 embedding attempts.
 */
import { existsSync, readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

class VerificationFailure extends Error {}
const requireTrue = (value, code) => {
  if (!value) throw new VerificationFailure(code)
}
if (!process.argv.includes('--allow-model-calls')) {
  console.error(
    JSON.stringify({
      status: 'refused',
      reason:
        'Explicit --allow-model-calls is required; this script uses paid model and embedding endpoints.',
    }),
  )
  process.exit(2)
}
const counts = {
  source_searches: 0,
  chat_submissions: 0,
  saved_replays: 0,
  saved_messages: 0,
  citations: 0,
  tool_steps: 0,
  screenshots: 0,
}
const envPath = new URL('../../backend/.env', import.meta.url)
const localEnv = existsSync(envPath) ? readFileSync(envPath, 'utf8') : ''
const password =
  process.env.RETAILOPS_DEMO_PASSWORD ??
  localEnv.match(/^RETAILOPS_DEMO_PASSWORD=(.+)$/m)?.[1]?.trim()
const baseURL = process.env.RETAILOPS_BASE_URL ?? 'http://127.0.0.1:5173'
const screenshotDirectory = new URL('../../docs/screenshots/', import.meta.url)
let browser
let page
let result
async function prepareScreenshot(page) {
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
async function checkedJSON(response, code) {
  requireTrue(response.ok(), `${code}_http_${response.status()}`)
  return response.json()
}
function namedEvent(stream, name) {
  const frames = stream.replace(/\r\n/g, '\n').split('\n\n')
  for (const frame of frames) {
    if (!frame.split('\n').some((line) => line === `event: ${name}`)) continue
    const data = frame
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
      .join('\n')
    return JSON.parse(data)
  }
  return null
}
function terminalEvent(stream) {
  return namedEvent(stream, 'message.completed')
}
try {
  requireTrue(Boolean(password), 'demo_password_missing')
  browser = await chromium.launch()
  const context = await browser.newContext({
    baseURL,
    viewport: { width: 1440, height: 1000 },
  })
  page = await context.newPage()
  page.setDefaultTimeout(15000)
  await page.goto('/login')
  await page.getByLabel('Work email').fill('manager@retailops.demo')
  await page.getByLabel('Password', { exact: true }).fill(password)
  const loginResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/auth/login') &&
      response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  const session = await checkedJSON(await loginResponse, 'login')
  const headers = { Authorization: `Bearer ${session.access_token}` }
  const status = await checkedJSON(
    await context.request.get('/api/v1/ai/status', { headers }),
    'ai_status',
  )
  requireTrue(
    status.configured && status.operational_tools && status.document_retrieval,
    'grounded_provider_not_configured',
  )
  const documents = await checkedJSON(
    await context.request.get('/api/v1/documents', { headers }),
    'document_list',
  )
  requireTrue(
    documents.some((document) => document.status === 'ready'),
    'no_ready_private_fixture',
  )
  await page
    .getByRole('heading', { name: 'Business overview', exact: true })
    .waitFor()
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Documents', exact: true })
    .click()
  await page
    .getByRole('heading', { name: 'Knowledge library', exact: true })
    .waitFor()
  await page
    .getByLabel('Search query')
    .fill('How often should staff count shelves?')
  const searchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/documents/search') &&
      response.request().method() === 'POST',
    { timeout: 90000 },
  )
  counts.source_searches++
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  const search = await checkedJSON(await searchResponse, 'source_search')
  requireTrue(search.citations?.length > 0, 'source_search_no_citations')
  const first = search.citations[0]
  requireTrue(
    documents.some(
      (document) =>
        document.id === first.document_id && document.status === 'ready',
    ),
    'source_not_ready_private_fixture',
  )
  await page.locator('.citation-card').first().waitFor()
  await page.locator('.citation-card').first().locator('summary').click()
  requireTrue(
    (await page
      .locator('.citation-card')
      .first()
      .locator('blockquote')
      .textContent()) === first.excerpt,
    'source_excerpt_mismatch',
  )
  mkdirSync(screenshotDirectory, { recursive: true })
  await page.evaluate(
    () =>
      document.activeElement instanceof HTMLElement &&
      document.activeElement.blur(),
  )
  await prepareScreenshot(page)
  await page.screenshot({
    animations: 'disabled',
    path: fileURLToPath(
      new URL('documents-ready-desktop.png', screenshotDirectory),
    ),
    fullPage: true,
  })
  counts.screenshots++
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForFunction(() => {
    const sidebar = document.querySelector('#sidebar')
    return (
      innerWidth > 700 ||
      !sidebar ||
      getComputedStyle(sidebar).position !== 'fixed' ||
      sidebar.getBoundingClientRect().right <= 0
    )
  })
  requireTrue(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    'documents_mobile_overflow',
  )
  await prepareScreenshot(page)
  await page.screenshot({
    animations: 'disabled',
    path: fileURLToPath(
      new URL('documents-ready-mobile.png', screenshotDirectory),
    ),
    fullPage: true,
  })
  counts.screenshots++
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'AI Companion', exact: true })
    .click()
  await page
    .getByRole('heading', { name: 'AI Companion Gemini', exact: true })
    .waitFor()
  const prompt =
    'Use get_sales_summary to report current completed-day revenue, and cite our policy for how often staff count shelves. Explain that stockouts do not prove sales causation.'
  await page
    .getByRole('textbox', { name: 'Message your retail companion' })
    .fill(prompt)
  const newTurnResponse = page.waitForResponse(
    (response) =>
      /\/api\/v1\/conversations\/[^/]+\/messages$/.test(response.url()) &&
      response.request().method() === 'POST',
    { timeout: 150000 },
  )
  counts.chat_submissions++
  await page.getByRole('button', { name: 'Send message', exact: true }).click()
  const response = await newTurnResponse
  requireTrue(response.ok(), `chat_http_${response.status()}`)
  const stream = (await response.body()).toString('utf8')
  const complete = terminalEvent(stream)
  if (!complete) {
    const failed = namedEvent(stream, 'message.error')
    const code = /^[a-z0-9_]+$/.test(failed?.payload?.code ?? '')
      ? failed.payload.code
      : 'no_completed_terminal'
    throw new VerificationFailure(`chat_${code}_no_retry`)
  }
  const conversationId = complete.conversation_id
  const messages = await checkedJSON(
    await context.request.get(
      `/api/v1/conversations/${conversationId}/messages`,
      { headers },
    ),
    'saved_messages',
  )
  counts.saved_messages = messages.length
  const saved = messages.find((message) => message.id === complete.message_id)
  requireTrue(
    saved?.role === 'assistant' &&
      saved.status === 'completed' &&
      saved.content.trim().length > 0,
    'saved_answer_not_completed',
  )
  requireTrue(
    saved.content === complete.payload.content,
    'saved_answer_stream_mismatch',
  )
  requireTrue(
    saved.tool_trace?.some(
      (tool) =>
        tool.name === 'get_sales_summary' && tool.status === 'completed',
    ),
    'sales_summary_tool_not_completed',
  )
  requireTrue(saved.citations?.length > 0, 'saved_answer_has_no_citations')
  counts.citations = saved.citations.length
  counts.tool_steps = saved.tool_trace.length
  const rendered = page
    .locator(
      'article[aria-label="Assistant message"] .ai-message-body > :is(p,ul,ol,table,pre,blockquote,h1,h2,h3)',
    )
    .first()
  await rendered.waitFor({ state: 'visible' })
  requireTrue(
    (await rendered.innerText()).trim().length > 10,
    'answer_not_rendered',
  )
  await page.evaluate(
    () =>
      document.activeElement instanceof HTMLElement &&
      document.activeElement.blur(),
  )
  await prepareScreenshot(page)
  await page.screenshot({
    animations: 'disabled',
    path: fileURLToPath(
      new URL('assistant-live-desktop.png', screenshotDirectory),
    ),
    fullPage: true,
  })
  counts.screenshots++
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForFunction(() => {
    const sidebar = document.querySelector('#sidebar')
    return (
      innerWidth > 700 ||
      !sidebar ||
      getComputedStyle(sidebar).position !== 'fixed' ||
      sidebar.getBoundingClientRect().right <= 0
    )
  })
  requireTrue(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    'assistant_mobile_overflow',
  )
  await prepareScreenshot(page)
  await page.screenshot({
    animations: 'disabled',
    path: fileURLToPath(
      new URL('assistant-live-mobile.png', screenshotDirectory),
    ),
    fullPage: true,
  })
  counts.screenshots++
  // Same request UUID + identical prompt enters the persisted replay branch before provider work.
  counts.saved_replays++
  const replay = await context.request.post(
    `/api/v1/conversations/${conversationId}/messages`,
    {
      headers,
      data: { content: prompt, request_id: saved.request_id },
      timeout: 30000,
    },
  )
  requireTrue(replay.ok(), `replay_http_${replay.status()}`)
  const replayed = terminalEvent(await replay.text())
  requireTrue(
    replayed?.message_id === saved.id &&
      replayed.payload.content === saved.content,
    'saved_replay_mismatch',
  )
  const after = await checkedJSON(
    await context.request.get(
      `/api/v1/conversations/${conversationId}/messages`,
      { headers },
    ),
    'replayed_history',
  )
  requireTrue(after.length === messages.length, 'replay_duplicated_messages')
  result = { status: 'passed', ...counts }
  console.log(JSON.stringify(result))
} catch (error) {
  if ((counts.chat_submissions || counts.source_searches) && page) {
    const errorPrefix = counts.chat_submissions
      ? 'assistant-live-error'
      : 'documents-live-error'
    try {
      await page.getByRole('alert').first().waitFor({ timeout: 5000 })
      await page.setViewportSize({ width: 1440, height: 1000 })
      await prepareScreenshot(page)
      await page.screenshot({
        animations: 'disabled',
        path: fileURLToPath(
          new URL(`${errorPrefix}-desktop.png`, screenshotDirectory),
        ),
        fullPage: true,
      })
      counts.screenshots++
      await page.setViewportSize({ width: 390, height: 844 })
      await page.waitForFunction(() => {
        const sidebar = document.querySelector('#sidebar')
        return (
          innerWidth > 700 ||
          !sidebar ||
          getComputedStyle(sidebar).position !== 'fixed' ||
          sidebar.getBoundingClientRect().right <= 0
        )
      })
      await prepareScreenshot(page)
      await page.screenshot({
        animations: 'disabled',
        path: fileURLToPath(
          new URL(`${errorPrefix}-mobile.png`, screenshotDirectory),
        ),
        fullPage: true,
      })
      counts.screenshots++
    } catch {
      /* Screenshot failure never triggers another provider request. */
    }
  }
  result = {
    status: 'failed',
    reason:
      error instanceof VerificationFailure
        ? error.message
        : 'unexpected_verification_error',
    ...counts,
  }
  console.error(JSON.stringify(result))
  process.exitCode = 1
} finally {
  const verificationDirectory = new URL(
    '../../docs/verification/',
    import.meta.url,
  )
  mkdirSync(verificationDirectory, { recursive: true })
  writeFileSync(
    new URL('live-browser.json', verificationDirectory),
    JSON.stringify(
      result ?? {
        status: 'failed',
        reason: 'verification_incomplete',
        ...counts,
      },
      null,
      2,
    ) + '\n',
  )
  await browser?.close()
}
