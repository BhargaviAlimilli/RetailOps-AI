export function StreamingMessage({ text }: { text: string }) {
  return (
    <div role="status" className="ai-stream-state">
      {text}
    </div>
  )
}
