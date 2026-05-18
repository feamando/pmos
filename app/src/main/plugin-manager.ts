import path from 'path'
import { existsSync, readdirSync, readFileSync, copyFileSync, mkdirSync, unlinkSync, writeFileSync, cpSync, rmSync } from 'fs'
import type { PluginInfo, PluginHealth, PluginActionResult } from '../shared/types'

interface PluginManifest {
  name: string
  version: string
  description: string
  author: string
  dependencies: string[]
  commands?: string[]
  skills?: string[]
  mcp_servers?: string[]
  requires?: { python?: string; config_keys?: string[] }
}

function readPluginManifest(pluginDir: string): PluginManifest | null {
  const manifestPath = path.join(pluginDir, '.claude-plugin', 'plugin.json')
  if (!existsSync(manifestPath)) return null
  try {
    return JSON.parse(readFileSync(manifestPath, 'utf-8'))
  } catch {
    return null
  }
}

function getCommandsDir(pmosPath: string): string {
  return path.join(pmosPath, '.claude', 'commands')
}

function getSkillsDir(pmosPath: string): string {
  return path.join(pmosPath, '.claude', 'skills')
}

function isPluginInstalled(pmosPath: string, manifest: PluginManifest, pluginDir: string): boolean {
  const commandsDir = getCommandsDir(pmosPath)
  for (const cmd of manifest.commands || []) {
    const cmdName = path.basename(cmd)
    if (existsSync(path.join(commandsDir, cmdName))) return true
  }
  const skillsDir = getSkillsDir(pmosPath)
  for (const skill of manifest.skills || []) {
    const skillDirName = path.basename(path.dirname(skill))
    if (existsSync(path.join(skillsDir, skillDirName, 'SKILL.md'))) return true
  }
  return false
}

export function getInstalledPlugins(pmosPath: string): PluginInfo[] {
  return getAllPlugins(pmosPath).filter((p) => p.status === 'installed')
}

export function getAvailablePlugins(pmosPath: string): PluginInfo[] {
  return getAllPlugins(pmosPath).filter((p) => p.status === 'available')
}

export function getAllPlugins(pmosPath: string): PluginInfo[] {
  const pluginsDir = path.join(pmosPath, 'v5', 'plugins')
  if (!existsSync(pluginsDir)) return []

  const plugins: PluginInfo[] = []
  const entries = readdirSync(pluginsDir, { withFileTypes: true })

  for (const entry of entries) {
    if (!entry.isDirectory() || !entry.name.startsWith('pm-os-')) continue
    if (entry.name === 'pm-os-hellodev-chatbot') continue
    const pluginDir = path.join(pluginsDir, entry.name)
    const manifest = readPluginManifest(pluginDir)
    if (!manifest) continue

    const installed = isPluginInstalled(pmosPath, manifest, pluginDir)

    plugins.push({
      id: manifest.name,
      name: manifest.name,
      version: manifest.version,
      description: manifest.description,
      author: typeof manifest.author === 'string' ? manifest.author : (manifest.author as any)?.name || 'Unknown',
      dependencies: manifest.dependencies || [],
      status: installed ? 'installed' : 'available',
      commands: manifest.commands || [],
      skills: manifest.skills || [],
      mcpServers: (manifest as any).mcpServers || manifest.mcp_servers || [],
      requires: manifest.requires,
    })
  }

  return plugins
}

export function installAllPlugins(pmosPath: string): { success: boolean; installed: string[]; errors: string[] } {
  const all = getAllPlugins(pmosPath)
  const installed: string[] = []
  const errors: string[] = []

  // Install base first (other plugins depend on it)
  const base = all.find((p) => p.id === 'pm-os-base')
  if (base && base.status !== 'installed') {
    const r = installPlugin(pmosPath, 'pm-os-base')
    if (r.success) installed.push('pm-os-base')
    else errors.push(`pm-os-base: ${r.error}`)
  } else if (base) {
    installed.push('pm-os-base')
  }

  // Then install the rest
  for (const plugin of all) {
    if (plugin.id === 'pm-os-base') continue
    if (plugin.status === 'installed') {
      installed.push(plugin.id)
      continue
    }
    const r = installPlugin(pmosPath, plugin.id)
    if (r.success) installed.push(plugin.id)
    else errors.push(`${plugin.id}: ${r.error}`)
  }

  return { success: errors.length === 0, installed, errors }
}

export function installPlugin(pmosPath: string, pluginId: string): PluginActionResult {
  const pluginsDir = path.join(pmosPath, 'v5', 'plugins')
  const pluginDir = path.join(pluginsDir, pluginId)

  if (!existsSync(pluginDir)) {
    return { success: false, pluginId, action: 'install', error: `Plugin directory not found: ${pluginId}` }
  }

  const manifest = readPluginManifest(pluginDir)
  if (!manifest) {
    return { success: false, pluginId, action: 'install', error: 'Invalid plugin manifest' }
  }

  // Check dependencies are installed
  for (const dep of manifest.dependencies) {
    const depDir = path.join(pluginsDir, dep)
    const depManifest = readPluginManifest(depDir)
    if (!depManifest || !isPluginInstalled(pmosPath, depManifest, depDir)) {
      return { success: false, pluginId, action: 'install', error: `Dependency not installed: ${dep}` }
    }
  }

  try {
    // Copy commands
    const commandsDir = getCommandsDir(pmosPath)
    mkdirSync(commandsDir, { recursive: true })
    for (const cmd of manifest.commands || []) {
      const src = path.join(pluginDir, cmd)
      const dest = path.join(commandsDir, path.basename(cmd))
      if (existsSync(src)) copyFileSync(src, dest)
    }

    // Copy skills (each skill is a directory containing SKILL.md)
    const skillsDir = getSkillsDir(pmosPath)
    mkdirSync(skillsDir, { recursive: true })
    for (const skill of manifest.skills || []) {
      const skillDir = path.dirname(skill)
      const skillName = path.basename(skillDir)
      const src = path.join(pluginDir, skillDir)
      const dest = path.join(skillsDir, skillName)
      if (existsSync(src)) {
        mkdirSync(dest, { recursive: true })
        cpSync(src, dest, { recursive: true })
      }
    }

    // Merge MCP servers
    mergeMcpServers(pmosPath, pluginDir)

    return { success: true, pluginId, action: 'install' }
  } catch (err: any) {
    return { success: false, pluginId, action: 'install', error: err.message }
  }
}

export function disablePlugin(pmosPath: string, pluginId: string): PluginActionResult {
  if (pluginId === 'pm-os-base') {
    return { success: false, pluginId, action: 'disable', error: 'Cannot disable pm-os-base — it is required by all plugins' }
  }

  const pluginsDir = path.join(pmosPath, 'v5', 'plugins')
  const pluginDir = path.join(pluginsDir, pluginId)
  const manifest = readPluginManifest(pluginDir)
  if (!manifest) {
    return { success: false, pluginId, action: 'disable', error: 'Plugin manifest not found' }
  }

  try {
    // Remove commands
    const commandsDir = getCommandsDir(pmosPath)
    for (const cmd of manifest.commands || []) {
      const dest = path.join(commandsDir, path.basename(cmd))
      if (existsSync(dest)) unlinkSync(dest)
    }

    // Remove skill directories
    const skillsDir = getSkillsDir(pmosPath)
    for (const skill of manifest.skills || []) {
      const skillDir = path.dirname(skill)
      const skillName = path.basename(skillDir)
      const dest = path.join(skillsDir, skillName)
      if (existsSync(dest)) rmSync(dest, { recursive: true })
    }

    // Remove MCP entries
    removeMcpServers(pmosPath, pluginDir)

    return { success: true, pluginId, action: 'disable' }
  } catch (err: any) {
    return { success: false, pluginId, action: 'disable', error: err.message }
  }
}

export function getPluginHealth(pmosPath: string, pluginId: string): PluginHealth {
  const pluginsDir = path.join(pmosPath, 'v5', 'plugins')
  const pluginDir = path.join(pluginsDir, pluginId)
  const manifest = readPluginManifest(pluginDir)

  if (!manifest) {
    return { status: 'error', message: 'Plugin not found', lastChecked: Date.now() }
  }

  const installed = isPluginInstalled(pmosPath, manifest, pluginDir)
  if (!installed) {
    return { status: 'unknown', message: 'Not installed', lastChecked: Date.now() }
  }

  // Plugin-specific health checks
  if (pluginId === 'pm-os-base') {
    const configPath = path.join(pmosPath, 'user', 'config.yaml')
    if (!existsSync(configPath)) {
      return { status: 'degraded', message: 'config.yaml not found', lastChecked: Date.now() }
    }
    return { status: 'healthy', message: 'Config valid', lastChecked: Date.now() }
  }

  if (pluginId === 'pm-os-brain') {
    const brainMd = path.join(pmosPath, 'user', 'brain', 'BRAIN.md')
    if (!existsSync(brainMd)) {
      return { status: 'degraded', message: 'BRAIN.md not found', lastChecked: Date.now() }
    }
    try {
      const content = readFileSync(brainMd, 'utf-8')
      const entityMatch = content.match(/Entities: (\d+)/)
      const count = entityMatch ? parseInt(entityMatch[1], 10) : 0
      return {
        status: 'healthy',
        message: `${count} entities indexed`,
        metrics: { entityCount: count },
        lastChecked: Date.now(),
      }
    } catch {
      return { status: 'degraded', message: 'Could not read BRAIN.md', lastChecked: Date.now() }
    }
  }

  if (pluginId === 'pm-os-daily-workflow') {
    const contextDir = path.join(pmosPath, 'user', 'personal', 'context')
    if (!existsSync(contextDir)) {
      return { status: 'degraded', message: 'Context directory not found', lastChecked: Date.now() }
    }
    try {
      const files = readdirSync(contextDir).filter((f) => f.match(/^\d{4}-\d{2}-\d{2}/)).sort().reverse()
      if (files.length === 0) {
        return { status: 'degraded', message: 'No context files', lastChecked: Date.now() }
      }
      return { status: 'healthy', message: `Latest: ${files[0]}`, lastChecked: Date.now() }
    } catch {
      return { status: 'degraded', message: 'Could not read context dir', lastChecked: Date.now() }
    }
  }

  // Generic check for other plugins
  return { status: 'healthy', message: 'Installed', lastChecked: Date.now() }
}

function mergeMcpServers(pmosPath: string, pluginDir: string): void {
  const pluginMcpPath = path.join(pluginDir, '.mcp.json')
  if (!existsSync(pluginMcpPath)) return

  try {
    const pluginMcp = JSON.parse(readFileSync(pluginMcpPath, 'utf-8'))
    const servers = pluginMcp.mcpServers || {}
    if (Object.keys(servers).length === 0) return

    const rootMcpPath = path.join(pmosPath, '.mcp.json')
    let rootMcp: any = { mcpServers: {} }
    if (existsSync(rootMcpPath)) {
      rootMcp = JSON.parse(readFileSync(rootMcpPath, 'utf-8'))
      if (!rootMcp.mcpServers) rootMcp.mcpServers = {}
    }

    Object.assign(rootMcp.mcpServers, servers)
    writeFileSync(rootMcpPath, JSON.stringify(rootMcp, null, 2), 'utf-8')
  } catch {
    // Non-fatal: MCP merge failure
  }
}

function removeMcpServers(pmosPath: string, pluginDir: string): void {
  const pluginMcpPath = path.join(pluginDir, '.mcp.json')
  if (!existsSync(pluginMcpPath)) return

  try {
    const pluginMcp = JSON.parse(readFileSync(pluginMcpPath, 'utf-8'))
    const servers = pluginMcp.mcpServers || {}
    if (Object.keys(servers).length === 0) return

    const rootMcpPath = path.join(pmosPath, '.mcp.json')
    if (!existsSync(rootMcpPath)) return

    const rootMcp = JSON.parse(readFileSync(rootMcpPath, 'utf-8'))
    if (!rootMcp.mcpServers) return

    for (const key of Object.keys(servers)) {
      delete rootMcp.mcpServers[key]
    }

    writeFileSync(rootMcpPath, JSON.stringify(rootMcp, null, 2), 'utf-8')
  } catch {
    // Non-fatal
  }
}
