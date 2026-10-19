import { DiffViewer } from '../../components/ai/DiffViewer'
import { StructuredSpecification } from '../../components/ai/StructuredSpecification'
import './showcase.css'
import { useState } from 'react'
import { AIMessage } from '../../components/ai/AIMessage'
import { ToolExecutionCard } from '../../components/ai/ToolExecutionCard'
import { AIComposer } from '../../components/ai/AIComposer'
import { CitationCard } from '../../components/ai/CitationCard'
import { StreamingMessage } from '../../components/ai/StreamingMessage'
import { PageHeading } from '../retail/shared'
import '../assistant/assistant.css'
import '../documents/knowledge.css'
export default function ShowcasePage() {
  const [submitted, setSubmitted] = useState('')
  return (
    <section>
      <PageHeading
        title="AI component showcase"
        description="Interactive design examples. These examples are authored fixtures, not generated answers or live retail findings."
      />
      <section className="knowledge-panel">
        <h2>Markdown, code, and message copy</h2>
        <AIMessage
          role="user"
          content="Show an example of a structured operations note."
        />
        <AIMessage
          role="assistant"
          content={
            '## Example operations note\n\n- Review available stock.\n- Verify supplier terms before ordering.\n\n| Check | Owner |\n| --- | --- |\n| Stock review | Manager |\n\n```json\n{"example": true}\n```\n\n[Example reference](https://example.com)'
          }
        />
      </section>
      <section className="knowledge-panel">
        <h2>Source citation example</h2>
        <CitationCard
          citation={{
            document_id: '11111111-1111-4111-8111-111111111111',
            chunk_id: '22222222-2222-4222-8222-222222222222',
            title: 'Example policy (authored fixture)',
            excerpt:
              'This example excerpt demonstrates an expandable source card. It is not a business policy.',
            score: 1,
          }}
        />
      </section>
      <section className="knowledge-panel">
        <h2>Workflow step example</h2>
        <ToolExecutionCard
          name="Example inventory review"
          status="Example completed state"
          detail="Authored fixture showing how a real workflow step is presented. No tool was executed."
        />
      </section>
      <section className="knowledge-panel">
        <h2>AI Engineering Lab examples</h2>
        <p className="knowledge-muted">
          Authored display fixtures. No code changes are applied and no
          specification is generated here.
        </p>
        <DiffViewer
          title="Example policy text comparison"
          lines={[
            { kind: 'context', text: 'Review supplier terms.' },
            { kind: 'removed', text: 'Submit immediately.' },
            { kind: 'added', text: 'Request explicit manager approval.' },
          ]}
        />
        <StructuredSpecification
          title="Example review specification"
          sections={[
            {
              heading: 'Approval requirements',
              fields: [
                { label: 'Actor', value: 'Manager or administrator' },
                {
                  label: 'Evidence',
                  value: 'Supplier terms and current inventory',
                },
                {
                  label: 'Decision',
                  value: 'Explicit approval with a recorded reason',
                },
              ],
            },
          ]}
        />
      </section>
      <section className="knowledge-panel">
        <h2>Composer and status examples</h2>
        <p className="knowledge-muted">
          Sending here only previews your text locally. No model or backend
          request is made.
        </p>
        <AIComposer busy={false} onSend={setSubmitted} onStop={() => {}} />
        {submitted && <p role="status">Local preview: {submitted}</p>}
        <StreamingMessage text="Example streaming status (static fixture)" />
      </section>
    </section>
  )
}
