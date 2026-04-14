import { useEffect, useRef } from 'react'
import WcrSettingsForm from '../settings/WcrSettingsForm'

interface UserSetupStep6Props {
  data: Record<string, any>
  devConfig?: Record<string, any>
  onChange: (data: Record<string, any>) => void
}

export default function UserSetupStep6({ data, devConfig, onChange }: UserSetupStep6Props) {
  const devApplied = useRef(false)

  // Build WCR-shaped data from step data
  const wcrData: Record<string, any> = {
    products: data.products || { organization: {}, items: [] },
    team: data.team || { manager: {}, reports: [], stakeholders: [] },
    workspace: data.workspace || {},
    master_sheet: data.master_sheet || {},
  }

  useEffect(() => {
    if (devConfig && !devApplied.current) {
      devApplied.current = true
      // Apply dev config — WcrSettingsForm reads products, team, workspace, master_sheet
      const newData: Record<string, any> = { ...data }
      if (devConfig.products) newData.products = devConfig.products
      if (devConfig.team) newData.team = devConfig.team
      if (devConfig.workspace) newData.workspace = devConfig.workspace
      if (devConfig.master_sheet) newData.master_sheet = devConfig.master_sheet
      onChange(newData)
    }
  }, [devConfig])

  const handleSectionChange = (section: string, value: any) => {
    onChange({ ...data, [section]: value })
  }

  return (
    <div>
      <p style={{
        fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16,
        fontFamily: "'Inter', sans-serif", lineHeight: 1.5,
      }}>
        Configure your organization structure, team, and products. You can update these later in Settings.
      </p>
      <WcrSettingsForm data={wcrData} onChange={handleSectionChange} />
    </div>
  )
}
