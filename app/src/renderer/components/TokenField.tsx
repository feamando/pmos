import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

interface TokenFieldProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
}

export default function TokenField({ value, onChange, placeholder, disabled }: TokenFieldProps) {
  const [revealed, setRevealed] = useState(false)

  return (
    <div style={{ position: 'relative' }}>
      <input
        type={revealed ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        style={{
          width: '100%',
          padding: '10px 40px 10px 12px',
          border: '1px solid #ff008844',
          background: '#0a1929',
          color: '#ffffff',
          borderRadius: 'var(--radius)',
          fontSize: 14,
          fontFamily: "'Inter', sans-serif",
          boxSizing: 'border-box',
          opacity: disabled ? 0.5 : 1,
        }}
      />
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
    </div>
  )
}
