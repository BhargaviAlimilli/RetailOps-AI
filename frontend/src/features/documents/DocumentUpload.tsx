import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { knowledge, MAX_UPLOAD_BYTES } from '../../services/knowledge'
export function DocumentUpload() {
  const client = useQueryClient(),
    form = useRef<HTMLFormElement>(null)
  const [title, setTitle] = useState(''),
    [file, setFile] = useState<File | null>(null),
    [error, setError] = useState('')
  const upload = useMutation({
    mutationFn: knowledge.upload,
    onSettled: () => client.invalidateQueries({ queryKey: ['documents'] }),
    onSuccess: () => {
      setTitle('')
      setFile(null)
      form.current?.reset()
    },
  })
  return (
    <section>
      <h3>Upload a text file</h3>
      <p className="knowledge-muted">
        Import UTF-8 .txt or .md files, up to 100,000 bytes. PDF, Word, and
        other formats are not supported.
      </p>
      <form
        ref={form}
        onSubmit={(event) => {
          event.preventDefault()
          if (!file || !title.trim()) return
          setError('')
          upload.mutate({ title: title.trim(), file })
        }}
      >
        <label className="knowledge-field">
          File title
          <input
            value={title}
            disabled={upload.isPending}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={160}
            required
            placeholder="Name this source document"
          />
        </label>
        <label className="knowledge-field">
          Document file
          <input
            type="file"
            disabled={upload.isPending}
            accept=".txt,.md,text/plain,text/markdown"
            required
            onChange={(event) => {
              upload.reset()
              setError('')
              const next = event.target.files?.[0] ?? null
              if (
                next &&
                (!/\.(txt|md)$/i.test(next.name) ||
                  next.size > MAX_UPLOAD_BYTES ||
                  !next.size)
              ) {
                setError(
                  next.size > MAX_UPLOAD_BYTES
                    ? 'The file exceeds the 100,000 byte limit.'
                    : 'Choose a non-empty UTF-8 .txt or .md file. PDF and other formats are not supported.',
                )
                setFile(null)
                return
              }
              setFile(next)
            }}
          />
        </label>
        {error && <p role="alert">{error}</p>}
        {upload.isError && <p role="alert">{upload.error.message}</p>}
        {upload.isSuccess && (
          <p role="status">File uploaded and indexed successfully.</p>
        )}
        <button
          className="retail-button primary"
          disabled={upload.isPending || !file || !title.trim()}
        >
          {upload.isPending
            ? 'Uploading and indexing...'
            : 'Upload and index file'}
        </button>
      </form>
    </section>
  )
}
