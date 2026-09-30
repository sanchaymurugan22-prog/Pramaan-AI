// Decorative line mandala used in the dashboard hero (drawn the same way as the prototype).
type Props = { size: number; petals: number; color: string; opacity: number }

export function Mandala({ size, petals, color, opacity }: Props) {
  const half = size / 2
  const angles = Array.from({ length: petals }, (_, i) => (360 / petals) * i)
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <g fill="none" stroke={color} strokeOpacity={opacity} strokeWidth="1.4" transform={`translate(${half} ${half})`}>
        <circle r={size * 0.46} />
        <circle r={size * 0.4} strokeDasharray="2 5" />
        {angles.map((a) => (
          <ellipse key={a} cx="0" cy={-size * 0.27} rx={size * 0.07} ry={size * 0.17} transform={`rotate(${a})`} />
        ))}
        <circle r={size * 0.09} />
        <circle r={size * 0.04} />
      </g>
    </svg>
  )
}
