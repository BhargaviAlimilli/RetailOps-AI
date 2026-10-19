export type DiffLine = { kind: 'added' | 'removed' | 'context'; text: string }
/** Renders an explicitly supplied diff; never evaluates generated patches. */
export function DiffViewer({
  title,
  lines,
}: {
  title: string
  lines: DiffLine[]
}) {
  return (
    <section className="ai-diff" aria-label={title}>
      <h3>{title}</h3>
      <pre>
        {lines.map((line, index) => (
          <span key={index} className={`diff-${line.kind}`}>
            <span aria-label={line.kind}>
              {line.kind === 'added'
                ? '+'
                : line.kind === 'removed'
                  ? '-'
                  : ' '}
            </span>{' '}
            {line.text}
            {'\n'}
          </span>
        ))}
      </pre>
    </section>
  )
}
