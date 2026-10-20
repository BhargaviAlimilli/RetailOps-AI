/** Verify an existing generated turn and its replay. Makes no new generation/embedding calls. */
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const id = process.argv[process.argv.indexOf('--conversation') + 1]
if (!/^[a-f0-9-]{36}$/i.test(id ?? ''))
  throw new Error('Pass --conversation UUID')
const local = readFileSync(
  new URL('../../backend/.env', import.meta.url),
  'utf8',
)
const password =
  process.env.RETAILOPS_DEMO_PASSWORD ??
  local.match(/^RETAILOPS_DEMO_PASSWORD=(.+)$/m)?.[1]?.trim()
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const browser = await chromium.launch()
try {
  const context = await browser.newContext({
    baseURL: 'http://127.0.0.1:5173',
    permissions: ['clipboard-read', 'clipboard-write'],
    viewport: { width: 1440, height: 1000 },
  })
  const page = await context.newPage()
  await page.goto('/login')
  await page.getByLabel('Work email').fill('manager@retailops.demo')
  await page.getByLabel('Password', { exact: true }).fill(password)
  const login = page.waitForResponse((r) =>
    r.url().endsWith('/api/v1/auth/login'),
  )
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  const session = await (await login).json()
  const headers = { Authorization: `Bearer ${session.access_token}` }
  const get = async (path) => {
    const r = await context.request.get(path, { headers })
    assert(r.ok(), 'Authenticated read failed')
    return r.json()
  }
  const path = `/api/v1/conversations/${id}/messages`
  const messages = await get(path)
  const answer = messages
    .filter((m) => m.role === 'assistant' && m.status === 'completed')
    .at(-1)
  assert(answer?.content?.trim(), 'No completed saved answer')
  assert(
    answer.tool_trace.some(
      (t) => t.name === 'get_sales_summary' && t.status === 'completed',
    ),
    'Sales tool missing',
  )
  assert(answer.citations.length > 0, 'Citations missing')
  for (const citation of answer.citations) {
    const source = await get(`/api/v1/documents/${citation.document_id}`)
    assert(
      source.content.includes(citation.excerpt),
      'Citation differs from actual owned source',
    )
  }
  const dashboard = await get('/api/v1/dashboard')
  assert(
    answer.content
      .replaceAll(',', '')
      .includes(dashboard.revenue.replace(/\.00$/, '')),
    'Revenue differs from SQL report',
  )
  assert(/Monday/i.test(answer.content), 'Policy answer missing')
  await page
    .getByRole('heading', { name: 'Business overview', exact: true })
    .waitFor()
  const history = page.waitForResponse(
    (r) =>
      r.url().endsWith('/api/v1/conversations') &&
      r.request().method() === 'GET',
  )
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'AI Companion', exact: true })
    .click()
  const list = await (await history).json()
  const index = list.findIndex((c) => c.id === id)
  assert(index >= 0, 'Saved conversation is not listed')
  await page
    .getByRole('navigation', { name: 'Conversation history' })
    .getByRole('button')
    .nth(index)
    .click()
  const article = page.locator('article[aria-label="Assistant message"]').last()
  await article.waitFor({ state: 'visible' })
  const paragraph = article
    .locator('.ai-message-body > :is(p,ul,ol,table,pre,blockquote,h1,h2,h3)')
    .first()
  assert(
    (await paragraph.innerText()).trim().length > 10,
    'Answer text is not rendered',
  )
  await article.getByRole('button', { name: 'Copy message' }).click()
  await article
    .getByRole('status')
    .filter({ hasText: 'Copied to clipboard.' })
    .waitFor()
  assert(
    (await page.evaluate(() => navigator.clipboard.readText())).replaceAll(
      '\r\n',
      '\n',
    ) === answer.content.replaceAll('\r\n', '\n'),
    'Copied answer differs',
  )
  for (const [name, size] of [
    ['desktop', { width: 1440, height: 1000 }],
    ['mobile', { width: 390, height: 844 }],
  ]) {
    await page.setViewportSize(size)
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
        innerWidth > 700 ||
        !sidebar ||
        getComputedStyle(sidebar).position !== 'fixed' ||
        sidebar.getBoundingClientRect().right <= 0
      )
    })
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      'Viewport overflow',
    )
    await page.screenshot({
      path: fileURLToPath(
        new URL(
          `../../docs/screenshots/assistant-live-${name}.png`,
          import.meta.url,
        ),
      ),
      fullPage: true,
      animations: 'disabled',
    })
  }
  const prompt = messages.find(
    (m) => m.role === 'user' && m.request_id === answer.request_id,
  )
  assert(prompt, 'Original request is missing')
  const replay = await context.request.post(path, {
    headers,
    data: { content: prompt.content, request_id: answer.request_id },
  })
  assert(replay.ok(), 'Saved replay failed')
  const terminal = (await replay.text())
    .split('\n\n')
    .find((frame) => frame.includes('event: message.completed'))
  assert(terminal, 'Replay completion missing')
  const event = JSON.parse(
    terminal
      .split('\n')
      .find((line) => line.startsWith('data: '))
      .slice(6),
  )
  assert(
    event.message_id === answer.id && event.payload.content === answer.content,
    'Replay differs',
  )
  assert(
    (await get(path)).length === messages.length,
    'Replay duplicated messages',
  )
  const result = {
    status: 'passed',
    mode: 'saved_turn_ui_and_replay',
    conversation_id: id,
    new_model_calls: 0,
    new_embedding_calls: 0,
    saved_messages: messages.length,
    citations: answer.citations.length,
    tool_steps: answer.tool_trace.length,
    revenue_matches_database: true,
    citation_excerpts_match_sources: true,
    clipboard_matches_saved_answer: true,
    desktop_mobile_screenshots: 2,
    saved_replays: 1,
    usage: answer.usage,
  }
  writeFileSync(
    new URL('../../docs/verification/live-saved-answer.json', import.meta.url),
    JSON.stringify(result, null, 2) + '\n',
  )
  console.log(JSON.stringify(result))
  await context.request.post('/api/v1/auth/logout', { headers })
} finally {
  await browser.close()
}
