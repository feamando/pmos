import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { SettingsField, SettingsToggle, SettingsSection } from './SettingsField'

interface IntegrationSettingsFormProps {
  data: Record<string, any>
  onChange: (section: string, value: any) => void
}

interface IntegrationDef {
  id: string
  label: string
  fields: Array<{ key: string; label: string; type?: 'text' | 'csv'; placeholder?: string; note?: string }>
}

const INTEGRATIONS: IntegrationDef[] = [
  {
    id: 'jira', label: 'Jira',
    fields: [
      { key: 'url', label: 'URL', placeholder: 'https://company.atlassian.net' },
      { key: 'username', label: 'Username', placeholder: 'your.email@company.com' },
      { key: 'tracked_projects', label: 'Tracked Projects', type: 'csv', placeholder: 'GOC, TPT, RTEVMS' },
      { key: 'default_project', label: 'Default Project', placeholder: 'PROJ1' },
    ],
  },
  {
    id: 'confluence', label: 'Confluence',
    fields: [
      { key: 'url', label: 'URL', placeholder: 'https://company.atlassian.net/wiki' },
      { key: 'spaces', label: 'Spaces', type: 'csv', placeholder: 'TNV, PMOS' },
    ],
  },
  {
    id: 'github', label: 'GitHub',
    fields: [
      { key: 'org', label: 'Organization', placeholder: 'my-org' },
      { key: 'tracked_repos', label: 'Tracked Repos', type: 'csv', placeholder: 'my-org/web, my-org/api' },
    ],
  },
  {
    id: 'slack', label: 'Slack',
    fields: [
      { key: 'channel', label: 'Default Channel', placeholder: 'C0XXXXXXXXX' },
      { key: 'context_output_channel', label: 'Context Output Channel', placeholder: 'C0XXXXXXXXX' },
      { key: 'mention_bot_name', label: 'Bot Name', placeholder: 'your-bot-name' },
    ],
  },
  {
    id: 'google', label: 'Google',
    fields: [],
  },
  {
    id: 'statsig', label: 'Statsig',
    fields: [],
  },
  {
    id: 'sprint_tracker', label: 'Sprint Tracker',
    fields: [
      { key: 'spreadsheet_id', label: 'Spreadsheet ID', placeholder: 'Google Sheets ID' },
      { key: 'calendar_tab', label: 'Calendar Tab', placeholder: 'Sprint Calendar' },
      { key: 'default_tribe_filter', label: 'Tribe Filter', placeholder: 'e.g. Platform' },
    ],
  },
]

export default function IntegrationSettingsForm({ data, onChange }: IntegrationSettingsFormProps) {
  const integrations = data.integrations || {}
  const [expanded, setExpanded] = useState<string>('jira')

  const updateIntegration = (id: string, field: string, value: any) => {
    const current = integrations[id] || {}
    onChange('integrations', { ...integrations, [id]: { ...current, [field]: value } })
  }

  return (
    <div style={{ paddingTop: 16 }}>
      {/* Claude Connectors section */}
      <div style={{
        marginBottom: 16, padding: 14, background: '#0a2a1a', border: '1px solid #bbf7d0',
        borderRadius: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <span style={{ fontWeight: 600, fontSize: 13, fontFamily: "'Inter', sans-serif", color: '#166534' }}>
              CLAUDE CONNECTORS (Primary)
            </span>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#166534', fontFamily: "'Inter', sans-serif" }}>
              MCP servers are configured in Claude Settings
            </p>
          </div>
          <button
            onClick={() => window.open('https://claude.ai/settings', '_blank')}
            style={{
              padding: '6px 12px', fontSize: 12, fontWeight: 600, border: 'none',
              borderRadius: 4, background: 'black', color: 'white', cursor: 'pointer',
              fontFamily: "'Inter', sans-serif",
            }}
          >
            Open Claude Settings
          </button>
        </div>
      </div>

      {/* API Connections section */}
      <div style={{ marginBottom: 8 }}>
        <span style={{
          fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
          color: 'var(--text-muted)', fontFamily: "'Inter', sans-serif",
        }}>
          API Connections (Optional)
        </span>
      </div>

      {INTEGRATIONS.map((integ) => {
        const config = integrations[integ.id] || {}
        const isExpanded = expanded === integ.id

        return (
          <div key={integ.id} style={{ marginBottom: 4, border: '1px solid var(--border)', borderRadius: 6 }}>
            <button
              onClick={() => setExpanded(isExpanded ? '' : integ.id)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontFamily: "'Inter', sans-serif",
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <span style={{ fontWeight: 600, fontSize: 13 }}>{integ.label}</span>
              </div>
              <span style={{ fontSize: 11, color: config.enabled ? 'var(--status-green)' : 'var(--text-muted)' }}>
                {config.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </button>

            {isExpanded && (
              <div style={{ padding: '0 14px 14px' }}>
                <SettingsToggle
                  label="Enabled"
                  checked={config.enabled ?? false}
                  onChange={(v) => updateIntegration(integ.id, 'enabled', v)}
                />
                {integ.fields.map((field) => (
                  <SettingsField
                    key={field.key}
                    label={field.label}
                    value={
                      field.type === 'csv' && Array.isArray(config[field.key])
                        ? config[field.key].join(', ')
                        : config[field.key] ?? ''
                    }
                    onChange={(v) => {
                      if (field.type === 'csv') {
                        updateIntegration(integ.id, field.key, v.split(',').map((s: string) => s.trim()).filter(Boolean))
                      } else {
                        updateIntegration(integ.id, field.key, v)
                      }
                    }}
                    placeholder={field.placeholder}
                    note={field.note}
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
