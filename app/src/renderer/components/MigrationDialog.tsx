import { useState, useEffect } from 'react'
import { X, ArrowUpCircle, CheckCircle, AlertCircle, Loader } from 'lucide-react'
import type { MigrationProgress, MigrationStep } from '@shared/types'

interface MigrationDialogProps {
  isOpen: boolean
  onClose: () => void
}

const STEP_LABELS: Record<MigrationStep, string> = {
  'analyzing': 'Analyzing installation...',
  'confirming': 'Confirming changes...',
  'backing-up': 'Creating backup...',
  'migrating': 'Migrating to v5.0...',
  'validating': 'Validating migration...',
  'done': 'Migration complete!',
  'error': 'Migration failed',
}

const STEP_ORDER: MigrationStep[] = [
  'analyzing', 'confirming', 'backing-up', 'migrating', 'validating', 'done',
]

export default function MigrationDialog({ isOpen, onClose }: MigrationDialogProps) {
  const [started, setStarted] = useState(false)
  const [progress, setProgress] = useState<MigrationProgress | null>(null)
  const [rollingBack, setRollingBack] = useState(false)

  useEffect(() => {
    if (!isOpen) {
      setStarted(false)
      setProgress(null)
      setRollingBack(false)
      return
    }
  }, [isOpen])

  useEffect(() => {
    if (!started) return

    window.api.onMigrationProgress((p: MigrationProgress) => {
      setProgress(p)
    })

    return () => {
      window.api.removeMigrationProgressListener()
    }
  }, [started])

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !started) onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, started, onClose])

  const handleUpgrade = async () => {
    setStarted(true)
    window.api.logTelemetryClick('migration_start')
    try {
      await window.api.startMigration()
    } catch {
      setProgress({ step: 'error', percent: 0, message: 'Failed to start migration' })
    }
  }

  const handleRollback = async () => {
    setRollingBack(true)
    window.api.logTelemetryClick('migration_rollback')
    try {
      const result = await window.api.rollbackMigration()
      if (result.success) {
        setProgress({ step: 'done', percent: 100, message: 'Rollback completed. Restart the app.' })
      } else {
        setProgress({ step: 'error', percent: 0, message: `Rollback failed: ${result.error}` })
      }
    } finally {
      setRollingBack(false)
    }
  }

  if (!isOpen) return null

  const isDone = progress?.step === 'done'
  const isError = progress?.step === 'error'

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={started ? undefined : onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.3)',
          zIndex: 22,
        }}
      />

      {/* Dialog */}
      <div style={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 480,
        maxHeight: '80vh',
        background: '#0a1929',
        borderRadius: 8,
        boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
        zIndex: 25,
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '20px 24px 12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ArrowUpCircle size={20} color="var(--hf-green)" />
            <h3 style={{
              margin: 0, fontSize: 18, fontWeight: 700,
              fontFamily: "'Inter', sans-serif", color: '#ffffff',
            }}>
              Upgrade to PM-OS v5.0
            </h3>
          </div>
          {!started && (
            <button
              onClick={onClose}
              style={{
                width: 28, height: 28, borderRadius: 4, border: '1px solid #ff008844',
                background: '#0a1929', display: 'flex', alignItems: 'center',
                justifyContent: 'center', cursor: 'pointer', padding: 0,
              }}
            >
              <X size={14} color="#aabbcc" />
            </button>
          )}
        </div>

        {/* Content */}
        <div style={{ padding: '0 24px 20px', overflowY: 'auto', flex: 1 }}>
          {!started ? (
            <>
              <p style={{
                fontSize: 14, color: '#aabbcc', lineHeight: 1.6, marginBottom: 16,
                fontFamily: "'Inter', sans-serif",
              }}>
                A v4.x PM-OS installation was detected. Upgrade to v5.0 to unlock the new modular plugin architecture.
              </p>
              <div style={{
                padding: 12, background: '#0a2a1a', border: '1px solid #bbf7d0', borderRadius: 6,
                fontSize: 13, lineHeight: 1.6, fontFamily: "'Inter', sans-serif", color: '#166534',
              }}>
                <strong>What&apos;s new in v5.0:</strong>
                <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                  <li>7 modular plugins (install only what you need)</li>
                  <li>Claude Cowork compatible</li>
                  <li>Faster boot with independent plugin loading</li>
                  <li>Automatic backup of v4.x data before migration</li>
                </ul>
              </div>
            </>
          ) : (
            <div>
              {/* Progress bar */}
              <div style={{
                width: '100%', height: 6, background: '#0d2137', borderRadius: 3,
                marginBottom: 16, overflow: 'hidden',
              }}>
                <div style={{
                  width: `${progress?.percent || 0}%`,
                  height: '100%',
                  background: isError ? '#dc2626' : isDone ? '#16a34a' : 'var(--hf-green)',
                  borderRadius: 3,
                  transition: 'width 0.3s ease',
                }} />
              </div>

              {/* Steps */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {STEP_ORDER.map((stepKey) => {
                  const currentIdx = progress ? STEP_ORDER.indexOf(progress.step) : -1
                  const thisIdx = STEP_ORDER.indexOf(stepKey)
                  const isActive = progress?.step === stepKey
                  const isCompleted = currentIdx > thisIdx
                  const isPending = currentIdx < thisIdx

                  return (
                    <div key={stepKey} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      fontSize: 13, fontFamily: "'Inter', sans-serif",
                      color: isActive ? '#ffffff' : isCompleted ? '#16a34a' : '#778899',
                    }}>
                      {isCompleted ? (
                        <CheckCircle size={14} color="#16a34a" />
                      ) : isActive ? (
                        <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />
                      ) : (
                        <div style={{ width: 14, height: 14, borderRadius: '50%', border: '1px solid #ff008844' }} />
                      )}
                      <span>{STEP_LABELS[stepKey]}</span>
                    </div>
                  )
                })}
              </div>

              {/* Progress message */}
              {progress?.message && (
                <div style={{
                  marginTop: 12, padding: '8px 12px',
                  background: isError ? '#2a0a0a' : '#0d2137',
                  border: `1px solid ${isError ? '#fecaca' : '#ff008844'}`,
                  borderRadius: 4, fontSize: 12,
                  color: isError ? '#dc2626' : '#aabbcc',
                  fontFamily: "'Inter', sans-serif",
                }}>
                  {progress.message}
                </div>
              )}

              {/* Report summary */}
              {isDone && progress?.report && (
                <div style={{
                  marginTop: 12, padding: 12, background: '#0a2a1a',
                  border: '1px solid #bbf7d0', borderRadius: 6, fontSize: 12,
                  fontFamily: "'Inter', sans-serif", color: '#166534',
                }}>
                  <div>Plugins to install: {progress.report.pluginsToInstall.join(', ')}</div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 24px 20px',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 8,
        }}>
          {!started && (
            <>
              <button
                onClick={onClose}
                style={{
                  padding: '8px 20px', fontSize: 13, fontWeight: 500,
                  border: '1px solid var(--border)', borderRadius: 4, background: '#0a1929',
                  color: '#ffffff', cursor: 'pointer', fontFamily: "'Inter', sans-serif",
                }}
              >
                Later
              </button>
              <button
                onClick={handleUpgrade}
                style={{
                  padding: '8px 20px', fontSize: 13, fontWeight: 600,
                  border: 'none', borderRadius: 4, background: 'black', color: 'white',
                  cursor: 'pointer', fontFamily: "'Inter', sans-serif",
                }}
              >
                Upgrade to v5.0
              </button>
            </>
          )}
          {isError && (
            <button
              onClick={handleRollback}
              disabled={rollingBack}
              style={{
                padding: '8px 20px', fontSize: 13, fontWeight: 500,
                border: '1px solid #fecaca', borderRadius: 4, background: '#2a0a0a',
                color: '#dc2626', cursor: rollingBack ? 'not-allowed' : 'pointer',
                opacity: rollingBack ? 0.5 : 1, fontFamily: "'Inter', sans-serif",
              }}
            >
              {rollingBack ? 'Rolling back...' : 'Rollback'}
            </button>
          )}
          {(isDone || isError) && (
            <button
              onClick={onClose}
              style={{
                padding: '8px 20px', fontSize: 13, fontWeight: 600,
                border: 'none', borderRadius: 4, background: 'black', color: 'white',
                cursor: 'pointer', fontFamily: "'Inter', sans-serif",
              }}
            >
              Close
            </button>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </>
  )
}
