import ConnectionCard from './ConnectionCard'
import type { ConnectionState } from '@shared/types'

interface ConnectionGridProps {
  connections: ConnectionState[]
  onCardClick: (id: string) => void
  dimmed?: boolean
}

export default function ConnectionGrid({ connections, onCardClick, dimmed }: ConnectionGridProps) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 12,
      opacity: dimmed ? 0.3 : 1,
      transition: 'opacity 0.2s',
      pointerEvents: dimmed ? 'none' : 'auto',
    }}>
      {connections.map((conn) => (
        <ConnectionCard
          key={conn.id}
          connection={conn}
          onClick={() => onCardClick(conn.id)}
        />
      ))}
    </div>
  )
}
