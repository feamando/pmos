import { useState, useImperativeHandle, forwardRef } from 'react'
import FormField from './FormField'
import type { ConnectionConfig } from '@shared/types'

interface StepFormProps {
  configs: ConnectionConfig[]
  initialValues: Record<string, string>
  validationErrors: string[]
}

export interface StepFormRef {
  getValues: () => Record<string, string>
  setValues: (values: Record<string, string>) => void
  hasValues: () => boolean
}

const StepForm = forwardRef<StepFormRef, StepFormProps>(({ configs, initialValues, validationErrors }, ref) => {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {}
    for (const config of configs) {
      for (const field of config.fields) {
        init[field.envKey] = initialValues[field.envKey] || ''
      }
    }
    return init
  })

  useImperativeHandle(ref, () => ({
    getValues: () => values,
    setValues: (newValues) => setValues((prev) => ({ ...prev, ...newValues })),
    hasValues: () => Object.values(values).some((v) => v.trim() !== ''),
  }))

  const handleChange = (envKey: string, value: string) => {
    setValues((prev) => ({ ...prev, [envKey]: value }))
  }

  return (
    <div>
      {configs.map((config) => (
        <div key={config.id}>
          {configs.length > 1 && (
            <h3 style={{
              fontSize: 16,
              fontWeight: 600,
              color: 'var(--text-primary)',
              marginBottom: 12,
              marginTop: configs.indexOf(config) > 0 ? 24 : 0,
              fontFamily: "'Inter', sans-serif",
            }}>
              {config.name}
            </h3>
          )}
          {config.fields.map((field) => (
            <FormField
              key={field.envKey}
              field={field}
              value={values[field.envKey]}
              onChange={(v) => handleChange(field.envKey, v)}
              error={validationErrors.includes(field.envKey)}
            />
          ))}
          {/* Help text */}
          <div style={{
            fontSize: 13,
            color: 'var(--text-muted)',
            lineHeight: 1.5,
            marginTop: 8,
            marginBottom: 16,
          }}>
            {config.helpText}
          </div>
        </div>
      ))}
    </div>
  )
})

StepForm.displayName = 'StepForm'
export default StepForm
