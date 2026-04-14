import { useState } from 'react'
import { CheckCircle, AlertCircle } from 'lucide-react'
import TokenField from './TokenField'
import type { ConnectionConfig, HealthStatus } from '@shared/types'

interface ConnectionFormProps {
  config: ConnectionConfig
  initialValues: Record<string, string>
  healthStatus: HealthStatus
  onSave: (values: Record<string, string>) => void
  onTest: () => Promise<{ success: boolean; message: string } | void>
  onCopyFromJira?: () => Promise<Record<string, string>>
}

export default function ConnectionForm({ config, initialValues, healthStatus, onSave, onTest, onCopyFromJira }: ConnectionFormProps) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {}
    for (const field of config.fields) {
      init[field.envKey] = initialValues[field.envKey] || ''
    }
    return init
  })
  const [editLocked, setEditLocked] = useState<Record<string, boolean>>(() => {
    const locked: Record<string, boolean> = {}
    for (const field of config.fields) {
      if (field.autoPopulated && initialValues[field.envKey]) {
        locked[field.envKey] = true
      }
    }
    return locked
  })
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  const handleFieldChange = (envKey: string, value: string) => {
    setValues((prev) => ({ ...prev, [envKey]: value }))
  }

  const handleUnlock = (envKey: string, confirmMessage?: string) => {
    if (confirmMessage) {
      const ok = window.confirm(confirmMessage)
      if (!ok) return
    }
    setEditLocked((prev) => ({ ...prev, [envKey]: false }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      onSave(values)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await onTest()
      if (result) {
        setTestResult(result)
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || 'Test failed' })
    } finally {
      setTesting(false)
    }
  }

  const handleCopyFromJira = async () => {
    if (!onCopyFromJira) return
    const jiraValues = await onCopyFromJira()
    setValues((prev) => ({ ...prev, ...jiraValues }))
  }

  return (
    <div>
      {/* Copy from Jira button for Confluence */}
      {config.linkedTo && onCopyFromJira && (
        <button
          onClick={handleCopyFromJira}
          style={{
            padding: '8px 16px',
            background: '#0a1929',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            fontSize: 13,
            marginBottom: 16,
            cursor: 'pointer',
          }}
        >
          Copy from Jira
        </button>
      )}

      {/* Help text */}
      <div style={{
        background: 'var(--bg-muted)',
        borderRadius: 'var(--radius-lg)',
        padding: 14,
        marginBottom: 24,
        fontSize: 13,
        color: 'var(--text-secondary)',
        lineHeight: 1.5,
      }}>
        {config.helpText}
      </div>

      {/* Fields */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {config.fields.map((field) => (
          <div key={field.envKey}>
            <label style={{
              display: 'block',
              fontSize: 12,
              fontWeight: 600,
              color: '#ffffff',
              marginBottom: 6,
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
            }}>
              {field.envKey}
            </label>
            {field.type === 'password' ? (
              <TokenField
                value={values[field.envKey]}
                onChange={(v) => handleFieldChange(field.envKey, v)}
                placeholder={field.placeholder}
                disabled={editLocked[field.envKey]}
              />
            ) : (
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={values[field.envKey]}
                  onChange={(e) => handleFieldChange(field.envKey, e.target.value)}
                  placeholder={field.placeholder}
                  disabled={editLocked[field.envKey]}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: '1px solid #ff008844',
                    background: '#0a1929',
                    color: '#ffffff',
                    borderRadius: 'var(--radius)',
                    fontSize: 14,
                    fontFamily: "'Inter', sans-serif",
                    boxSizing: 'border-box',
                    opacity: editLocked[field.envKey] ? 0.5 : 1,
                  }}
                />
                {editLocked[field.envKey] && (
                  <button
                    onClick={() => handleUnlock(field.envKey, field.confirmBeforeEdit)}
                    style={{
                      position: 'absolute',
                      right: 8,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      padding: '4px 8px',
                      fontSize: 11,
                      background: '#0a1929',
                      color: '#ffffff',
                      border: '1px solid var(--border)',
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                  >
                    Edit
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Buttons */}
      <div style={{ display: 'flex', gap: 12, marginTop: 24, alignItems: 'center' }}>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            padding: '10px 24px',
            background: 'var(--text-primary)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius)',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            opacity: saving ? 0.6 : 1,
          }}
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={handleTest}
          disabled={testing}
          style={{
            padding: '10px 24px',
            background: '#0a1929',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            fontSize: 14,
            fontWeight: 500,
            cursor: 'pointer',
            opacity: testing ? 0.6 : 1,
          }}
        >
          {testing ? 'Testing...' : 'Test Connection'}
        </button>
      </div>

      {/* Test result / health status */}
      {(testResult || (healthStatus.status === 'unhealthy' && healthStatus.message && !testResult)) && (
        <div style={{
          marginTop: 12,
          padding: '10px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          borderRadius: 'var(--radius)',
          background: (testResult?.success ?? false) ? '#0a2a1a' : '#2a0a0a',
          border: `1px solid ${(testResult?.success ?? false) ? '#bbf7d0' : '#fecaca'}`,
          fontSize: 13,
          fontFamily: "'Inter', sans-serif",
        }}>
          {(testResult?.success ?? false) ? (
            <CheckCircle size={16} color="#22c55e" style={{ flexShrink: 0 }} />
          ) : (
            <AlertCircle size={16} color="#ef4444" style={{ flexShrink: 0 }} />
          )}
          <span style={{ color: (testResult?.success ?? false) ? '#166534' : '#dc2626' }}>
            {testResult?.message || healthStatus.message}
          </span>
        </div>
      )}
    </div>
  )
}
