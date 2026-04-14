import { useState } from 'react'
import { CheckCircle, XCircle, Loader } from 'lucide-react'

interface VerifyButtonProps {
  connectionIds: string[]
  onVerify: (id: string) => Promise<{ success: boolean; message: string }>
  fieldValues: Record<string, string>
}

interface VerifyResult {
  connectionId: string
  success: boolean
  message: string
}

export default function VerifyButton({ connectionIds, onVerify, fieldValues }: VerifyButtonProps) {
  const [verifying, setVerifying] = useState(false)
  const [results, setResults] = useState<VerifyResult[]>([])
  const [lastFieldHash, setLastFieldHash] = useState('')

  // Clear results when fields change
  const fieldHash = JSON.stringify(fieldValues)
  if (fieldHash !== lastFieldHash && results.length > 0) {
    setResults([])
    setLastFieldHash(fieldHash)
  }

  const handleVerify = async () => {
    setVerifying(true)
    setLastFieldHash(fieldHash)
    const newResults: VerifyResult[] = []
    for (const id of connectionIds) {
      try {
        const result = await onVerify(id)
        newResults.push({ connectionId: id, ...result })
      } catch (err: any) {
        newResults.push({ connectionId: id, success: false, message: err.message || 'Unknown error' })
      }
    }
    // Deduplicate results with identical messages (e.g., Jira+Confluence share credentials)
    const seen = new Set<string>()
    const dedupedResults = newResults.filter((r) => {
      const key = `${r.success}:${r.message}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    setResults(dedupedResults)
    setVerifying(false)
  }

  return (
    <div style={{ marginTop: 20 }}>
      <button
        onClick={handleVerify}
        disabled={verifying}
        style={{
          padding: '10px 24px',
          background: 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid var(--btn-secondary-border)',
          borderRadius: 4,
          fontSize: 14,
          fontWeight: 500,
          cursor: verifying ? 'not-allowed' : 'pointer',
          opacity: verifying ? 0.6 : 1,
          fontFamily: "'Inter', sans-serif",
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        {verifying && <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />}
        {verifying ? 'Verifying...' : 'Verify Connection'}
      </button>

      {results.length > 0 && (
        <div style={{ marginTop: 12 }}>
          {results.map((r) => (
            <div
              key={r.connectionId}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 12px',
                marginBottom: 4,
                borderRadius: 4,
                background: r.success ? '#0a2a1a' : '#2a0a0a',
                border: `1px solid ${r.success ? '#bbf7d0' : '#fecaca'}`,
                fontSize: 13,
                fontFamily: "'Inter', sans-serif",
              }}
            >
              {r.success ? (
                <CheckCircle size={16} color="#22c55e" />
              ) : (
                <XCircle size={16} color="#ef4444" />
              )}
              <span style={{ color: r.success ? '#166534' : '#dc2626' }}>
                {r.message}
              </span>
            </div>
          ))}
        </div>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
