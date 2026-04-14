interface AuthOption {
  id: string
  label: string
  enabled: boolean
}

interface AuthMethodTabsProps {
  options: AuthOption[]
  activeTab: string
  onTabChange: (tabId: string) => void
}

export default function AuthMethodTabs({ options, activeTab, onTabChange }: AuthMethodTabsProps) {
  return (
    <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid #ff008844', marginBottom: 24 }}>
      {options.map((opt) => {
        const isActive = activeTab === opt.id
        const isDisabled = !opt.enabled

        return (
          <button
            key={opt.id}
            onClick={() => {
              if (!isDisabled) onTabChange(opt.id)
            }}
            style={{
              padding: '10px 20px',
              background: 'none',
              border: 'none',
              borderBottom: isActive ? '2px solid var(--btn-primary-bg)' : '2px solid transparent',
              fontFamily: "'Inter', sans-serif",
              fontSize: 14,
              fontWeight: isActive ? 600 : 400,
              color: isDisabled ? 'var(--text-muted)' : isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
              cursor: isDisabled ? 'not-allowed' : 'pointer',
              opacity: isDisabled ? 0.5 : 1,
              position: 'relative',
            }}
          >
            {opt.label}
            {isDisabled && (
              <span style={{
                fontSize: 10,
                background: '#0d2137',
                color: 'var(--text-muted)',
                padding: '1px 6px',
                borderRadius: 8,
                marginLeft: 6,
                fontWeight: 400,
              }}>
                Coming soon
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
