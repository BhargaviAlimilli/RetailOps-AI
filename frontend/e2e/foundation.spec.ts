import { expect, test } from '@playwright/test'

// Requires the real backend and migrated local demo database. No intercepted responses.
test('connected workspace is accessible and fits the viewport', async ({
  page,
  request,
}, info) => {
  const ready = await request.get('/api/v1/ready')
  expect(
    ready.status(),
    'Start the backend and demo PostgreSQL before this test',
  ).toBe(200)
  await page.goto('/system')
  await expect(
    page.getByRole('heading', { name: 'Workspace overview' }),
  ).toBeVisible()
  await expect(page.getByText('Connected', { exact: true })).toHaveCount(2)
  await expect(
    page.getByText('No operational metrics are displayed yet.'),
  ).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  )
  expect(overflow).toBe(false)
  if (info.project.name === 'mobile') {
    await page.getByRole('button', { name: 'Open navigation' }).click()
    await expect(page.getByRole('navigation')).toBeVisible()
    await page.getByRole('button', { name: 'Close navigation' }).click()
  }
  await page.screenshot({
    path: `../docs/screenshots/foundation-${info.project.name}.png`,
    fullPage: true,
  })
})
