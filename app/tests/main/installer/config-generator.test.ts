import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

vi.mock('../../../src/main/installer/logger', () => ({
  logInfo: vi.fn(),
  logError: vi.fn(),
  logOk: vi.fn(),
}))

import { generateConfigFiles } from '../../../src/main/installer/config-generator'

describe('config-generator', () => {
  let testDir: string
  let pmosPath: string
  let bundlePath: string

  beforeEach(() => {
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'config-gen-test-'))
    pmosPath = path.join(testDir, 'pmos')
    bundlePath = path.join(testDir, 'bundle')

    // Create pmos directory structure
    fs.mkdirSync(path.join(pmosPath, 'user'), { recursive: true })
    fs.mkdirSync(path.join(pmosPath, 'common'), { recursive: true })

    // Create template directory with templates
    const templateDir = path.join(bundlePath, 'data', 'templates')
    fs.mkdirSync(templateDir, { recursive: true })

    fs.writeFileSync(path.join(templateDir, 'env.template'), 'PM_OS_ROOT={{PMOS_PATH}}\nDATE={{DATE}}\n')
    fs.writeFileSync(path.join(templateDir, 'config.yaml.template'), 'user:\n  name: ""\nversion: 0.1\n')
    fs.writeFileSync(path.join(templateDir, 'claude.md.template'), '# PM-OS\nDate: {{DATE}}\nReserved: logout, login\n')
    fs.writeFileSync(path.join(templateDir, 'mcp.json.template'), '{"mcpServers":{"brain":{"cwd":"{{PMOS_PATH}}/common/tools/brain"}}}\n')
    fs.writeFileSync(path.join(templateDir, 'user.md.template'), '# User Profile\n')
    fs.writeFileSync(path.join(templateDir, 'agent.md.template'), '# Agent\n')
  })

  afterEach(() => {
    fs.rmSync(testDir, { recursive: true, force: true })
  })

  it('generates all config files from templates', async () => {
    const result = await generateConfigFiles(pmosPath, bundlePath)

    expect(result.success).toBe(true)
    expect(fs.existsSync(path.join(pmosPath, 'user', '.env'))).toBe(true)
    expect(fs.existsSync(path.join(pmosPath, 'user', 'config.yaml'))).toBe(true)
    expect(fs.existsSync(path.join(pmosPath, 'CLAUDE.md'))).toBe(true)
    expect(fs.existsSync(path.join(pmosPath, '.mcp.json'))).toBe(true)
    expect(fs.existsSync(path.join(pmosPath, 'user', 'USER.md'))).toBe(true)
    expect(fs.existsSync(path.join(pmosPath, 'common', 'AGENT.md'))).toBe(true)
  })

  it('replaces template variables', async () => {
    await generateConfigFiles(pmosPath, bundlePath)

    const envContent = fs.readFileSync(path.join(pmosPath, 'user', '.env'), 'utf-8')
    expect(envContent).toContain(pmosPath)
    expect(envContent).not.toContain('{{PMOS_PATH}}')

    const mcpContent = fs.readFileSync(path.join(pmosPath, '.mcp.json'), 'utf-8')
    expect(mcpContent).toContain(pmosPath)
  })

  it('does not overwrite existing files', async () => {
    // Pre-create .env with custom content
    fs.writeFileSync(path.join(pmosPath, 'user', '.env'), 'CUSTOM=value')

    await generateConfigFiles(pmosPath, bundlePath)

    const envContent = fs.readFileSync(path.join(pmosPath, 'user', '.env'), 'utf-8')
    expect(envContent).toBe('CUSTOM=value')
  })

  it('fails when template directory missing', async () => {
    const emptyBundle = path.join(testDir, 'empty-bundle')
    fs.mkdirSync(emptyBundle, { recursive: true })

    const result = await generateConfigFiles(pmosPath, emptyBundle)
    expect(result.success).toBe(false)
    expect(result.message).toContain('Template directory not found')
  })
})
