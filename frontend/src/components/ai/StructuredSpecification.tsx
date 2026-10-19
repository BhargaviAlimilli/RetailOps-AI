export type SpecificationSection = {
  heading: string
  fields: { label: string; value: string }[]
}
export function StructuredSpecification({
  title,
  sections,
}: {
  title: string
  sections: SpecificationSection[]
}) {
  return (
    <section className="ai-specification" aria-label={title}>
      <h3>{title}</h3>
      {sections.map((section) => (
        <section key={section.heading}>
          <h4>{section.heading}</h4>
          <dl>
            {section.fields.map((field) => (
              <div key={field.label}>
                <dt>{field.label}</dt>
                <dd>{field.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </section>
  )
}
