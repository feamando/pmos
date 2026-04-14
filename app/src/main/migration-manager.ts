import path from 'path'
import { existsSync } from 'fs'
import { spawn } from 'child_process'
import { BrowserWindow } from 'electron'
import type { MigrationProgress } from '../shared/types'

export function detectV4Installation(pmosPath: string): { isV4: boolean; path?: string } {
  if (!pmosPath) return { isV4: false }

  // v4.x marker: common/.claude/commands/brain.md exists
  const v4Marker = path.join(pmosPath, 'common', '.claude', 'commands', 'brain.md')
  // v5 marker: v5/plugins directory with marketplace
  const v5Marker = path.join(pmosPath, 'v5', 'plugins', 'pm-os-base', '.claude-plugin', 'plugin.json')

  const hasV4Commands = existsSync(v4Marker)
  const hasV5Plugins = existsSync(v5Marker)

  // v4.x if old commands exist but v5 plugins not yet installed (commands not registered)
  if (hasV4Commands && !hasV5Plugins) {
    return { isV4: true, path: pmosPath }
  }

  // Also detect if v5 plugins exist but are not registered (available but not installed)
  // This means migration hasn't completed the install step
  if (hasV4Commands && hasV5Plugins) {
    const commandsDir = path.join(pmosPath, '.claude', 'commands')
    // Check if v5 base command is registered
    const v5BaseCommand = path.join(commandsDir, 'base.md')
    if (!existsSync(v5BaseCommand)) {
      return { isV4: true, path: pmosPath }
    }
  }

  return { isV4: false }
}

export function startMigration(pmosPath: string): void {
  const migrationScript = path.join(pmosPath, 'v5', 'migration', 'migrate_to_v5.py')

  if (!existsSync(migrationScript)) {
    sendProgress({ step: 'error', percent: 0, message: 'Migration script not found: v5/migration/migrate_to_v5.py' })
    return
  }

  // Determine python binary
  const venvPython = path.join(pmosPath, '.venv', 'bin', 'python3')
  const pythonBin = existsSync(venvPython) ? venvPython : 'python3'

  sendProgress({ step: 'analyzing', percent: 5, message: 'Starting migration analysis...' })

  const child = spawn(pythonBin, [migrationScript, '--auto-confirm'], {
    cwd: pmosPath,
    env: { ...process.env, PM_OS_ROOT: pmosPath },
    stdio: ['pipe', 'pipe', 'pipe'],
  })

  let stdout = ''
  let stderr = ''

  child.stdout.on('data', (data: Buffer) => {
    const text = data.toString()
    stdout += text
    parseProgressOutput(text)
  })

  child.stderr.on('data', (data: Buffer) => {
    stderr += data.toString()
  })

  child.on('close', (code: number | null) => {
    if (code === 0) {
      sendProgress({ step: 'done', percent: 100, message: 'Migration completed successfully' })
    } else {
      sendProgress({
        step: 'error',
        percent: 0,
        message: stderr.trim() || `Migration failed with exit code ${code}`,
      })
    }
  })

  child.on('error', (err: Error) => {
    sendProgress({ step: 'error', percent: 0, message: `Failed to start migration: ${err.message}` })
  })
}

export function rollbackMigration(pmosPath: string): { success: boolean; error?: string } {
  // The migration script creates a git tag for backup
  // Rollback by checking if the tag exists and reverting
  try {
    const { execSync } = require('child_process')
    // Find the latest migration backup tag
    const tags = execSync('git tag -l "v4-backup-*" --sort=-creatordate', {
      cwd: pmosPath,
      encoding: 'utf-8',
    }).trim()

    if (!tags) {
      return { success: false, error: 'No migration backup found' }
    }

    const latestTag = tags.split('\n')[0]
    execSync(`git checkout ${latestTag} -- .`, { cwd: pmosPath })
    return { success: true }
  } catch (err: any) {
    return { success: false, error: err.message }
  }
}

function sendProgress(progress: MigrationProgress): void {
  const windows = BrowserWindow.getAllWindows()
  for (const win of windows) {
    if (!win.isDestroyed()) {
      win.webContents.send('migration-progress', progress)
    }
  }
}

function parseProgressOutput(text: string): void {
  const lines = text.split('\n').filter(Boolean)

  for (const line of lines) {
    const lower = line.toLowerCase()

    if (lower.includes('analyzing') || lower.includes('analysis')) {
      sendProgress({ step: 'analyzing', percent: 15, message: line.trim() })
    } else if (lower.includes('backup') || lower.includes('backing')) {
      sendProgress({ step: 'backing-up', percent: 30, message: line.trim() })
    } else if (lower.includes('migrat')) {
      sendProgress({ step: 'migrating', percent: 55, message: line.trim() })
    } else if (lower.includes('validat')) {
      sendProgress({ step: 'validating', percent: 80, message: line.trim() })
    } else if (lower.includes('complete') || lower.includes('success')) {
      sendProgress({ step: 'done', percent: 100, message: line.trim() })
    }
  }
}
