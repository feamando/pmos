import type { ConnectionConfig } from './types'

export const CONNECTION_CONFIGS: ConnectionConfig[] = [
  {
    id: 'jira',
    name: 'Jira',
    icon: 'jira.svg',
    brandColor: '#0052CC',
    fields: [
      { envKey: 'JIRA_URL', label: 'Jira URL', type: 'text', required: true, placeholder: 'https://your-company.atlassian.net' },
      { envKey: 'JIRA_USERNAME', label: 'Username (email)', type: 'text', required: true, placeholder: 'you@company.com' },
      { envKey: 'JIRA_API_TOKEN', label: 'API Token', type: 'password', required: true, placeholder: 'Your Jira API token' },
    ],
    helpText: 'Create an API token at id.atlassian.com/manage-profile/security/api-tokens. Use the email address associated with your Atlassian account.',
    testEndpoint: {
      method: 'GET',
      urlTemplate: '${JIRA_URL}/rest/api/2/myself',
      headers: {},
      authType: 'basic',
    },
  },
  {
    id: 'confluence',
    name: 'Confluence',
    icon: 'confluence.svg',
    brandColor: '#1868DB',
    linkedTo: 'jira',
    fields: [
      { envKey: 'JIRA_URL', label: 'Atlassian URL', type: 'text', required: true, placeholder: 'https://your-company.atlassian.net' },
      { envKey: 'JIRA_USERNAME', label: 'Username (email)', type: 'text', required: true, placeholder: 'you@company.com' },
      { envKey: 'JIRA_API_TOKEN', label: 'API Token', type: 'password', required: true, placeholder: 'Your Jira API token' },
    ],
    helpText: 'Confluence uses the same Atlassian credentials as Jira. Click "Copy from Jira" to auto-fill if you already have Jira configured.',
    testEndpoint: {
      method: 'GET',
      urlTemplate: '${JIRA_URL}/wiki/rest/api/space?limit=1',
      headers: {},
      authType: 'basic',
    },
  },
  {
    id: 'google',
    name: 'Google',
    icon: 'google.svg',
    brandColor: '#4285F4',
    fields: [
      {
        envKey: 'GOOGLE_CREDENTIALS_PATH',
        label: 'Credentials Path',
        type: 'path',
        required: true,
        placeholder: '.secrets/credentials.json',
        autoPopulated: true,
        confirmBeforeEdit: 'You have a distributed Google access token. Are you sure you want to edit?',
      },
      {
        envKey: 'GOOGLE_TOKEN_PATH',
        label: 'Token Path',
        type: 'path',
        required: true,
        placeholder: '.secrets/token.json',
        autoPopulated: true,
        confirmBeforeEdit: 'You have a distributed Google access token. Are you sure you want to edit?',
      },
    ],
    helpText: 'Google OAuth credentials are typically set up during PM-OS installation. If installed via pip, these paths are pre-configured.',
    testEndpoint: {
      method: 'GET',
      urlTemplate: '',
      headers: {},
      authType: 'file-check',
    },
  },
  {
    id: 'slack',
    name: 'Slack',
    icon: 'slack.svg',
    brandColor: '#4A154B',
    fields: [
      { envKey: 'SLACK_BOT_TOKEN', label: 'Bot Token', type: 'password', required: true, placeholder: 'xoxb-...' },
      { envKey: 'USER_OATH_TOKEN', label: 'User OAuth Token', type: 'password', required: true, placeholder: 'xoxp-...' },
      { envKey: 'SLACK_USER_ID', label: 'User ID', type: 'text', required: false, placeholder: 'Your Slack user ID' },
      { envKey: 'SLACK_APP_ID', label: 'App ID', type: 'text', required: false, placeholder: 'Your Slack app ID' },
    ],
    helpText: 'Find your bot and user OAuth tokens in your Slack app settings at api.slack.com/apps. User ID is in your Slack profile.',
    testEndpoint: {
      method: 'POST',
      urlTemplate: 'https://slack.com/api/auth.test',
      headers: {},
      authType: 'bearer',
    },
  },
  {
    id: 'github',
    name: 'GitHub',
    icon: 'github.svg',
    brandColor: '#24292e',
    fields: [
      { envKey: 'GITHUB_ORG', label: 'Organization', type: 'text', required: true, placeholder: 'my-org' },
      { envKey: 'GITHUB_REPO_FILTER', label: 'Repo Filter', type: 'text', required: false, placeholder: 'Comma-separated repo names (optional)' },
      { envKey: 'GITHUB_API_TOKEN', label: 'Personal Access Token', type: 'password', required: true, placeholder: 'ghp_...' },
    ],
    helpText: 'Create a personal access token at github.com/settings/tokens. Select repo scope for repository access.',
    testEndpoint: {
      method: 'GET',
      urlTemplate: 'https://api.github.com/user',
      headers: {},
      authType: 'bearer',
    },
  },
  {
    id: 'figma',
    name: 'Figma',
    icon: 'figma.svg',
    brandColor: '#F24E1E',
    fields: [
      { envKey: 'FIGMA_ACCESS_TOKEN', label: 'Access Token', type: 'password', required: true, placeholder: 'figd_...' },
    ],
    helpText: 'Create a personal access token at figma.com/developers/api#access-tokens.',
    testEndpoint: {
      method: 'GET',
      urlTemplate: 'https://api.figma.com/v1/me',
      headers: {},
      authType: 'bearer',
    },
  },
]

export function getConnectionConfig(id: string): ConnectionConfig | undefined {
  return CONNECTION_CONFIGS.find((c) => c.id === id)
}

export function getAllEnvKeys(): string[] {
  const keys = new Set<string>()
  for (const config of CONNECTION_CONFIGS) {
    for (const field of config.fields) {
      keys.add(field.envKey)
    }
  }
  return Array.from(keys)
}
