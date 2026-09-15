interface Props {
  headlines: string[]
}

export default function HeadlinesFeed({ headlines }: Props) {
  if (headlines.length === 0) {
    return <div className="text-gray-600 text-sm py-4 text-center">No headlines</div>
  }

  return (
    <ul className="space-y-2">
      {headlines.map((h, i) => (
        <li key={i} className="text-sm text-gray-300 flex gap-2">
          <span className="text-gray-600 shrink-0 mt-0.5">•</span>
          <span>{h}</span>
        </li>
      ))}
    </ul>
  )
}
