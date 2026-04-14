interface SettingsFooterProps {
  onSave: () => void
  onCancel: () => void
  saving?: boolean
}

export default function SettingsFooter({ onSave, onCancel, saving }: SettingsFooterProps) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'flex-end',
      gap: 12,
      padding: '16px 24px',
      borderTop: '1px solid var(--border)',
      background: '#0a1929',
    }}>
      <button
        onClick={onCancel}
        style={{
          padding: '8px 20px',
          background: 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid var(--btn-secondary-border)',
          borderRadius: 4,
          fontSize: 13,
          fontWeight: 500,
          cursor: 'pointer',
          fontFamily: "'Inter', sans-serif",
        }}
      >
        Cancel
      </button>
      <button
        onClick={onSave}
        disabled={saving}
        style={{
          padding: '8px 24px',
          background: 'var(--btn-primary-bg)',
          color: 'var(--btn-primary-text)',
          border: 'none',
          borderRadius: 4,
          fontSize: 13,
          fontWeight: 600,
          cursor: saving ? 'not-allowed' : 'pointer',
          opacity: saving ? 0.6 : 1,
          fontFamily: "'Inter', sans-serif",
        }}
      >
        {saving ? 'Saving...' : 'Save'}
      </button>
    </div>
  )
}
