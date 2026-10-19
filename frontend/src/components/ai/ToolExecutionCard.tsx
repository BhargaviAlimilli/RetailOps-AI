export function ToolExecutionCard({
  name,
  status,
  detail,
}: {
  name: string
  status: string
  detail?: string
}) {
  return (
    <div className="tool-execution-card">
      <strong>{name.replaceAll('_', ' ')}</strong>
      <small>{status}</small>
      {detail && <p>{detail}</p>}
    </div>
  )
}
