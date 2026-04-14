import { useEffect } from 'react'
import FormField from '../onboarding/FormField'
import NoteText from './NoteText'
import type { FieldConfig } from '@shared/types'

interface UserSetupStep2Props {
  data: Record<string, any>
  devConfig?: Record<string, any>
  onChange: (data: Record<string, any>) => void
}

export default function UserSetupStep2({ data, devConfig, onChange }: UserSetupStep2Props) {
  const jiraProjects = data.jira_tracked_projects || ''
  const confluenceSpaces = data.confluence_tracked_spaces || ''

  useEffect(() => {
    if (devConfig?.integrations && !data._devApplied) {
      const jira = devConfig.integrations.jira || {}
      const conf = devConfig.integrations.confluence || {}
      onChange({
        _devApplied: true,
        jira_tracked_projects: Array.isArray(jira.tracked_projects) ? jira.tracked_projects.join(', ') : '',
        confluence_tracked_spaces: Array.isArray(conf.spaces) ? conf.spaces.join(', ') : '',
      })
    }
  }, [devConfig])

  const jiraField: FieldConfig = {
    envKey: 'jira_tracked_projects',
    label: 'Jira Tracked Project(s)',
    type: 'text',
    required: false,
    placeholder: 'GOC, TPT, RTEVMS',
  }
  const confField: FieldConfig = {
    envKey: 'confluence_tracked_spaces',
    label: 'Confluence Tracked Spaces',
    type: 'text',
    required: false,
    placeholder: 'TNV, SHOPFOUND',
  }

  return (
    <div>
      <FormField
        field={jiraField}
        value={jiraProjects}
        onChange={(v) => onChange({ ...data, jira_tracked_projects: v })}
      />
      <NoteText text="Please add comma separated values for your tracked Jira projects, e.g. GOC, TPT etc." />

      <FormField
        field={confField}
        value={confluenceSpaces}
        onChange={(v) => onChange({ ...data, confluence_tracked_spaces: v })}
      />
      <NoteText text="Please add comma separated values for your tracked Confluence Spaces, e.g. TNV, SHOPFOUND etc." />
    </div>
  )
}
