interface ContextSectionProps {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
  empty?: boolean
}

export default function ContextSection({ title, icon, children, empty }: ContextSectionProps) {
  return (
    <div style={{
      background: '#0a1929',
      border: '1px solid var(--border)',
      borderRadius: 8,
      marginBottom: 16,
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        {icon}
        <h3 style={{
          fontSize: 15,
          fontWeight: 700,
          margin: 0,
          fontFamily: "'Krub', sans-serif",
          color: 'var(--text-primary)',
        }}>
          {title}
        </h3>
      </div>
      <div style={{ padding: '14px 18px' }}>
        {empty ? (
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, fontStyle: 'italic', fontFamily: "'Inter', sans-serif" }}>
            No items found
          </p>
        ) : children}
      </div>
    </div>
  )
}
