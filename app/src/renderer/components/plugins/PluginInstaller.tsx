import { useState } from 'react'
import { CheckCircle, AlertCircle, Loader } from 'lucide-react'
import type { PluginActionResult } from '@shared/types'

interface PluginInstallerProps {
  pluginId: string
  action: 'install' | 'disable'
  onComplete: (result: PluginActionResult) => void
  onCancel: () => void
}

export default function PluginInstaller({ pluginId, action, onComplete, onCancel }: PluginInstallerProps) {
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<PluginActionResult | null>(null)

  const handleAction = async () => {
    setRunning(true)
    try {
      const res = action === 'install'
        ? await window.api.installPlugin(pluginId)
        : await window.api.disablePlugin(pluginId)
      setResult(res)
      onComplete(res)
    } catch (err: any) {
      const failResult: PluginActionResult = {
        success: false,
        pluginId,
        action,
        error: err.message,
      }
      setResult(failResult)
      onComplete(failResult)
    } finally {
      setRunning(false)
    }
  }

  if (result) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 12px',
        background: result.success ? '#0a2a1a' : '#2a0a0a',
        border: `1px solid ${result.success ? '#bbf7d0' : '#fecaca'}`,
        borderRadius: 6,
        fontSize: 13,
        fontFamily: "'Inter', sans-serif",
        color: result.success ? '#166534' : '#dc2626',
      }}>
        {result.success ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
        {result.success ? `Plugin ${action === 'install' ? 'installed' : 'disabled'} successfully` : result.error}
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '8px 12px',
      background: '#2a2200',
      border: '1px solid #fde68a',
      borderRadius: 6,
      fontSize: 13,
      fontFamily: "'Inter', sans-serif",
    }}>
      {running ? (
        <>
          <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />
          <span>{action === 'install' ? 'Installing' : 'Disabling'} {pluginId}...</span>
        </>
      ) : (
        <>
          <span>{action === 'install' ? 'Install' : 'Disable'} {pluginId}?</span>
          <button
            onClick={handleAction}
            style={{
              padding: '4px 10px',
              fontSize: 12,
              fontWeight: 600,
              border: 'none',
              borderRadius: 4,
              background: action === 'install' ? 'black' : '#dc2626',
              color: 'white',
              cursor: 'pointer',
              fontFamily: "'Inter', sans-serif",
            }}
          >
            Confirm
          </button>
          <button
            onClick={onCancel}
            style={{
              padding: '4px 10px',
              fontSize: 12,
              border: '1px solid var(--border)',
              borderRadius: 4,
              background: '#0a1929',
              color: '#ffffff',
              cursor: 'pointer',
              fontFamily: "'Inter', sans-serif",
            }}
          >
            Cancel
          </button>
        </>
      )}
    </div>
  )
}
