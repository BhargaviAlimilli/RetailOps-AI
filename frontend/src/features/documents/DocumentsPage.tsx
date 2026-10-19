import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { FileText, Plus, Search, Trash2 } from 'lucide-react'
import { DocumentUpload } from './DocumentUpload'
import { knowledge } from '../../services/knowledge'
import { CitationCard } from '../../components/ai/CitationCard'
import { useAuth } from '../auth/AuthProvider'
import { PageHeading, QueryState } from '../retail/shared'
import '../retail/retail.css'
import './knowledge.css'
const formSchema = z.object({
  title: z.string().trim().min(1).max(160),
  content: z.string().trim().min(1).max(100000),
})
export default function DocumentsPage() {
  const { user } = useAuth(),
    client = useQueryClient()
  const canEdit = !!user
  const [title, setTitle] = useState(''),
    [content, setContent] = useState(''),
    [query, setQuery] = useState(''),
    [validation, setValidation] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const documents = useQuery({
    queryKey: ['documents'],
    queryFn: knowledge.list,
  })
  const add = useMutation({
    mutationFn: knowledge.create,
    onSettled: () => client.invalidateQueries({ queryKey: ['documents'] }),
    onSuccess: () => {
      setTitle('')
      setContent('')
      void client.invalidateQueries({ queryKey: ['documents'] })
    },
  })
  const remove = useMutation({
    mutationFn: knowledge.remove,
    onSuccess: () => {
      setDeleting(null)
      void client.invalidateQueries({ queryKey: ['documents'] })
      search.reset()
    },
  })
  const search = useMutation({ mutationFn: knowledge.search })
  return (
    <section>
      <PageHeading
        title="Knowledge library"
        description="Bring your operating guides into your retail workspace."
      />
      <div className="knowledge-layout">
        <div>
          <section className="knowledge-panel">
            <h2>
              <FileText size={18} /> Your documents
            </h2>
            <p className="knowledge-muted">
              Documents are indexed for retrieval. Source text is treated as
              reference material, never as instructions to execute.
            </p>
            <QueryState
              pending={documents.isPending}
              error={documents.error}
              retry={() => documents.refetch()}
            />
            {documents.data?.length === 0 && (
              <div className="knowledge-empty">
                No documents yet. Add your first policy, guide, or supplier
                note.
              </div>
            )}
            {documents.data?.map((doc) => (
              <article className="knowledge-document" key={doc.id}>
                <div>
                  <strong>{doc.title}</strong>
                  <p>
                    {doc.chunk_count} chunks / {doc.status}
                  </p>
                </div>
                {canEdit && (
                  <button
                    className="retail-button"
                    aria-label={`Delete ${doc.title}`}
                    onClick={() => {
                      setDeleting(doc.id)
                      remove.reset()
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
                {deleting === doc.id && (
                  <div className="knowledge-delete">
                    <p>Delete this document and its indexed chunks?</p>
                    <button
                      className="retail-button"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(doc.id)}
                    >
                      {remove.isPending ? 'Deleting...' : 'Confirm delete'}
                    </button>
                    <button
                      className="retail-button"
                      onClick={() => setDeleting(null)}
                    >
                      Cancel
                    </button>
                    {remove.isError && (
                      <p role="alert">{remove.error.message}</p>
                    )}
                  </div>
                )}
              </article>
            ))}
          </section>
          <section className="knowledge-panel">
            <h2>
              <Search size={18} /> Search your sources
            </h2>
            <form
              className="knowledge-search"
              onSubmit={(event) => {
                event.preventDefault()
                if (query.trim()) search.mutate(query.trim())
              }}
            >
              <label className="knowledge-field">
                Search query
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  maxLength={2000}
                  placeholder="Find a return policy or supplier term"
                  required
                />
              </label>
              <button
                className="retail-button primary"
                disabled={search.isPending || !query.trim()}
              >
                {search.isPending ? 'Searching...' : 'Search'}
              </button>
            </form>
            {search.isError && <p role="alert">{search.error.message}</p>}
            {search.data?.citations.length === 0 && (
              <p className="knowledge-empty">
                No relevant excerpts found. Try a different question or add a
                document.
              </p>
            )}
            {search.data?.citations.map((citation) => (
              <CitationCard key={citation.chunk_id} citation={citation} />
            ))}
          </section>
        </div>
        <section className="knowledge-panel knowledge-add">
          <h2>
            <Plus size={18} /> Add a document
          </h2>
          {canEdit ? (
            <form
              onSubmit={(event) => {
                event.preventDefault()
                const result = formSchema.safeParse({ title, content })
                if (!result.success) {
                  setValidation(
                    'Enter a title (up to 160 characters) and document text (up to 100,000 characters).',
                  )
                  return
                }
                setValidation('')
                add.mutate(result.data)
              }}
            >
              <label className="knowledge-field">
                Document title
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  maxLength={160}
                  required
                  placeholder="Returns and exchanges policy"
                />
              </label>
              <label className="knowledge-field">
                Document text
                <textarea
                  rows={13}
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  maxLength={100000}
                  required
                  placeholder="Paste plain text or Markdown from an approved business document."
                />
              </label>
              <p className="knowledge-muted">
                Add business reference content only. Do not include passwords,
                API keys, or private customer details.
              </p>
              {validation && <p role="alert">{validation}</p>}
              {add.isError && <p role="alert">{add.error.message}</p>}
              {add.isSuccess && (
                <p role="status">Document indexed successfully.</p>
              )}
              <button
                className="retail-button primary"
                disabled={add.isPending}
              >
                {add.isPending
                  ? 'Indexing document...'
                  : 'Add and index document'}
              </button>
            </form>
          ) : (
            <p className="knowledge-muted">
              Sign in to manage and search your private document library.
            </p>
          )}
          {canEdit && <DocumentUpload />}
        </section>
      </div>
    </section>
  )
}
