import type { SettingsCategory } from './SettingsPanel'

interface SettingsCategoryListProps {
  active: SettingsCategory
  onChange: (category: SettingsCategory) => void
}

const CATEGORIES: Array<{ id: SettingsCategory; label: string }> = [
  { id: 'user', label: 'User' },
  { id: 'integrations', label: 'Integrations' },
  { id: 'pmos', label: 'PM-OS' },
  { id: 'wcr', label: 'WCR' },
  { id: 'app', label: 'App' },
]

export default function SettingsCategoryList({ active, onChange }: SettingsCategoryListProps) {
  return (
    <div style={{
      display: 'flex',
      gap: 0,
      borderBottom: '1px solid var(--border)',
      padding: '0 24px',
      overflowX: 'auto',
    }}>
      {CATEGORIES.map((cat) => (
        <button
          key={cat.id}
          onClick={() => onChange(cat.id)}
          style={{
            padding: '10px 14px',
            background: 'none',
            border: 'none',
            borderBottom: active === cat.id ? '2px solid var(--btn-primary-bg)' : '2px solid transparent',
            fontSize: 13,
            fontWeight: active === cat.id ? 600 : 400,
            color: active === cat.id ? 'var(--text-primary)' : 'var(--text-secondary)',
            cursor: 'pointer',
            fontFamily: "'Inter', sans-serif",
            whiteSpace: 'nowrap',
          }}
        >
          {cat.label}
        </button>
      ))}
    </div>
  )
}
