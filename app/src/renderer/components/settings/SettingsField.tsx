interface SettingsFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  type?: 'text' | 'number'
  placeholder?: string
  note?: string
}

export function SettingsField({ label, value, onChange, type = 'text', placeholder, note }: SettingsFieldProps) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4, fontFamily: "'Inter', sans-serif" }}>
        {label}
      </label>
      <input
        type={type}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%',
          padding: '8px 10px',
          background: '#0a1929',
          border: '1px solid #ff008844',
          borderRadius: 4,
          fontSize: 13,
          fontFamily: "'Inter', sans-serif",
          boxSizing: 'border-box' as const,
          outline: 'none',
          color: '#ffffff',
        }}
      />
      {note && <p style={{ fontSize: 11, fontStyle: 'italic', color: '#778899', marginTop: 2, marginBottom: 0 }}>{note}</p>}
    </div>
  )
}

interface SettingsToggleProps {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
}

export function SettingsToggle({ label, checked, onChange }: SettingsToggleProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, padding: '4px 0' }}>
      <span style={{ fontSize: 13, fontFamily: "'Inter', sans-serif" }}>{label}</span>
      <label style={{ position: 'relative', display: 'inline-block', width: 36, height: 20, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={checked ?? false}
          onChange={(e) => onChange(e.target.checked)}
          style={{ opacity: 0, width: 0, height: 0 }}
        />
        <span style={{
          position: 'absolute',
          inset: 0,
          background: checked ? '#ff0088' : '#778899',
          borderRadius: 10,
          transition: 'background 0.2s',
        }}>
          <span style={{
            position: 'absolute',
            left: checked ? 18 : 2,
            top: 2,
            width: 16,
            height: 16,
            background: 'white',
            borderRadius: '50%',
            transition: 'left 0.2s',
          }} />
        </span>
      </label>
    </div>
  )
}

interface SettingsSelectProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: Array<{ value: string; label: string }>
}

export function SettingsSelect({ label, value, onChange, options }: SettingsSelectProps) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4, fontFamily: "'Inter', sans-serif" }}>
        {label}
      </label>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: '100%',
          padding: '8px 10px',
          background: '#0a1929',
          border: '1px solid #ff008844',
          borderRadius: 4,
          fontSize: 13,
          fontFamily: "'Inter', sans-serif",
          boxSizing: 'border-box' as const,
          outline: 'none',
          cursor: 'pointer',
          color: '#ffffff',
        }}
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}

export function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h4 style={{ fontSize: 14, fontWeight: 700, fontFamily: "'Krub', sans-serif", marginBottom: 12, marginTop: 0, color: 'var(--text-primary)' }}>
        {title}
      </h4>
      {children}
    </div>
  )
}
