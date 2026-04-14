import { execFile } from 'child_process'
import { existsSync, renameSync, rmSync, chmodSync, statSync } from 'fs'
import path from 'path'
import { app } from 'electron'
import { logInfo, logError } from '../installer/logger'

function runCommand(cmd: string, args: string[], cwd?: string): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { cwd, timeout: 120000 }, (err, stdout, stderr) => {
      if (err) reject(new Error(stderr?.trim() || err.message))
      else resolve(stdout.trim())
    })
  })
}

/**
 * Resolve the .app bundle path from process.execPath.
 * macOS production: /Applications/PM-OS.app/Contents/MacOS/PM-OS
 * Walk up to find the *.app directory.
 */
export function resolveAppBundlePath(): string | null {
  let current = process.execPath
  while (current !== '/') {
    if (current.endsWith('.app')) return current
    current = path.dirname(current)
  }
  return null
}

export async function replaceApp(zipPath: string): Promise<void> {
  const appPath = resolveAppBundlePath()
  if (!appPath) {
    throw new Error('Could not determine current .app bundle path')
  }

  logInfo('updater', `Replacing app at: ${appPath}`)

  const appDir = path.dirname(appPath)
  const appName = path.basename(appPath)
  const backupPath = `${appPath}.backup`
  const tempExtract = path.join(appDir, '.pmos-update-temp')

  try {
    // Unzip to temp location
    if (existsSync(tempExtract)) rmSync(tempExtract, { recursive: true })

    // Use ditto on macOS (preserves permissions and extended attributes)
    await runCommand('ditto', ['-xk', zipPath, tempExtract])

    // Find the .app inside the extracted archive
    const extractedApp = findAppInDir(tempExtract)
    if (!extractedApp) {
      throw new Error('No .app bundle found in downloaded archive')
    }

    // Get original permissions
    const originalStat = statSync(appPath)

    // Backup current app
    if (existsSync(backupPath)) rmSync(backupPath, { recursive: true })
    renameSync(appPath, backupPath)
    logInfo('updater', 'Current app backed up')

    // Move new app into place (atomic at filesystem level)
    await runCommand('mv', [extractedApp, appPath])
    logInfo('updater', 'New app moved into place')

    // Preserve permissions
    try {
      chmodSync(appPath, originalStat.mode)
    } catch { /* best effort */ }

    // Clean up backup and temp
    rmSync(backupPath, { recursive: true, force: true })
    rmSync(tempExtract, { recursive: true, force: true })

    logInfo('updater', 'App replacement complete')
  } catch (err: any) {
    // Restore from backup on failure
    logError('updater', `App replacement failed: ${err.message}`)
    if (existsSync(backupPath) && !existsSync(appPath)) {
      renameSync(backupPath, appPath)
      logInfo('updater', 'Restored from backup')
    }
    // Clean up temp
    if (existsSync(tempExtract)) rmSync(tempExtract, { recursive: true, force: true })
    throw err
  }
}

function findAppInDir(dir: string): string | null {
  const { readdirSync } = require('fs')
  const entries = readdirSync(dir)

  // Direct .app in root
  for (const entry of entries) {
    if (entry.endsWith('.app')) {
      return path.join(dir, entry)
    }
  }

  // Check one level deep
  for (const entry of entries) {
    const subdir = path.join(dir, entry)
    try {
      const stat = statSync(subdir)
      if (stat.isDirectory()) {
        const subEntries = readdirSync(subdir)
        for (const sub of subEntries) {
          if (sub.endsWith('.app')) {
            return path.join(subdir, sub)
          }
        }
      }
    } catch { /* skip */ }
  }

  return null
}

export function relaunchApp(): void {
  logInfo('updater', 'Relaunching app...')

  // Set flag so hide-to-tray close handler doesn't intercept
  ;(app as any).isQuitting = true

  app.relaunch({ args: process.argv.slice(1) })
  app.exit(0)
}
