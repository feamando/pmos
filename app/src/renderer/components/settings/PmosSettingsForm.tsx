import { useState, useEffect } from 'react'
import { SettingsField, SettingsToggle, SettingsSelect, SettingsSection } from './SettingsField'

interface PmosSettingsFormProps {
  data: Record<string, any>
  onChange: (section: string, value: any) => void
}

const DEPTH_OPTIONS = [
  { value: 'quick', label: 'Quick' },
  { value: 'standard', label: 'Standard' },
]

const MODEL_OPTIONS = [
  { value: 'bedrock', label: 'Bedrock' },
  { value: 'auto', label: 'Auto' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'claude', label: 'Claude' },
  { value: 'template', label: 'Template' },
]

export default function PmosSettingsForm({ data, onChange }: PmosSettingsFormProps) {
  const [pmosPath, setPmosPath] = useState('')
  const [pmosPathStatus, setPmosPathStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [pmosPathError, setPmosPathError] = useState('')

  useEffect(() => {
    window.api.getPmosPath().then((p) => { if (p) setPmosPath(p) })
  }, [])

  const handleSavePmosPath = async () => {
    if (!pmosPath.trim()) return
    setPmosPathStatus('saving')
    const result = await window.api.setPmosPath(pmosPath.trim())
    if (result.success) {
      setPmosPathStatus('saved')
      setPmosPathError('')
      setTimeout(() => setPmosPathStatus('idle'), 2000)
    } else {
      setPmosPathStatus('error')
      setPmosPathError(result.error || 'Invalid path')
    }
  }

  const pmos = data.pm_os || {}
  const paths = data.paths || {}
  const brain = data.brain || {}
  const context = data.context || {}
  const sessions = data.sessions || {}
  const meetingPrep = data.meeting_prep || {}
  const taskInference = meetingPrep.task_inference || {}
  const sectionDefaults = meetingPrep.section_defaults || {}
  const typeOverrides = meetingPrep.type_overrides || {}
  const designContext = data.design_context || {}
  const specMachine = data.spec_machine || {}

  const updatePmos = (field: string, value: any) => {
    onChange('pm_os', { ...pmos, [field]: value })
  }

  const updatePaths = (field: string, value: any) => {
    onChange('paths', { ...paths, [field]: value })
  }

  const updateBrain = (field: string, value: any) => {
    onChange('brain', { ...brain, [field]: value })
  }

  const updateContext = (field: string, value: any) => {
    onChange('context', { ...context, [field]: value })
  }

  const updateContextInclude = (field: string, value: boolean) => {
    const include = context.include || {}
    onChange('context', { ...context, include: { ...include, [field]: value } })
  }

  const updateSessions = (field: string, value: any) => {
    onChange('sessions', { ...sessions, [field]: value })
  }

  const updateMeetingPrep = (field: string, value: any) => {
    onChange('meeting_prep', { ...meetingPrep, [field]: value })
  }

  const updateTaskInference = (field: string, value: any) => {
    onChange('meeting_prep', { ...meetingPrep, task_inference: { ...taskInference, [field]: value } })
  }

  const updateSectionDefault = (section: string, field: string, value: any) => {
    const current = sectionDefaults[section] || {}
    onChange('meeting_prep', {
      ...meetingPrep,
      section_defaults: { ...sectionDefaults, [section]: { ...current, [field]: value } },
    })
  }

  const updateTypeOverride = (type: string, value: string) => {
    onChange('meeting_prep', {
      ...meetingPrep,
      type_overrides: { ...typeOverrides, [type]: { ...typeOverrides[type], max_words: value ? Number(value) : null } },
    })
  }

  const updateDesignContext = (field: string, value: any) => {
    onChange('design_context', { ...designContext, [field]: value })
  }

  const updateSpecMachine = (field: string, value: any) => {
    onChange('spec_machine', { ...specMachine, [field]: value })
  }

  return (
    <div style={{ paddingTop: 16 }}>
      {/* PM-OS Installation Path */}
      <SettingsSection title="PM-OS Installation">
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4, fontFamily: "'Inter', sans-serif" }}>
            PM-OS Path
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={pmosPath}
              onChange={(e) => { setPmosPath(e.target.value); setPmosPathStatus('idle') }}
              placeholder="/Users/you/pm-os"
              style={{
                flex: 1,
                padding: '8px 10px',
                background: '#0a1929',
                color: '#ffffff',
                border: `1px solid ${pmosPathStatus === 'error' ? '#dc2626' : pmosPathStatus === 'saved' ? '#16a34a' : '#ff008844'}`,
                borderRadius: 4,
                fontSize: 13,
                fontFamily: "'Inter', sans-serif",
                boxSizing: 'border-box' as const,
                outline: 'none',
              }}
            />
            <button
              onClick={handleSavePmosPath}
              disabled={pmosPathStatus === 'saving'}
              style={{
                padding: '8px 14px',
                background: pmosPathStatus === 'saved' ? '#16a34a' : '#111',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                fontSize: 12,
                fontWeight: 600,
                cursor: pmosPathStatus === 'saving' ? 'wait' : 'pointer',
                fontFamily: "'Inter', sans-serif",
                whiteSpace: 'nowrap',
              }}
            >
              {pmosPathStatus === 'saving' ? 'Saving...' : pmosPathStatus === 'saved' ? 'Saved' : 'Set Path'}
            </button>
          </div>
          {pmosPathStatus === 'error' && (
            <p style={{ fontSize: 11, color: '#dc2626', marginTop: 4, marginBottom: 0 }}>{pmosPathError}</p>
          )}
          <p style={{ fontSize: 11, fontStyle: 'italic', color: '#778899', marginTop: 4, marginBottom: 0 }}>
            Root directory of your PM-OS installation (contains common/ and user/ folders)
          </p>
        </div>
      </SettingsSection>

      {/* Core Toggles */}
      <SettingsSection title="Core Features">
        <SettingsToggle label="FPF (First Principles Framework)" checked={pmos.fpf_enabled ?? true} onChange={(v) => updatePmos('fpf_enabled', v)} />
        <SettingsToggle label="Confucius (Session Notes)" checked={pmos.confucius_enabled ?? true} onChange={(v) => updatePmos('confucius_enabled', v)} />
        <SettingsToggle label="Ralph (Workflow Engine)" checked={pmos.ralph_enabled ?? true} onChange={(v) => updatePmos('ralph_enabled', v)} />
        <SettingsToggle label="Auto-update on Boot" checked={pmos.auto_update ?? true} onChange={(v) => updatePmos('auto_update', v)} />
        <SettingsField label="Ralph Slack Channel" value={pmos.ralph_slack_channel || ''} onChange={(v) => updatePmos('ralph_slack_channel', v)} placeholder="C0XXXXXXXXX" />
      </SettingsSection>

      {/* Paths */}
      <SettingsSection title="Paths">
        <SettingsField label="Common Path" value={paths.common || ''} onChange={(v) => updatePaths('common', v)} placeholder="/path/to/pm-os/common" />
        <SettingsField label="User Path" value={paths.user || ''} onChange={(v) => updatePaths('user', v)} placeholder="/path/to/pm-os/user" />
        <SettingsField label="Snapshots Path" value={paths.snapshots || ''} onChange={(v) => updatePaths('snapshots', v)} placeholder="/path/to/pm-os/snapshots" />
      </SettingsSection>

      {/* Brain */}
      <SettingsSection title="Brain">
        <SettingsField
          label="Entity Types"
          value={Array.isArray(brain.entity_types) ? brain.entity_types.join(', ') : ''}
          onChange={(v) => updateBrain('entity_types', v.split(',').map((s: string) => s.trim()).filter(Boolean))}
          placeholder="person, team, project, domain, experiment, feature, brand"
        />
        <SettingsField label="Hot Topics Limit" value={String(brain.hot_topics_limit ?? '')} onChange={(v) => updateBrain('hot_topics_limit', v ? Number(v) : null)} type="number" placeholder="10" />
        <SettingsToggle label="Validate on Load" checked={brain.validate_on_load ?? false} onChange={(v) => updateBrain('validate_on_load', v)} />
        <SettingsField label="Target Entity Count" value={String(brain.target_entity_count ?? '')} onChange={(v) => updateBrain('target_entity_count', v ? Number(v) : null)} type="number" placeholder="500" />
        <SettingsField label="Workers" value={String(brain.workers ?? '')} onChange={(v) => updateBrain('workers', v ? Number(v) : null)} type="number" placeholder="5" />
        <SettingsField
          label="Seed Documents"
          value={Array.isArray(brain.seed_documents) ? brain.seed_documents.join(', ') : ''}
          onChange={(v) => updateBrain('seed_documents', v.split(',').map((s: string) => s.trim()).filter(Boolean))}
          placeholder="Google Drive URLs (comma-separated)"
          note="URLs to documents that seed the brain on initial load"
        />
      </SettingsSection>

      {/* Context */}
      <SettingsSection title="Context">
        <SettingsField label="Retention Days" value={String(context.retention_days ?? '')} onChange={(v) => updateContext('retention_days', v ? Number(v) : null)} type="number" placeholder="30" />
        <SettingsToggle label="Include Jira" checked={context.include?.jira ?? true} onChange={(v) => updateContextInclude('jira', v)} />
        <SettingsToggle label="Include GitHub" checked={context.include?.github ?? true} onChange={(v) => updateContextInclude('github', v)} />
        <SettingsToggle label="Include Slack" checked={context.include?.slack ?? true} onChange={(v) => updateContextInclude('slack', v)} />
        <SettingsToggle label="Include Calendar" checked={context.include?.calendar ?? true} onChange={(v) => updateContextInclude('calendar', v)} />
      </SettingsSection>

      {/* Sessions */}
      <SettingsSection title="Sessions">
        <SettingsField label="Auto-save Interval (min)" value={String(sessions.auto_save_interval ?? '')} onChange={(v) => updateSessions('auto_save_interval', v ? Number(v) : null)} type="number" placeholder="5" />
        <SettingsField label="Max Sessions" value={String(sessions.max_sessions ?? '')} onChange={(v) => updateSessions('max_sessions', v ? Number(v) : null)} type="number" placeholder="50" />
      </SettingsSection>

      {/* Meeting Prep */}
      <SettingsSection title="Meeting Prep">
        <SettingsField label="Prep Hours" value={String(meetingPrep.prep_hours ?? '')} onChange={(v) => updateMeetingPrep('prep_hours', v ? Number(v) : null)} type="number" placeholder="24" />
        <SettingsSelect label="Default Depth" value={meetingPrep.default_depth || 'standard'} onChange={(v) => updateMeetingPrep('default_depth', v)} options={DEPTH_OPTIONS} />
        <SettingsField label="Workers" value={String(meetingPrep.workers ?? '')} onChange={(v) => updateMeetingPrep('workers', v ? Number(v) : null)} type="number" placeholder="3" />
        <SettingsSelect label="Preferred Model" value={meetingPrep.preferred_model || 'bedrock'} onChange={(v) => updateMeetingPrep('preferred_model', v)} options={MODEL_OPTIONS} />
        <SettingsToggle label="Include Competitors" checked={meetingPrep.include_competitors ?? false} onChange={(v) => updateMeetingPrep('include_competitors', v)} />
        <SettingsToggle label="Include Recent Context" checked={meetingPrep.include_recent_context ?? true} onChange={(v) => updateMeetingPrep('include_recent_context', v)} />
      </SettingsSection>

      {/* Task Inference */}
      <SettingsSection title="Task Inference">
        <SettingsToggle label="Enabled" checked={taskInference.enabled ?? true} onChange={(v) => updateTaskInference('enabled', v)} />
        <SettingsField
          label="Sources"
          value={Array.isArray(taskInference.sources) ? taskInference.sources.join(', ') : ''}
          onChange={(v) => updateTaskInference('sources', v.split(',').map((s: string) => s.trim()).filter(Boolean))}
          placeholder="slack, jira, github, brain, daily_context"
        />
        <SettingsField label="Confidence Threshold" value={String(taskInference.confidence_threshold ?? '')} onChange={(v) => updateTaskInference('confidence_threshold', v ? Number(v) : null)} type="number" placeholder="0.7" />
      </SettingsSection>

      {/* Section Defaults */}
      <SettingsSection title="Section Defaults">
        {(['tldr', 'action_items', 'topics', 'questions'] as const).map((section) => {
          const def = sectionDefaults[section] || {}
          return (
            <div key={section} style={{ marginBottom: 16, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 12, fontWeight: 600, textTransform: 'capitalize', fontFamily: "'Inter', sans-serif" }}>
                {section.replace('_', ' ')}
              </span>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 6 }}>
                <SettingsField label="Min" value={String(def.min ?? '')} onChange={(v) => updateSectionDefault(section, 'min', v ? Number(v) : null)} type="number" placeholder="1" />
                <SettingsField label="Max" value={String(def.max ?? '')} onChange={(v) => updateSectionDefault(section, 'max', v ? Number(v) : null)} type="number" placeholder="5" />
                <SettingsField label="Threshold" value={String(def.relevance_threshold ?? '')} onChange={(v) => updateSectionDefault(section, 'relevance_threshold', v ? Number(v) : null)} type="number" placeholder="0.5" />
              </div>
            </div>
          )
        })}
      </SettingsSection>

      {/* Type Overrides */}
      <SettingsSection title="Meeting Type Max Words">
        {['1on1', 'standup', 'large_meeting', 'external', 'interview', 'review', 'planning', 'other'].map((type) => (
          <SettingsField
            key={type}
            label={type.replace('_', ' ')}
            value={String(typeOverrides[type]?.max_words ?? '')}
            onChange={(v) => updateTypeOverride(type, v)}
            type="number"
            placeholder="500"
          />
        ))}
      </SettingsSection>

      {/* Design Context */}
      <SettingsSection title="Design Context">
        <SettingsField label="Default Platform" value={designContext.default_platform || ''} onChange={(v) => updateDesignContext('default_platform', v)} placeholder="web" />
        <SettingsToggle label="Repo Profiles Enabled" checked={designContext.repo_profiles_enabled ?? false} onChange={(v) => updateDesignContext('repo_profiles_enabled', v)} />
      </SettingsSection>

      {/* Spec Machine */}
      <SettingsSection title="Spec Machine">
        <SettingsToggle label="Enabled" checked={specMachine.enabled ?? false} onChange={(v) => updateSpecMachine('enabled', v)} />
        <SettingsField label="Default Repo" value={specMachine.default_repo || ''} onChange={(v) => updateSpecMachine('default_repo', v)} placeholder="my-repo" />
        <SettingsField label="Default Subdir" value={specMachine.default_subdir || ''} onChange={(v) => updateSpecMachine('default_subdir', v)} placeholder="specs/" />
        <SettingsToggle label="Auto-export on Orthogonal" checked={specMachine.auto_export_on_orthogonal ?? false} onChange={(v) => updateSpecMachine('auto_export_on_orthogonal', v)} />
      </SettingsSection>
    </div>
  )
}
