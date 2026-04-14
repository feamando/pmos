import { useEffect } from 'react'
import FormField from '../onboarding/FormField'
import NoteText from './NoteText'
import type { FieldConfig } from '@shared/types'

interface UserSetupStep5Props {
  data: Record<string, any>
  devConfig?: Record<string, any>
  onChange: (data: Record<string, any>) => void
}

const DEFAULTS = {
  target_entity_count: '500',
  hot_topics_limit: '10',
  retention_days: '30',
  workers: '5',
  prep_hours: '12',
  default_depth: 'standard',
  prep_workers: '3',
}

export default function UserSetupStep5({ data, devConfig, onChange }: UserSetupStep5Props) {
  // Initialize defaults on first render
  useEffect(() => {
    if (!data._initialized) {
      onChange({ _initialized: true, ...DEFAULTS, ...data })
    }
  }, [])

  useEffect(() => {
    if (devConfig && !data._devApplied) {
      const brain = devConfig.brain || {}
      const context = devConfig.context || {}
      const meeting = devConfig.meeting_prep || {}
      onChange({
        ...data,
        _devApplied: true,
        target_entity_count: String(brain.target_entity_count || DEFAULTS.target_entity_count),
        hot_topics_limit: String(brain.hot_topics_limit || DEFAULTS.hot_topics_limit),
        retention_days: String(context.retention_days || DEFAULTS.retention_days),
        workers: String(brain.workers || DEFAULTS.workers),
        prep_hours: String(meeting.prep_hours || DEFAULTS.prep_hours),
        default_depth: meeting.default_depth || DEFAULTS.default_depth,
        prep_workers: String(meeting.workers || DEFAULTS.prep_workers),
      })
    }
  }, [devConfig])

  const update = (field: string, value: string) => {
    onChange({ ...data, [field]: value })
  }

  const entityCountField: FieldConfig = { envKey: 'target_entity_count', label: 'Target Entity Count', type: 'text', required: false, placeholder: '500' }
  const hotTopicsField: FieldConfig = { envKey: 'hot_topics_limit', label: 'Hot Topic Limits', type: 'text', required: false, placeholder: '10' }
  const retentionField: FieldConfig = { envKey: 'retention_days', label: 'Retention Days', type: 'text', required: false, placeholder: '30' }
  const workersField: FieldConfig = { envKey: 'workers', label: 'Workers', type: 'text', required: false, placeholder: '5' }
  const prepHoursField: FieldConfig = { envKey: 'prep_hours', label: 'Meeting Prep Hours', type: 'text', required: false, placeholder: '12' }
  const prepDepthField: FieldConfig = { envKey: 'default_depth', label: 'Meeting Prep Depth', type: 'text', required: false, placeholder: 'standard' }
  const prepWorkersField: FieldConfig = { envKey: 'prep_workers', label: 'Meeting Prep Workers', type: 'text', required: false, placeholder: '3' }

  return (
    <div>
      <p style={{
        fontSize: 16,
        fontWeight: 700,
        fontFamily: "'Krub', sans-serif",
        marginBottom: 20,
        marginTop: 0,
      }}>
        Enrich PM-OS Brain with your Context
      </p>

      <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, fontFamily: "'Inter', sans-serif" }}>
        Depth Settings
      </h4>
      <FormField field={entityCountField} value={data.target_entity_count || ''} onChange={(v) => update('target_entity_count', v)} />
      <NoteText text="500 minimum recommended" />
      <FormField field={hotTopicsField} value={data.hot_topics_limit || ''} onChange={(v) => update('hot_topics_limit', v)} />
      <FormField field={retentionField} value={data.retention_days || ''} onChange={(v) => update('retention_days', v)} />
      <FormField field={workersField} value={data.workers || ''} onChange={(v) => update('workers', v)} />

      <h4 style={{ fontSize: 14, fontWeight: 600, marginTop: 24, marginBottom: 12, fontFamily: "'Inter', sans-serif" }}>
        Meeting Prep
      </h4>
      <FormField field={prepHoursField} value={data.prep_hours || ''} onChange={(v) => update('prep_hours', v)} />
      <FormField field={prepDepthField} value={data.default_depth || ''} onChange={(v) => update('default_depth', v)} />
      <NoteText text="quick is possible for optimization" />
      <FormField field={prepWorkersField} value={data.prep_workers || ''} onChange={(v) => update('prep_workers', v)} />
    </div>
  )
}
