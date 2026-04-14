import { useEffect } from 'react'
import FormField from '../onboarding/FormField'
import type { FieldConfig } from '@shared/types'

interface UserSetupStep3Props {
  data: Record<string, any>
  devConfig?: Record<string, any>
  onChange: (data: Record<string, any>) => void
}

export default function UserSetupStep3({ data, devConfig, onChange }: UserSetupStep3Props) {
  const github = data.github || {}
  const slack = data.slack || {}

  useEffect(() => {
    if (devConfig?.integrations && !data._devApplied) {
      const gh = devConfig.integrations.github || {}
      const sl = devConfig.integrations.slack || {}
      onChange({
        _devApplied: true,
        github: {
          org: gh.org || 'my-org',
          tracked_repos: Array.isArray(gh.tracked_repos) ? gh.tracked_repos.join(', ') : '',
        },
        slack: {
          channel: sl.channel || '',
          context_output_channel: sl.context_output_channel || '',
        },
      })
      return
    }

    // Pre-populate from .env values if no devConfig
    if (!data._envLoaded) {
      window.api.getEnvValues(['GITHUB_ORG', 'GITHUB_REPO_FILTER']).then((envValues) => {
        if (envValues.GITHUB_ORG || envValues.GITHUB_REPO_FILTER) {
          onChange({
            ...data,
            _envLoaded: true,
            github: {
              org: envValues.GITHUB_ORG || github.org || 'my-org',
              tracked_repos: envValues.GITHUB_REPO_FILTER || github.tracked_repos || '',
            },
            slack: data.slack || {},
          })
        }
      })
    }
  }, [devConfig])

  const updateGithub = (field: string, value: string) => {
    onChange({ ...data, github: { ...github, [field]: value } })
  }

  const updateSlack = (field: string, value: string) => {
    onChange({ ...data, slack: { ...slack, [field]: value } })
  }

  const orgField: FieldConfig = { envKey: 'org', label: 'GitHub Organization', type: 'text', required: false, placeholder: 'my-org' }
  const reposField: FieldConfig = { envKey: 'tracked_repos', label: 'Tracked Repositories', type: 'text', required: false, placeholder: 'my-org/web, my-org/api' }
  const slackChannelField: FieldConfig = { envKey: 'channel', label: 'Personal Bot Channel', type: 'text', required: false, placeholder: 'e.g. C0XXXXXXXXX' }
  const slackContextField: FieldConfig = { envKey: 'context_output_channel', label: 'Daily Context Publishing Channel', type: 'text', required: false, placeholder: 'e.g. C0XXXXXXXXX' }

  return (
    <div>
      <h3 style={{ fontSize: 15, fontWeight: 700, fontFamily: "'Krub', sans-serif", marginTop: 0, marginBottom: 16 }}>
        GitHub
      </h3>
      <FormField field={orgField} value={github.org || ''} onChange={(v) => updateGithub('org', v)} />
      <FormField field={reposField} value={github.tracked_repos || ''} onChange={(v) => updateGithub('tracked_repos', v)} />

      <h3 style={{ fontSize: 15, fontWeight: 700, fontFamily: "'Krub', sans-serif", marginTop: 24, marginBottom: 16 }}>
        Slack
      </h3>
      <FormField field={slackChannelField} value={slack.channel || ''} onChange={(v) => updateSlack('channel', v)} />
      <FormField field={slackContextField} value={slack.context_output_channel || ''} onChange={(v) => updateSlack('context_output_channel', v)} />
    </div>
  )
}
