import { z } from 'zod'
import { apiRequest, requestVoid } from '../lib/api'

export const userSchema = z.object({
  id: z.string(),
  email: z.email(),
  name: z.string(),
  role: z.enum(['admin', 'manager', 'analyst']),
})
export const loginSchema = z.object({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.').max(1024),
})
export const sessionSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal('bearer'),
  user: userSchema,
})
export type AuthSession = z.infer<typeof sessionSchema>
export type User = z.infer<typeof userSchema>
export type LoginInput = z.infer<typeof loginSchema>
export const login = (input: LoginInput) =>
  apiRequest('/api/v1/auth/login', sessionSchema, {
    method: 'POST',
    body: JSON.stringify(loginSchema.parse(input)),
  })
export const getCurrentUser = () => apiRequest('/api/v1/auth/me', userSchema)
export const logout = () =>
  requestVoid('/api/v1/auth/logout', { method: 'POST' })
