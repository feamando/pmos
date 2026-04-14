import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdirSync, writeFileSync, rmSync, existsSync, readFileSync } from 'fs'
import path from 'path'
import os from 'os'
import { getInstalledPlugins, getAvailablePlugins, getAllPlugins, installPlugin, disablePlugin, getPluginHealth } from '../../../src/main/plugin-manager'

let tmpDir: string

function makeTmpDir(): string {
  const dir = path.join(os.tmpdir(), `pmos-test-${Date.now()}-${Math.random().toString(36).slice(2)}`)
  mkdirSync(dir, { recursive: true })
  return dir
}

function writeManifest(pmosPath: string, pluginName: string, manifest: Record<string, any>) {
  const dir = path.join(pmosPath, 'v5', 'plugins', pluginName, '.claude-plugin')
  mkdirSync(dir, { recursive: true })
  writeFileSync(path.join(dir, 'plugin.json'), JSON.stringify(manifest))
}

function writeCommand(pmosPath: string, pluginName: string, cmdName: string) {
  const dir = path.join(pmosPath, 'v5', 'plugins', pluginName, 'commands')
  mkdirSync(dir, { recursive: true })
  writeFileSync(path.join(dir, cmdName), `# ${cmdName}`)
}

function writeSkill(pmosPath: string, pluginName: string, skillName: string) {
  const dir = path.join(pmosPath, 'v5', 'plugins', pluginName, 'skills')
  mkdirSync(dir, { recursive: true })
  writeFileSync(path.join(dir, skillName), `# ${skillName}`)
}

beforeEach(() => {
  tmpDir = makeTmpDir()
})

afterEach(() => {
  rmSync(tmpDir, { recursive: true, force: true })
})

describe('plugin-manager', () => {
  describe('getAllPlugins', () => {
    it('returns empty array when plugins dir does not exist', () => {
      expect(getAllPlugins(tmpDir)).toEqual([])
    })

    it('discovers plugins from v5/plugins/', () => {
      writeManifest(tmpDir, 'pm-os-base', {
        name: 'pm-os-base', version: '5.0.0', description: 'Base', author: 'PM-OS',
        dependencies: [], commands: ['commands/base.md'], skills: [], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-base', 'base.md')

      const plugins = getAllPlugins(tmpDir)
      expect(plugins).toHaveLength(1)
      expect(plugins[0].id).toBe('pm-os-base')
      expect(plugins[0].status).toBe('available')
    })

    it('marks plugin as installed when commands exist', () => {
      writeManifest(tmpDir, 'pm-os-base', {
        name: 'pm-os-base', version: '5.0.0', description: 'Base', author: 'PM-OS',
        dependencies: [], commands: ['commands/base.md'], skills: [], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-base', 'base.md')

      // Register the command
      const cmdDir = path.join(tmpDir, '.claude', 'commands')
      mkdirSync(cmdDir, { recursive: true })
      writeFileSync(path.join(cmdDir, 'base.md'), '# base')

      const plugins = getAllPlugins(tmpDir)
      expect(plugins[0].status).toBe('installed')
    })

    it('ignores directories not starting with pm-os-', () => {
      const otherDir = path.join(tmpDir, 'v5', 'plugins', 'other-plugin', '.claude-plugin')
      mkdirSync(otherDir, { recursive: true })
      writeFileSync(path.join(otherDir, 'plugin.json'), '{}')

      expect(getAllPlugins(tmpDir)).toEqual([])
    })
  })

  describe('getInstalledPlugins / getAvailablePlugins', () => {
    it('splits by status correctly', () => {
      writeManifest(tmpDir, 'pm-os-base', {
        name: 'pm-os-base', version: '5.0.0', description: 'Base', author: 'PM-OS',
        dependencies: [], commands: ['commands/base.md'], skills: [], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-base', 'base.md')

      writeManifest(tmpDir, 'pm-os-brain', {
        name: 'pm-os-brain', version: '5.0.0', description: 'Brain', author: 'PM-OS',
        dependencies: ['pm-os-base'], commands: ['commands/brain.md'], skills: [], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-brain', 'brain.md')

      // Install base only
      const cmdDir = path.join(tmpDir, '.claude', 'commands')
      mkdirSync(cmdDir, { recursive: true })
      writeFileSync(path.join(cmdDir, 'base.md'), '# base')

      expect(getInstalledPlugins(tmpDir)).toHaveLength(1)
      expect(getAvailablePlugins(tmpDir)).toHaveLength(1)
      expect(getInstalledPlugins(tmpDir)[0].id).toBe('pm-os-base')
      expect(getAvailablePlugins(tmpDir)[0].id).toBe('pm-os-brain')
    })
  })

  describe('installPlugin', () => {
    it('copies commands and skills to .claude/', () => {
      writeManifest(tmpDir, 'pm-os-base', {
        name: 'pm-os-base', version: '5.0.0', description: 'Base', author: 'PM-OS',
        dependencies: [], commands: ['commands/base.md'], skills: ['skills/base-skill.md'], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-base', 'base.md')
      writeSkill(tmpDir, 'pm-os-base', 'base-skill.md')

      const result = installPlugin(tmpDir, 'pm-os-base')
      expect(result.success).toBe(true)
      expect(existsSync(path.join(tmpDir, '.claude', 'commands', 'base.md'))).toBe(true)
      expect(existsSync(path.join(tmpDir, '.claude', 'skills', 'base-skill.md'))).toBe(true)
    })

    it('fails when dependency is not installed', () => {
      writeManifest(tmpDir, 'pm-os-base', {
        name: 'pm-os-base', version: '5.0.0', description: 'Base', author: 'PM-OS',
        dependencies: [], commands: ['commands/base.md'], skills: [], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-base', 'base.md')

      writeManifest(tmpDir, 'pm-os-brain', {
        name: 'pm-os-brain', version: '5.0.0', description: 'Brain', author: 'PM-OS',
        dependencies: ['pm-os-base'], commands: ['commands/brain.md'], skills: [], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-brain', 'brain.md')

      const result = installPlugin(tmpDir, 'pm-os-brain')
      expect(result.success).toBe(false)
      expect(result.error).toContain('Dependency not installed')
    })

    it('returns error for non-existent plugin', () => {
      const result = installPlugin(tmpDir, 'pm-os-nonexistent')
      expect(result.success).toBe(false)
      expect(result.error).toContain('not found')
    })
  })

  describe('disablePlugin', () => {
    it('removes commands and skills from .claude/', () => {
      writeManifest(tmpDir, 'pm-os-brain', {
        name: 'pm-os-brain', version: '5.0.0', description: 'Brain', author: 'PM-OS',
        dependencies: ['pm-os-base'], commands: ['commands/brain.md'], skills: ['skills/entity.md'], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-brain', 'brain.md')
      writeSkill(tmpDir, 'pm-os-brain', 'entity.md')

      // Simulate installed state
      const cmdDir = path.join(tmpDir, '.claude', 'commands')
      const skillDir = path.join(tmpDir, '.claude', 'skills')
      mkdirSync(cmdDir, { recursive: true })
      mkdirSync(skillDir, { recursive: true })
      writeFileSync(path.join(cmdDir, 'brain.md'), '# brain')
      writeFileSync(path.join(skillDir, 'entity.md'), '# entity')

      const result = disablePlugin(tmpDir, 'pm-os-brain')
      expect(result.success).toBe(true)
      expect(existsSync(path.join(cmdDir, 'brain.md'))).toBe(false)
      expect(existsSync(path.join(skillDir, 'entity.md'))).toBe(false)
    })

    it('refuses to disable pm-os-base', () => {
      const result = disablePlugin(tmpDir, 'pm-os-base')
      expect(result.success).toBe(false)
      expect(result.error).toContain('Cannot disable')
    })
  })

  describe('getPluginHealth', () => {
    it('returns error for non-existent plugin', () => {
      const health = getPluginHealth(tmpDir, 'pm-os-nonexistent')
      expect(health.status).toBe('error')
    })

    it('returns healthy for base with config.yaml', () => {
      writeManifest(tmpDir, 'pm-os-base', {
        name: 'pm-os-base', version: '5.0.0', description: 'Base', author: 'PM-OS',
        dependencies: [], commands: ['commands/base.md'], skills: [], mcp_servers: [],
      })
      writeCommand(tmpDir, 'pm-os-base', 'base.md')

      // Install it
      const cmdDir = path.join(tmpDir, '.claude', 'commands')
      mkdirSync(cmdDir, { recursive: true })
      writeFileSync(path.join(cmdDir, 'base.md'), '# base')

      // Create config.yaml
      const userDir = path.join(tmpDir, 'user')
      mkdirSync(userDir, { recursive: true })
      writeFileSync(path.join(userDir, 'config.yaml'), 'user:\n  name: Test')

      const health = getPluginHealth(tmpDir, 'pm-os-base')
      expect(health.status).toBe('healthy')
    })

    it('returns brain entity count', () => {
      writeManifest(tmpDir, 'pm-os-brain', {
        name: 'pm-os-brain', version: '5.0.0', description: 'Brain', author: 'PM-OS',
        dependencies: ['pm-os-base'], commands: ['commands/brain.md'], skills: ['skills/entity.md'], mcp_servers: [],
      })

      // Install it
      const cmdDir = path.join(tmpDir, '.claude', 'commands')
      mkdirSync(cmdDir, { recursive: true })
      writeFileSync(path.join(cmdDir, 'brain.md'), '# brain')

      // Create BRAIN.md
      const brainDir = path.join(tmpDir, 'user', 'brain')
      mkdirSync(brainDir, { recursive: true })
      writeFileSync(path.join(brainDir, 'BRAIN.md'), '<!-- Generated: 2026-04-02 | Entities: 117 -->')

      const health = getPluginHealth(tmpDir, 'pm-os-brain')
      expect(health.status).toBe('healthy')
      expect(health.metrics?.entityCount).toBe(117)
    })
  })
})
