import { SettingsField, SettingsSelect, SettingsToggle, SettingsSection } from './SettingsField'

const FUNCTION_OPTIONS = [
  { value: '', label: 'Select...' },
  { value: 'Engineer', label: 'Engineer' },
  { value: 'Product Manager', label: 'Product Manager' },
  { value: 'Product Designer', label: 'Product Designer' },
  { value: 'Product Analyst', label: 'Product Analyst' },
  { value: 'Commercial', label: 'Commercial' },
]

const CAREER_STEP_OPTIONS = [
  { value: '', label: 'Select...' },
  ...Array.from({ length: 10 }, (_, i) => ({ value: String(i + 1), label: String(i + 1) })),
]

interface UserSettingsFormProps {
  data: Record<string, any>
  onChange: (section: string, value: any) => void
}

export default function UserSettingsForm({ data, onChange }: UserSettingsFormProps) {
  const user = data.user || {}
  const personal = data.personal || {}
  const learning = personal.learning_capture || {}
  const career = personal.career || {}

  const updateUser = (field: string, value: any) => {
    onChange('user', { ...user, [field]: value })
  }

  const updatePersonal = (path: string, field: string, value: any) => {
    const section = personal[path] || {}
    onChange('personal', { ...personal, [path]: { ...section, [field]: value } })
  }

  return (
    <div style={{ paddingTop: 16 }}>
      <SettingsSection title="User Profile">
        <SettingsField label="Name" value={user.name || ''} onChange={(v) => updateUser('name', v)} placeholder="First Last" />
        <SettingsField label="Email" value={user.email || ''} onChange={(v) => updateUser('email', v)} placeholder="email@company.com" />
        <SettingsField label="Position / Title" value={user.position || ''} onChange={(v) => updateUser('position', v)} placeholder="e.g. Senior PM" />
        <SettingsField label="Tribe" value={user.tribe || ''} onChange={(v) => updateUser('tribe', v)} placeholder="e.g. Platform" />
        <SettingsField label="Team" value={user.team || ''} onChange={(v) => updateUser('team', v)} placeholder="e.g. Growth Squad" />
        <SettingsSelect label="Function" value={user.function || ''} onChange={(v) => updateUser('function', v)} options={FUNCTION_OPTIONS} />
        <SettingsSelect label="Career Step" value={String(user.career_step || '')} onChange={(v) => updateUser('career_step', v ? Number(v) : null)} options={CAREER_STEP_OPTIONS} />
      </SettingsSection>

      <SettingsSection title="Personal Development">
        <SettingsToggle label="Learning Capture Enabled" checked={learning.enabled ?? true} onChange={(v) => updatePersonal('learning_capture', 'enabled', v)} />
        <SettingsField label="Slack Channels" value={Array.isArray(learning.slack_channels) ? learning.slack_channels.join(', ') : ''} onChange={(v) => updatePersonal('learning_capture', 'slack_channels', v.split(',').map((s: string) => s.trim()).filter(Boolean))} placeholder="#channel1, #channel2" />
        <SettingsField label="Current Level" value={career.current_level || ''} onChange={(v) => updatePersonal('career', 'current_level', v)} placeholder="e.g. Senior Director" />
        <SettingsField label="Target Level" value={career.target_level || ''} onChange={(v) => updatePersonal('career', 'target_level', v)} placeholder="e.g. Vice President" />
        <SettingsField label="Review Cycle" value={career.review_cycle || ''} onChange={(v) => updatePersonal('career', 'review_cycle', v)} placeholder="e.g. H1/H2" />
      </SettingsSection>
    </div>
  )
}
