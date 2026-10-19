import { FileText } from 'lucide-react'
import type { Citation } from '../../services/knowledge'
export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <details className="citation-card">
      <summary>
        <FileText size={14} />
        <span>{citation.title}</span>
        <small>View source excerpt</small>
      </summary>
      <blockquote>{citation.excerpt}</blockquote>
      <p>
        Source document: {citation.document_id} / chunk: {citation.chunk_id}
      </p>
    </details>
  )
}
