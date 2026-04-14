import { useState, useEffect, useCallback } from 'react'
import { X } from 'lucide-react'

interface BugReportPopupProps {
  isOpen: boolean
  onClose: () => void
}

export default function BugReportPopup({ isOpen, onClose }: BugReportPopupProps) {
  const [diagnosticData, setDiagnosticData] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const fetchDiagnostics = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await window.api.getDiagnosticBundle()
      if (result.success) {
        setDiagnosticData(result.data)
      } else {
        setError(result.error || 'Could not load diagnostic data')
      }
    } catch (err: any) {
      setError(err.message || 'Could not load diagnostic data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isOpen) {
      setDiagnosticData(null)
      setCopied(false)
      fetchDiagnostics()
    }
  }, [isOpen, fetchDiagnostics])

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  const handleCopy = async () => {
    if (!diagnosticData) return
    try {
      await navigator.clipboard.writeText(diagnosticData)
      window.api.logTelemetryClick('bug_report_copied')
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard API may fail in some contexts
    }
  }

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.3)',
          zIndex: 22,
        }}
      />

      {/* Popup */}
      <div style={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 520,
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
          <h3 style={{
            margin: 0,
            fontSize: 18,
            fontWeight: 700,
            fontFamily: "'Inter', sans-serif",
            color: '#ffffff',
          }}>
            Report a Bug
          </h3>
          <button
            onClick={onClose}
            style={{
              width: 28,
              height: 28,
              borderRadius: 4,
              border: '1px solid #ff008844',
              background: '#0a1929',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            <X size={14} color="#aabbcc" />
          </button>
        </div>

        {/* Description */}
        <div style={{
          padding: '0 24px 16px',
          fontSize: 14,
          color: '#aabbcc',
          fontFamily: "'Inter', sans-serif",
        }}>
          Describe your issue and post this in #pm-os-support
        </div>

        {/* Log snippet area */}
        <div style={{
          margin: '0 24px',
          background: '#dc2626',
          borderRadius: 6,
          padding: 16,
          maxHeight: 400,
          overflowY: 'auto',
          flex: '1 1 auto',
        }}>
          {loading ? (
            <div style={{
              color: 'white',
              fontSize: 13,
              fontFamily: "'Inter', sans-serif",
            }}>
              Loading diagnostic data...
            </div>
          ) : error ? (
            <div style={{
              color: 'white',
              fontSize: 13,
              fontFamily: "'Inter', sans-serif",
            }}>
              {error}
            </div>
          ) : diagnosticData ? (
            <pre style={{
              margin: 0,
              fontFamily: 'monospace',
              fontSize: 11,
              color: 'white',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              lineHeight: 1.5,
            }}>
              {diagnosticData}
            </pre>
          ) : (
            <div style={{
              color: 'white',
              fontSize: 13,
              fontFamily: "'Inter', sans-serif",
            }}>
              No recent logs available
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 24px' }}>
          <button
            onClick={handleCopy}
            disabled={!diagnosticData || loading}
            style={{
              width: '100%',
              padding: '10px 24px',
              background: 'black',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              fontSize: 13,
              fontWeight: 600,
              cursor: diagnosticData && !loading ? 'pointer' : 'not-allowed',
              opacity: diagnosticData && !loading ? 1 : 0.5,
              fontFamily: "'Inter', sans-serif",
            }}
          >
            {copied ? 'Copied!' : 'Copy to Clipboard'}
          </button>
        </div>
      </div>
    </>
  )
}
