import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

vi.mock('child_process', () => ({
  execFile: vi.fn((cmd: any, args: any, opts: any, cb: any) => {
    const callback = typeof opts === 'function' ? opts : cb
    if (typeof cmd === 'string' && cmd.includes('python3') && typeof args?.[1] === 'string' && args[1].includes('import')) {
      callback(null, '', '')
    } else if (cmd === 'python3') {
      callback(null, 'Python 3.12.7', '')
    } else {
      callback(null, '', '')
    }
    return {} as any
  }),
}))
vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logError: vi.fn(),
  logOk: vi.fn(),
}))

import { runVerification } from '../../../src/main/installer/verifier'

describe('verifier', () => {
  let testDir: string

  beforeEach(() => {
    vi.clearAllMocks()
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'verify-test-'))
  })

  afterEach(() => {
    fs.rmSync(testDir, { recursive: true, force: true })
  })

  function createFullInstall() {
    // Structure
    fs.writeFileSync(path.join(testDir, '.pm-os-root'), 'marker')
    fs.mkdirSync(path.join(testDir, 'common', 'tools', 'brain'), { recursive: true })
    fs.mkdirSync(path.join(testDir, 'common', 'tools', 'session'), { recursive: true })
    fs.mkdirSync(path.join(testDir, 'common', '.claude', 'commands'), { recursive: true })
    fs.mkdirSync(path.join(testDir, 'common', 'pipelines'), { recursive: true })
    fs.mkdirSync(path.join(testDir, 'common', 'tools', 'mcp', 'brain_mcp'), { recursive: true })
    fs.mkdirSync(path.join(testDir, 'user', 'brain'), { recursive: true })
    fs.mkdirSync(path.join(testDir, 'user', '.secrets'), { recursive: true })
    fs.chmodSync(path.join(testDir, 'user', '.secrets'), 0o700)
    fs.mkdirSync(path.join(testDir, '.venv', 'bin'), { recursive: true })

    // Config files
    fs.writeFileSync(path.join(testDir, 'user', '.env'), 'JIRA_URL=\nSLACK_BOT_TOKEN=\nGITHUB_API_TOKEN=\nGOOGLE_CREDENTIALS_PATH=\n')
    fs.writeFileSync(path.join(testDir, 'user', 'config.yaml'), 'user:\n  name: test\n')
    fs.writeFileSync(path.join(testDir, 'CLAUDE.md'), '# PM-OS\nReserved: logout\n')
    fs.writeFileSync(path.join(testDir, '.mcp.json'), '{"mcpServers":{"brain":{"command":"python3"}}}')
    fs.writeFileSync(path.join(testDir, 'common', 'AGENT.md'), '# Agent\n')

    // Tools
    fs.writeFileSync(path.join(testDir, 'common', 'tools', 'brain', 'brain_index.py'), '')
    fs.writeFileSync(path.join(testDir, 'common', 'tools', 'session', 'session_manager.py'), '')
    fs.writeFileSync(path.join(testDir, 'common', 'tools', 'mcp', 'brain_mcp', 'server.py'), '')
    fs.writeFileSync(path.join(testDir, 'common', '.claude', 'commands', 'boot.md'), '')
    fs.writeFileSync(path.join(testDir, 'common', 'pipelines', 'boot.yaml'), '')

    // Python
    fs.writeFileSync(path.join(testDir, '.venv', 'bin', 'python3'), '')

    // Google creds
    fs.writeFileSync(path.join(testDir, 'user', '.secrets', 'credentials.json'), '{"installed":{}}')
  }

  it('passes all checks on a complete installation', async () => {
    createFullInstall()
    const result = await runVerification(testDir)

    expect(result.success).toBe(true)
    expect(result.checks.length).toBeGreaterThan(10)
    expect(result.checks.every((c) => c.passed)).toBe(true)
  })

  it('fails on missing structure', async () => {
    // Empty directory — nothing exists
    const result = await runVerification(testDir)

    expect(result.success).toBe(false)
    const failed = result.checks.filter((c) => !c.passed)
    expect(failed.length).toBeGreaterThan(0)
    expect(failed.some((c) => c.name.includes('.pm-os-root'))).toBe(true)
  })

  it('detects wrong .secrets permissions', async () => {
    createFullInstall()
    fs.chmodSync(path.join(testDir, 'user', '.secrets'), 0o755)

    const result = await runVerification(testDir)
    const permCheck = result.checks.find((c) => c.name.includes('permissions'))
    expect(permCheck?.passed).toBe(false)
  })

  it('checks return duration', async () => {
    createFullInstall()
    const result = await runVerification(testDir)

    expect(result.duration).toBeGreaterThanOrEqual(0)
    for (const check of result.checks) {
      expect(check).toHaveProperty('duration')
      expect(check).toHaveProperty('category')
    }
  })
})
