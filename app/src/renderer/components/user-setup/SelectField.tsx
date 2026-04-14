interface SelectFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: Array<{ value: string; label: string }>
  required?: boolean
  placeholder?: string
}

export default function SelectField({ label, value, onChange, options, required, placeholder }: SelectFieldProps) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{
        display: 'block',
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--text-primary)',
        marginBottom: 6,
        fontFamily: "'Inter', sans-serif",
      }}>
        {label}
        {required && <span style={{ color: '#ef4444', marginLeft: 2 }}>*</span>}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: '100%',
          padding: '10px 12px',
          background: '#0a1929',
          border: '1px solid #ff008844',
          borderRadius: 4,
          fontSize: 14,
          fontFamily: "'Inter', sans-serif",
          boxSizing: 'border-box' as const,
          outline: 'none',
          cursor: 'pointer',
          color: value ? '#ffffff' : '#778899',
        }}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  )
}
