import { useState } from 'react'

interface DevCredentialsProps {
  isDevMode: boolean
  onLoadCredentials: () => Promise<Record<string, string>>
  onApplyCredentials: (values: Record<string, string>) => void
}

export default function DevCredentials({ isDevMode, onLoadCredentials, onApplyCredentials }: DevCredentialsProps) {
  const [loading, setLoading] = useState(false)

  if (!isDevMode) return null

  const handleLoad = async () => {
    setLoading(true)
    try {
      const creds = await onLoadCredentials()
      onApplyCredentials(creds)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleLoad}
      disabled={loading}
      style={{
        padding: '4px 12px',
        background: '#fbbf24',
        color: '#1a1a1a',
        border: 'none',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 700,
        cursor: loading ? 'not-allowed' : 'pointer',
        fontFamily: "'SF Mono', 'Menlo', monospace",
      }}
    >
      {loading ? 'Loading...' : 'Test Credentials'}
    </button>
  )
}
