import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from '../features/auth/LoginPage'
import { loginSchema, type AuthSession } from '../services/auth'
import { sessionCleared, sessionEstablished, store } from '../store'
import { apiRequest } from '../lib/api'
import { z } from 'zod'

const session: AuthSession = {
  access_token: 'unit-test-session',
  token_type: 'bearer',
  user: {
    id: 'test-user',
    email: 'analyst@example.com',
    name: 'Analyst',
    role: 'analyst',
  },
}
afterEach(() => {
  store.dispatch(sessionCleared())
  vi.unstubAllGlobals()
})
describe('authentication', () => {
  it('validates credentials before submitting', () => {
    expect(
      loginSchema.safeParse({ email: 'invalid', password: '' }).success,
    ).toBe(false)
    expect(
      loginSchema.safeParse({ email: 'person@example.com', password: 'value' })
        .success,
    ).toBe(true)
  })
  it('holds roles in memory and clears the entire session', () => {
    store.dispatch(sessionEstablished(session))
    expect(store.getState().auth?.user.role).toBe('analyst')
    store.dispatch(sessionCleared())
    expect(store.getState().auth).toBeNull()
  })
  it('attaches bearer token and clears an expired session', async () => {
    store.dispatch(sessionEstablished(session))
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response('{}', { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(
      apiRequest('/api/v1/auth/me', z.object({})),
    ).rejects.toMatchObject({ status: 401 })
    expect(
      new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get('Authorization'),
    ).toBe('Bearer unit-test-session')
    expect(store.getState().auth).toBeNull()
  })
  it('shows a normalized login failure without exposing server details', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('private server details', { status: 401 }),
        ),
    )
    render(
      <Provider store={store}>
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter>
            <LoginPage />
          </MemoryRouter>
        </QueryClientProvider>
      </Provider>,
    )
    await userEvent.type(
      screen.getByLabelText('Work email'),
      'person@example.com',
    )
    await userEvent.type(screen.getByLabelText('Password'), 'incorrect')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your email or password is incorrect',
    )
    expect(screen.queryByText('private server details')).not.toBeInTheDocument()
  })
})
