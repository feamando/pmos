import { execFile } from 'child_process'
import * as fs from 'fs'
import * as path from 'path'
import { logInfo, logError, logOk } from './logger'
import type { StepResult } from './dep-installer'

function execAsync(cmd: string, args: string[], timeout = 30000): Promise<{ stdout: string; code: number }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout }, (err, stdout) => {
      resolve({ stdout: stdout?.toString() || '', code: err ? 1 : 0 })
    })
  })
}

export async function runPostSetup(pmosPath: string): Promise<StepResult> {
  const start = Date.now()
  logInfo('installer', `Running post-setup for ${pmosPath}`)
  const errors: string[] = []

  // 1. Ensure .mcp.json has correct paths
  const mcpPath = path.join(pmosPath, '.mcp.json')
  if (fs.existsSync(mcpPath)) {
    try {
      const mcpConfig = JSON.parse(fs.readFileSync(mcpPath, 'utf-8'))
      // Verify brain server path exists
      if (mcpConfig.mcpServers?.brain?.args?.[0]) {
        const brainServerPath = path.join(pmosPath, mcpConfig.mcpServers.brain.args[0])
        if (!fs.existsSync(brainServerPath)) {
          logInfo('installer', `Brain MCP server not found at expected path: ${brainServerPath}`)
        }
      }
    } catch (err: any) {
      logInfo('installer', `MCP config check skipped: ${err.message}`)
    }
  }

  // 2. Create sync manifest for commands
  const syncManifest = path.join(pmosPath, 'common', '.claude', 'commands', '.sync-manifest.json')
  if (!fs.existsSync(syncManifest)) {
    try {
      fs.mkdirSync(path.dirname(syncManifest), { recursive: true })
      fs.writeFileSync(syncManifest, JSON.stringify({ synced: new Date().toISOString(), files: {} }, null, 2))
      logInfo('installer', 'Created command sync manifest')
    } catch {
      // Non-critical
    }
  }

  // 3. Verify Python path can import PM-OS tools
  const venvPython = path.join(pmosPath, '.venv', 'bin', 'python3')
  if (fs.existsSync(venvPython)) {
    const toolsPath = path.join(pmosPath, 'common', 'tools')
    const testImport = `import sys; sys.path.insert(0, '${toolsPath}'); from config_loader import get_config; print('OK')`
    const result = await execAsync(venvPython, ['-c', testImport])
    if (result.code !== 0) {
      logInfo('installer', 'PM-OS tools import test failed (may be expected if config_loader not yet distributed)')
    } else {
      logOk('installer', 'PM-OS tools importable from venv')
    }
  }

  // 4. Create .claude/settings.local.json skeleton
  const settingsPath = path.join(pmosPath, '.claude', 'settings.local.json')
  if (!fs.existsSync(settingsPath)) {
    try {
      fs.mkdirSync(path.dirname(settingsPath), { recursive: true })
      fs.writeFileSync(settingsPath, JSON.stringify({}, null, 2))
      logInfo('installer', 'Created Claude settings skeleton')
    } catch {
      // Non-critical
    }
  }

  const duration = (Date.now() - start) / 1000
  if (errors.length > 0) {
    return { success: false, message: errors.join('; '), duration }
  }

  logOk('installer', `Post-setup complete (${duration.toFixed(1)}s)`)
  return { success: true, message: 'Post-setup complete', duration }
}
