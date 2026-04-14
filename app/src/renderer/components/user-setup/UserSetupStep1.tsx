import { useEffect } from 'react'
import FormField from '../onboarding/FormField'
import SelectField from './SelectField'
import type { FieldConfig } from '@shared/types'

const FUNCTION_OPTIONS = [
  { value: 'Engineer', label: 'Engineer' },
  { value: 'Product Manager', label: 'Product Manager' },
  { value: 'Product Designer', label: 'Product Designer' },
  { value: 'Product Analyst', label: 'Product Analyst' },
  { value: 'Commercial', label: 'Commercial' },
]

const CAREER_STEP_OPTIONS = Array.from({ length: 10 }, (_, i) => ({
  value: String(i + 1),
  label: String(i + 1),
}))

interface UserSetupStep1Props {
  data: Record<string, any>
  devConfig?: Record<string, any>
  onChange: (data: Record<string, any>) => void
}

export default function UserSetupStep1({ data, devConfig, onChange }: UserSetupStep1Props) {
  const userSection = data.user || {}

  useEffect(() => {
    if (devConfig?.user && !data._devApplied) {
      const u = devConfig.user
      onChange({
        _devApplied: true,
        user: {
          name: u.name || '',
          email: u.email || '',
          function: u.function || '',
          career_step: u.career_step ? String(u.career_step) : '',
          position: u.position || '',
          tribe: u.tribe || '',
        },
      })
    }
  }, [devConfig])

  const update = (field: string, value: string) => {
    onChange({ ...data, user: { ...userSection, [field]: value } })
  }

  const nameField: FieldConfig = { envKey: 'name', label: 'Name', type: 'text', required: true, placeholder: 'First Last' }
  const emailField: FieldConfig = { envKey: 'email', label: 'Email', type: 'text', required: true, placeholder: 'your.email@company.com' }
  const positionField: FieldConfig = { envKey: 'position', label: 'Position / Title', type: 'text', required: false, placeholder: 'e.g. Senior Product Manager' }
  const tribeField: FieldConfig = { envKey: 'tribe', label: 'Tribe', type: 'text', required: false, placeholder: 'e.g. Platform' }

  return (
    <div>
      <FormField field={nameField} value={userSection.name || ''} onChange={(v) => update('name', v)} />
      <FormField field={emailField} value={userSection.email || ''} onChange={(v) => update('email', v)} />
      <SelectField
        label="Function"
        value={userSection.function || ''}
        onChange={(v) => update('function', v)}
        options={FUNCTION_OPTIONS}
        required
        placeholder="Select your function"
      />
      <SelectField
        label="Career Step"
        value={userSection.career_step || ''}
        onChange={(v) => update('career_step', v)}
        options={CAREER_STEP_OPTIONS}
        required
        placeholder="Select career step"
      />
      <FormField field={positionField} value={userSection.position || ''} onChange={(v) => update('position', v)} />
      <FormField field={tribeField} value={userSection.tribe || ''} onChange={(v) => update('tribe', v)} />
    </div>
  )
}
