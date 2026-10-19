import { z } from 'zod'
import { apiRequest, requestVoid } from '../lib/api'
export const citationSchema = z.object({
  document_id: z.string().uuid(),
  chunk_id: z.string().uuid(),
  title: z.string(),
  excerpt: z.string(),
  score: z.number(),
})
export type Citation = z.infer<typeof citationSchema>
export const documentSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  filename: z.string().nullable().optional(),
  status: z.enum(['processing', 'ready', 'error']),
  format: z.enum(['text', 'markdown']).optional(),
  error_code: z.string().nullable().optional(),
  created_at: z.string(),
  chunk_count: z.number().int(),
})
export const MAX_UPLOAD_BYTES = 100000
export async function validateDocumentFile(file: File): Promise<void> {
  if (!/\.(txt|md)$/i.test(file.name))
    throw new Error(
      'Choose a .txt or .md file. PDF and other formats are not supported.',
    )
  if (file.size > MAX_UPLOAD_BYTES)
    throw new Error('The file exceeds the 100,000 byte limit.')
  if (!file.size) throw new Error('Choose a non-empty document.')
  const bytes = file.arrayBuffer
    ? await file.arrayBuffer()
    : await new Promise<ArrayBuffer>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as ArrayBuffer)
        reader.onerror = () => reject(new Error('Unable to read this file.'))
        reader.readAsArrayBuffer(file)
      })
  let content: string
  try {
    content = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    throw new Error('The document must contain valid UTF-8 text.')
  }
  if (!content.trim() || content.includes('\0'))
    throw new Error(
      'Choose a non-empty UTF-8 text document without binary content.',
    )
}
export const knowledge = {
  upload: async ({ title, file }: { title: string; file: File }) => {
    const validTitle = z.string().trim().min(1).max(160).parse(title)
    await validateDocumentFile(file)
    const body = new FormData()
    body.append('title', validTitle)
    body.append('file', file, file.name)
    return apiRequest('/api/v1/documents/upload', documentSchema, {
      method: 'POST',
      body,
      timeoutMs: 60000,
    })
  },
  list: () => apiRequest('/api/v1/documents', z.array(documentSchema)),
  create: (body: { title: string; content: string }) =>
    apiRequest('/api/v1/documents', documentSchema, {
      method: 'POST',
      timeoutMs: 60000,
      body: JSON.stringify(
        z
          .object({
            title: z.string().trim().min(1).max(160),
            content: z.string().trim().min(1).max(100000),
          })
          .parse(body),
      ),
    }),
  remove: (id: string) =>
    requestVoid(`/api/v1/documents/${id}`, { method: 'DELETE' }),
  search: (query: string) =>
    apiRequest(
      '/api/v1/documents/search',
      z.object({ citations: z.array(citationSchema) }),
      {
        method: 'POST',
        timeoutMs: 60000,
        body: JSON.stringify({
          query: z.string().trim().min(1).max(2000).parse(query),
        }),
      },
    ),
}
