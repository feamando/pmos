import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import SettingsCategoryList from './SettingsCategoryList'
import SettingsFooter from './SettingsFooter'
import UserSettingsForm from './UserSettingsForm'
import IntegrationSettingsForm from './IntegrationSettingsForm'
import PmosSettingsForm from './PmosSettingsForm'
import WcrSettingsForm from './WcrSettingsForm'
import AppSettingsForm from './AppSettingsForm'

export type SettingsCategory = 'user' | 'integrations' | 'pmos' | 'wcr' | 'app'

interface SettingsPanelProps {
  isOpen: boolean
  onClose: () => void
}

export default function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>('user')
  const [configData, setConfigData] = useState<Record<string, any>>({})
  const [editData, setEditData] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      loadConfig()
    }
  }, [isOpen])

  const loadConfig = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await window.api.loadConfigYaml()
      if (result.success) {
        setConfigData(result.data)
        setEditData(structuredClone(result.data))
      } else {
        setError(result.error || 'Failed to load config')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const result = await window.api.saveConfigYaml(editData)
      if (result.success) {
        setConfigData(structuredClone(editData))
        onClose()
        window.api.logTelemetryClick('settings_saved')
      } else {
        setError(result.error || 'Failed to save')
        window.api.logTelemetryClick('error:settings_save_failed')
      }
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditData(structuredClone(configData))
    onClose()
  }

  const updateSection = (section: string, value: any) => {
    setEditData((prev) => ({ ...prev, [section]: value }))
  }

  const renderContent = () => {
    // App tab doesn't depend on config.yaml — skip loading/error states
    if (activeCategory === 'app') {
      return <AppSettingsForm />
    }

    if (loading) {
      return <div style={{ padding: 24, color: 'var(--text-muted)', textAlign: 'center' }}>Loading settings...</div>
    }

    if (error) {
      return (
        <div style={{ padding: 24 }}>
          <div style={{
            padding: 16,
            background: '#2a0a0a',
            border: '1px solid #fecaca',
            borderRadius: 6,
            fontSize: 13,
            color: '#dc2626',
            lineHeight: 1.6,
          }}>
            config.yaml configuration does not match. Please edit config.yaml file directly.
            <div style={{ marginTop: 8, fontSize: 12, color: '#778899' }}>{error}</div>
          </div>
        </div>
      )
    }

    switch (activeCategory) {
      case 'user':
        return <UserSettingsForm data={editData} onChange={updateSection} />
      case 'integrations':
        return <IntegrationSettingsForm data={editData} onChange={updateSection} />
      case 'pmos':
        return <PmosSettingsForm data={editData} onChange={updateSection} />
      case 'wcr':
        return <WcrSettingsForm data={editData} onChange={updateSection} />
      case 'app':
        return <AppSettingsForm />
    }
  }

  return (
    <>
      {isOpen && (
        <div
          onClick={handleCancel}
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(0,0,0,0.05)',
            zIndex: 10,
          }}
        />
      )}

      <div style={{
        position: 'absolute',
        right: 0,
        top: 0,
        bottom: 0,
        width: 480,
        background: '#0a1929',
        boxShadow: isOpen ? '-4px 0 24px rgba(0,0,0,0.12)' : 'none',
        transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.2s ease-out',
        zIndex: 20,
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '20px 24px 16px',
          borderBottom: '1px solid var(--border)',
        }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Settings</h2>
          <button
            onClick={handleCancel}
            style={{
              width: 28,
              height: 28,
              borderRadius: 'var(--radius)',
              border: '1px solid var(--border)',
              background: '#0a1929',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
          >
            <X size={14} color="var(--text-secondary)" />
          </button>
        </div>

        {/* Category tabs */}
        <SettingsCategoryList active={activeCategory} onChange={setActiveCategory} />

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 24px' }}>
          {renderContent()}
        </div>

        {/* Footer — hidden for app tab (no config to save) */}
        {!loading && !error && activeCategory !== 'app' && (
          <SettingsFooter onSave={handleSave} onCancel={handleCancel} saving={saving} />
        )}
      </div>
    </>
  )
}
