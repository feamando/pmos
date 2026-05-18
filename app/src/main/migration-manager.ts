import path from 'path'
import { existsSync } from 'fs'
import { spawn } from 'child_process'
import { BrowserWindow } from 'electron'
import type { MigrationProgress } from '../shared/types'

export function detectV4Installation(pmosPath: string): { isV4: boolean; path?: string } {
  if (!pmosPath) return { isV4: false }

  // Check version from both locations, take the higher one
  const versionPaths = [
    path.join(pmosPath, 'hf-pm-os', 'package', 'VERSION'),
    path.join(pmosPath, 'hf-pm-os', 'VERSION'),
    path.join(pmosPath, 'package', 'VERSION'),
    path.join(pmosPath, 'VERSION'),
  ]

  for (const vp of versionPaths) {
    if (existsSync(vp)) {
      try {
        const version = require('fs').readFileSync(vp, 'utf-8').trim()
        if (version.startsWith('5.')) return { isV4: false }
      } catch { /* continue to next */ }
    }
  }

  // v5 plugin markers: check both v5/ workspace and .claude/ plugin registration
  const v5Markers = [
    path.join(pmosPath, 'v5', 'plugins', 'pm-os-base', '.claude-plugin', 'plugin.json'),
    path.join(pmosPath, '.claude', 'commands', 'base.md'),
    path.join(pmosPath, '.claude', 'skills', 'pm-os-base:base'),
  ]

  if (v5Markers.some(m => existsSync(m))) return { isV4: false }

  // v4.x marker: common/.claude/commands/brain.md exists without any v5 signal
  const v4Marker = path.join(pmosPath, 'common', '.claude', 'commands', 'brain.md')
  if (existsSync(v4Marker)) {
    return { isV4: true, path: pmosPath }
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
