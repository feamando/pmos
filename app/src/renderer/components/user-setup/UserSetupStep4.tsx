import { useEffect } from 'react'
import GDriveLinksField from './GDriveLinksField'

interface UserSetupStep4Props {
  data: Record<string, any>
  devConfig?: Record<string, any>
  onChange: (data: Record<string, any>) => void
}

export default function UserSetupStep4({ data, devConfig, onChange }: UserSetupStep4Props) {
  const urls: string[] = data.seed_documents || []

  useEffect(() => {
    if (devConfig?.brain?.seed_documents && !data._devApplied) {
      onChange({
        _devApplied: true,
        seed_documents: devConfig.brain.seed_documents,
      })
    }
  }, [devConfig])

  return (
    <div>
      <p style={{
        fontSize: 14,
        color: 'var(--text-secondary)',
        lineHeight: 1.6,
        marginBottom: 20,
        fontFamily: "'Inter', sans-serif",
      }}>
        Add up to 5 Google Drive file links to seed your brain enrichment. These documents will be used as the starting point for building your PM-OS knowledge base.
      </p>
      <GDriveLinksField
        urls={urls}
        onChange={(newUrls) => onChange({ ...data, seed_documents: newUrls })}
      />
    </div>
  )
}
