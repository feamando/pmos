import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import type { FieldConfig } from '@shared/types'

interface FormFieldProps {
  field: FieldConfig
  value: string
  onChange: (value: string) => void
  error?: boolean
}

export default function FormField({ field, value, onChange, error }: FormFieldProps) {
  const [revealed, setRevealed] = useState(false)
  const isPassword = field.type === 'password'

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: isPassword ? '10px 40px 10px 12px' : '10px 12px',
    background: '#0a1929',
    border: `1px solid ${error ? '#ef4444' : '#ff008844'}`,
    color: '#ffffff',
    borderRadius: 4,
    fontSize: 14,
    fontFamily: "'Inter', sans-serif",
    boxSizing: 'border-box' as const,
    outline: 'none',
    transition: 'border-color 0.2s ease',
  }

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
        {field.label}
        {field.required && <span style={{ color: '#ef4444', marginLeft: 2 }}>*</span>}
      </label>
      <div style={{ position: 'relative' }}>
        <input
          type={isPassword && !revealed ? 'password' : 'text'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          style={inputStyle}
          onFocus={(e) => { e.target.style.borderColor = '#ff0088' }}
          onBlur={(e) => { e.target.style.borderColor = error ? '#ef4444' : '#ff008844' }}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setRevealed(!revealed)}
            style={{
              position: 'absolute',
              right: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 4,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {revealed ? <EyeOff size={16} color="var(--text-muted)" /> : <Eye size={16} color="var(--text-muted)" />}
          </button>
        )}
      </div>
    </div>
  )
}
