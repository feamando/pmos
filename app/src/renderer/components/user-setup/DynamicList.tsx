import { Plus, X } from 'lucide-react'

interface DynamicListProps<T> {
  items: T[]
  onAdd: () => void
  onRemove: (index: number) => void
  onUpdate: (index: number, item: T) => void
  maxItems: number
  minItems?: number
  renderItem: (item: T, index: number, onUpdate: (item: T) => void) => React.ReactNode
  addLabel?: string
}

export default function DynamicList<T>({
  items,
  onAdd,
  onRemove,
  onUpdate,
  maxItems,
  minItems = 0,
  renderItem,
  addLabel = 'Add',
}: DynamicListProps<T>) {
  return (
    <div>
      {items.map((item, index) => (
        <div key={index} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
          <div style={{ flex: 1 }}>
            {renderItem(item, index, (updated) => onUpdate(index, updated))}
          </div>
          {items.length > minItems && (
            <button
              type="button"
              onClick={() => onRemove(index)}
              style={{
                marginTop: 28,
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 4,
                color: '#ef4444',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>
      ))}
      {items.length < maxItems && (
        <button
          type="button"
          onClick={onAdd}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 16px',
            background: 'none',
            border: '1px dashed #ff008844',
            borderRadius: 4,
            color: '#ffffff',
            fontSize: 13,
            cursor: 'pointer',
            fontFamily: "'Inter', sans-serif",
            marginTop: 4,
          }}
        >
          <Plus size={14} />
          {addLabel}
        </button>
      )}
    </div>
  )
}
