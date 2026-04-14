import { useState, useEffect } from 'react'
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import type { ConfigValidationResult } from '@shared/types'

export default function UserSetupStep7() {
  const [validation, setValidation] = useState<ConfigValidationResult | null>(null)
  const [countdown, setCountdown] = useState(5)

  useEffect(() => {
    window.api.validateConfig().then(setValidation)
  }, [])

  useEffect(() => {
    if (validation === null) return

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          window.api.completeUserSetup()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [validation])

  const renderStatusIcon = () => {
    if (!validation) return null
    if (!validation.valid) return <XCircle size={48} color="#ef4444" />
    if (validation.warnings.length > 0) return <AlertTriangle size={48} color="#f59e0b" />
    return <CheckCircle size={48} color="#22c55e" />
  }

  return (
    <div style={{
      width: '100%',
      height: '100vh',
      background: 'var(--bg-onboarding)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <div style={{
        textAlign: 'center',
        maxWidth: 480,
        padding: '0 32px',
      }}>
        <div style={{ marginBottom: 24 }}>
          {renderStatusIcon()}
        </div>

        <h1 style={{
          fontFamily: "'Krub', sans-serif",
          fontWeight: 700,
          fontSize: 24,
          marginBottom: 16,
          color: 'var(--text-primary)',
        }}>
          {validation?.valid !== false ? 'Your settings are stored' : 'Settings saved with issues'}
        </h1>

        <p style={{
          fontSize: 15,
          color: 'var(--text-secondary)',
          lineHeight: 1.6,
          marginBottom: 24,
          fontFamily: "'Inter', sans-serif",
        }}>
          You can now open Claude Code in your terminal and launch the command{' '}
          <code style={{
            background: '#0d2137',
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 14,
            fontFamily: "'SF Mono', 'Menlo', monospace",
          }}>
            /session boot
          </code>
        </p>

        {validation?.errors && validation.errors.length > 0 && (
          <div style={{
            textAlign: 'left',
            padding: 12,
            background: '#2a0a0a',
            border: '1px solid #fecaca',
            borderRadius: 6,
            marginBottom: 12,
            fontSize: 13,
            color: '#dc2626',
          }}>
            {validation.errors.map((e, i) => <div key={i}>{e}</div>)}
          </div>
        )}

        {validation?.warnings && validation.warnings.length > 0 && (
          <div style={{
            textAlign: 'left',
            padding: 12,
            background: '#2a2200',
            border: '1px solid #fed7aa',
            borderRadius: 6,
            marginBottom: 12,
            fontSize: 13,
            color: '#92400e',
          }}>
            {validation.warnings.map((w, i) => <div key={i}>{w}</div>)}
          </div>
        )}

        {/* Progress bar countdown */}
        <div style={{
          marginTop: 24,
          height: 4,
          background: '#0d2137',
          borderRadius: 2,
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            background: '#ff0088',
            width: `${((5 - countdown) / 5) * 100}%`,
            transition: 'width 1s linear',
            borderRadius: 2,
          }} />
        </div>
        <p style={{ fontSize: 12, color: '#778899', marginTop: 8, fontFamily: "'Inter', sans-serif" }}>
          Continuing in {countdown}s...
        </p>
      </div>
    </div>
  )
}
