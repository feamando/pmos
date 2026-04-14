import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import yaml from 'js-yaml'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
}))

vi.mock('electron-store', () => ({
  default: class MockStore {
    constructor() {}
    get(_key: string, fallback?: any) { return fallback }
    set() {}
    clear() {}
  },
}))

import { readConfigYaml, writeConfigYaml } from '../../../src/main/config-yaml-manager'

describe('save-user-setup-step config mapping', () => {
  let tmpDir: string

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'save-step-test-'))
    fs.mkdirSync(path.join(tmpDir, 'user'), { recursive: true })
    // Start with a basic config
    fs.writeFileSync(
      path.join(tmpDir, 'user', 'config.yaml'),
      yaml.dump({ version: '3.0.0', user: { name: '', email: '' } })
    )
  })

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true })
  })

  it('saves user profile to user: section', () => {
    writeConfigYaml(tmpDir, {
      user: { name: 'Jane Doe', email: 'jane@test.com', function: 'Product Manager', career_step: 7 },
    })
    const config = readConfigYaml(tmpDir)
    expect(config.user.name).toBe('Jane Doe')
    expect(config.user.email).toBe('jane@test.com')
    expect(config.user.function).toBe('Product Manager')
    expect(config.user.career_step).toBe(7)
  })

  it('saves atlassian settings as arrays', () => {
    writeConfigYaml(tmpDir, {
      integrations: {
        jira: { tracked_projects: ['GOC', 'TPT'] },
        confluence: { spaces: ['TNV'] },
      },
    })
    const config = readConfigYaml(tmpDir)
    expect(config.integrations.jira.tracked_projects).toEqual(['GOC', 'TPT'])
    expect(config.integrations.confluence.spaces).toEqual(['TNV'])
  })

  it('saves github and slack settings', () => {
    writeConfigYaml(tmpDir, {
      integrations: {
        github: { org: 'my-org', tracked_repos: ['web', 'api'] },
        slack: { channel: 'C123', context_output_channel: 'C456' },
      },
    })
    const config = readConfigYaml(tmpDir)
    expect(config.integrations.github.org).toBe('my-org')
    expect(config.integrations.github.tracked_repos).toEqual(['web', 'api'])
    expect(config.integrations.slack.channel).toBe('C123')
  })

  it('saves brain seed documents', () => {
    writeConfigYaml(tmpDir, {
      brain: { seed_documents: ['https://docs.google.com/doc1', 'https://docs.google.com/doc2'] },
    })
    const config = readConfigYaml(tmpDir)
    expect(config.brain.seed_documents).toEqual(['https://docs.google.com/doc1', 'https://docs.google.com/doc2'])
  })

  it('saves brain enrichment settings as numbers', () => {
    writeConfigYaml(tmpDir, {
      brain: { target_entity_count: 500, hot_topics_limit: 10, workers: 5 },
      context: { retention_days: 30 },
      meeting_prep: { prep_hours: 12, default_depth: 'standard', workers: 3 },
    })
    const config = readConfigYaml(tmpDir)
    expect(config.brain.target_entity_count).toBe(500)
    expect(config.context.retention_days).toBe(30)
    expect(config.meeting_prep.workers).toBe(3)
  })

  it('saves team and products structure', () => {
    writeConfigYaml(tmpDir, {
      team: {
        manager: { name: 'Boss', email: 'boss@test.com' },
        reports: [{ name: 'Report1', email: 'r1@test.com', jira_project: 'GOC' }],
      },
      products: {
        organization: { name: 'Mega Alliance' },
        items: [{ id: 'squad-1', name: 'Squad 1', jira_project: 'GOC', board_id: '123' }],
      },
    })
    const config = readConfigYaml(tmpDir)
    expect(config.team.manager.name).toBe('Boss')
    expect(config.team.reports).toHaveLength(1)
    expect(config.products.organization.name).toBe('Mega Alliance')
    expect(config.products.items[0].board_id).toBe('123')
  })

  it('preserves existing config when saving new steps', () => {
    writeConfigYaml(tmpDir, { user: { name: 'First', email: 'first@test.com' } })
    writeConfigYaml(tmpDir, { brain: { hot_topics_limit: 15 } })
    const config = readConfigYaml(tmpDir)
    expect(config.user.name).toBe('First')
    expect(config.brain.hot_topics_limit).toBe(15)
  })
})
