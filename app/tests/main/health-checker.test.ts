import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import { checkConnection } from '../../src/main/connections/health-checker'

let tmpDir: string

beforeEach(() => {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pmos-health-test-'))
})

afterEach(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true })
  vi.restoreAllMocks()
})

describe('checkConnection', () => {
  it('returns unknown for unconfigured connection', async () => {
    const result = await checkConnection('jira', { JIRA_URL: '', JIRA_USERNAME: '', JIRA_API_TOKEN: '' }, tmpDir)
    expect(result.status).toBe('unknown')
  })

  it('returns unhealthy when validator returns missing fields', async () => {
    const result = await checkConnection('jira', { JIRA_URL: 'https://test.atlassian.net', JIRA_USERNAME: '', JIRA_API_TOKEN: '' }, tmpDir)
    // Has JIRA_URL (required) so it will try to validate
    expect(result.status).toBe('unhealthy')
    expect(result.message).toContain('Missing required fields')
  })

  it('returns unknown for unknown connection id', async () => {
    const result = await checkConnection('nonexistent', {}, tmpDir)
    expect(result.status).toBe('unknown')
  })

  describe('google file-check', () => {
    it('returns healthy when both files exist and token is valid JSON', async () => {
      const credPath = path.join(tmpDir, 'credentials.json')
      const tokenPath = path.join(tmpDir, 'token.json')
      fs.writeFileSync(credPath, '{"type": "service_account"}')
      fs.writeFileSync(tokenPath, '{"access_token": "test"}')

      const result = await checkConnection('google', {
        GOOGLE_CREDENTIALS_PATH: credPath,
        GOOGLE_TOKEN_PATH: tokenPath,
      }, tmpDir)
      expect(result.status).toBe('healthy')
    })

    it('returns unhealthy when credentials file is missing', async () => {
      const tokenPath = path.join(tmpDir, 'token.json')
      fs.writeFileSync(tokenPath, '{"access_token": "test"}')

      const result = await checkConnection('google', {
        GOOGLE_CREDENTIALS_PATH: path.join(tmpDir, 'missing.json'),
        GOOGLE_TOKEN_PATH: tokenPath,
      }, tmpDir)
      expect(result.status).toBe('unhealthy')
      expect(result.message).toContain('not found')
    })

    it('returns unhealthy when token is invalid JSON', async () => {
      const credPath = path.join(tmpDir, 'credentials.json')
      const tokenPath = path.join(tmpDir, 'token.json')
      fs.writeFileSync(credPath, '{"type": "service_account"}')
      fs.writeFileSync(tokenPath, 'not json')

      const result = await checkConnection('google', {
        GOOGLE_CREDENTIALS_PATH: credPath,
        GOOGLE_TOKEN_PATH: tokenPath,
      }, tmpDir)
      expect(result.status).toBe('unhealthy')
    })
  })
})
