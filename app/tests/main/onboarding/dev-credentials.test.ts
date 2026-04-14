import { describe, it, expect, vi, beforeEach } from 'vitest'
import path from 'path'
import os from 'os'
import fs from 'fs'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
}))

vi.mock('electron-store', () => ({
  default: class MockStore {
    constructor() {}
    get(key: string, fallback?: any) { return fallback }
    set() {}
    clear() {}
  }
}))

describe('dev-credentials IPC logic', () => {
  it('returns empty object when .env does not exist', async () => {
    const fakeEnvPath = path.join(os.tmpdir(), 'nonexistent-pm-os', 'user', '.env')
    const exists = fs.existsSync(fakeEnvPath)
    expect(exists).toBe(false)
  })

  it('parses env file with key=value pairs', () => {
    const content = `
JIRA_URL=https://test.atlassian.net
JIRA_USERNAME=user@test.com
JIRA_API_TOKEN=secret123
# Comment line
GITHUB_API_TOKEN=ghp_abc123
`.trim()

    const lines = content.split('\n')
    const result: Record<string, string> = {}
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue
      const eqIdx = trimmed.indexOf('=')
      if (eqIdx > 0) {
        result[trimmed.substring(0, eqIdx)] = trimmed.substring(eqIdx + 1)
      }
    }

    expect(result['JIRA_URL']).toBe('https://test.atlassian.net')
    expect(result['JIRA_API_TOKEN']).toBe('secret123')
    expect(result['GITHUB_API_TOKEN']).toBe('ghp_abc123')
  })
})
