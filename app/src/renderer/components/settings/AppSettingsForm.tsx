import { useState, useEffect } from 'react'
import { SettingsSection } from './SettingsField'
import type { UpdateStatus, UpdateProgress, AppVersionInfo } from '../../../shared/types'

export default function AppSettingsForm() {
  const [versionInfo, setVersionInfo] = useState<AppVersionInfo | null>(null)
  const [pmosPath, setPmosPath] = useState<string | null>(null)
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>('idle')
  const [updateMessage, setUpdateMessage] = useState('')
  const [updatePercent, setUpdatePercent] = useState(0)

  useEffect(() => {
    window.api.getAppVersion().then(setVersionInfo)
    window.api.getPmosPath().then(setPmosPath)

    window.api.onUpdateProgress((progress: UpdateProgress) => {
      setUpdateStatus(progress.status)
      setUpdateMessage(progress.message)
      setUpdatePercent(progress.percent)
      if (progress.status === 'up-to-date') window.api.logTelemetryClick('update_up_to_date')
      if (progress.status === 'error') window.api.logTelemetryClick('error:update_failed')
    })

    return () => {
      window.api.removeUpdateProgressListener()
    }
  }, [])

  const handleUpdate = async () => {
    window.api.logTelemetryClick('update_started')
    setUpdateStatus('checking')
    setUpdateMessage('Checking for updates...')
    try {
      await window.api.startUpdate()
    } catch (err: any) {
      setUpdateStatus('error')
      setUpdateMessage(err.message || 'Update failed')
    }
  }

  const getButtonText = () => {
    switch (updateStatus) {
      case 'checking': return 'Checking...'
      case 'downloading': return `Downloading... ${updatePercent}%`
      case 'verifying': return 'Verifying...'
      case 'installing': return 'Installing...'
      case 'relaunching': return 'Relaunching...'
      case 'up-to-date': return 'Up to Date'
      case 'error': return 'Retry Update'
      default: return 'Update App'
    }
  }

  const isUpdating = ['checking', 'downloading', 'verifying', 'installing', 'relaunching'].includes(updateStatus)

  return (
    <div style={{ paddingTop: 16 }}>
      <SettingsSection title="App Version">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '8px 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span style={{ color: 'var(--text-secondary)' }}>PM-OS App Version</span>
            <span style={{ fontWeight: 600 }}>{versionInfo?.version || '...'}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span style={{ color: 'var(--text-secondary)' }}>Electron</span>
            <span>{versionInfo?.electronVersion || '...'}</span>
          </div>
          {pmosPath && (
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span style={{ color: 'var(--text-secondary)' }}>PM-OS Path</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{pmosPath}</span>
            </div>
          )}
        </div>
      </SettingsSection>

      <SettingsSection title="Update">
        <div style={{ padding: '8px 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <button
            onClick={handleUpdate}
            disabled={isUpdating}
            style={{
              padding: '10px 24px',
              background: updateStatus === 'up-to-date' ? '#16a34a' : updateStatus === 'error' ? '#dc2626' : 'var(--btn-primary-bg)',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              fontSize: 13,
              fontWeight: 600,
              cursor: isUpdating ? 'not-allowed' : 'pointer',
              opacity: isUpdating ? 0.7 : 1,
              fontFamily: "'Inter', sans-serif",
              width: '100%',
            }}
          >
            {getButtonText()}
          </button>

          {isUpdating && updateStatus === 'downloading' && (
            <div style={{ width: '100%', height: 4, background: '#0d2137', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: `${updatePercent}%`, height: '100%', background: 'var(--btn-primary-bg)', borderRadius: 2, transition: 'width 0.3s ease' }} />
            </div>
          )}

          {updateMessage && (
            <div style={{
              fontSize: 12,
              color: updateStatus === 'error' ? '#dc2626' : updateStatus === 'up-to-date' ? '#16a34a' : 'var(--text-secondary)',
              lineHeight: 1.4,
            }}>
              {updateMessage}
            </div>
          )}
        </div>
      </SettingsSection>

      <SettingsSection title="Support & Credits">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0', fontSize: 13 }}>
          <div style={{ color: 'var(--text-secondary)' }}>
            Developed by <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Nikita Gorshkov</span>
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>
            Part of the PM-OS open-source project
          </div>
          <div style={{ marginTop: 4 }}>
            <a
              href="#"
              onClick={(e) => { e.preventDefault(); window.api.openBrainFolder() }}
              style={{ color: 'var(--btn-primary-bg)', textDecoration: 'none', fontSize: 12 }}
            >
              Open PM-OS Folder
            </a>
          </div>
        </div>
      </SettingsSection>
    </div>
  )
}
