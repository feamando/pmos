import { useState } from 'react'
import { Bug } from 'lucide-react'
import BugReportPopup from './BugReportPopup'

export default function BugReportButton() {
  const [isOpen, setIsOpen] = useState(false)

  const handleClick = () => {
    window.api.logTelemetryClick('bug_report_opened')
    setIsOpen(true)
  }

  return (
    <>
      <button
        onClick={handleClick}
        title="Report a Bug"
        style={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          width: 36,
          height: 36,
          borderRadius: '50%',
          background: 'black',
          border: '2px solid white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          opacity: 0.6,
          zIndex: 5,
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          transition: 'opacity 0.15s ease',
          padding: 0,
        }}
        onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
        onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.6' }}
      >
        <Bug size={18} color="white" />
      </button>

      <BugReportPopup isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  )
}
