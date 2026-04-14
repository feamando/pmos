import * as fs from 'fs'
import * as path from 'path'
import { logInfo, logError, logOk } from './logger'
import type { StepResult } from './dep-installer'

const DIRS = [
  'common',
  'user',
  'user/.secrets',
  'user/.config',
  'user/brain',
  'user/brain/Entities',
  'user/personal',
  'user/personal/context',
  'user/sessions',
  'user/planning',
  'user/products',
  'user/team',
  '.claude',
]

export async function createFolderStructure(basePath: string): Promise<StepResult> {
  const start = Date.now()
  logInfo('installer', `Creating folder structure at ${basePath}`)

  try {
    // Create base
    fs.mkdirSync(basePath, { recursive: true })

    // Create all subdirs
    for (const dir of DIRS) {
      const fullPath = path.join(basePath, dir)
      if (!fs.existsSync(fullPath)) {
        fs.mkdirSync(fullPath, { recursive: true })
        logInfo('installer', `Created: ${dir}`)
      }
    }

    // Create marker file
    const markerPath = path.join(basePath, '.pm-os-root')
    if (!fs.existsSync(markerPath)) {
      fs.writeFileSync(markerPath, `pm-os-root\ninstalled=${new Date().toISOString()}\n`)
    }

    // Set .secrets permissions
    const secretsPath = path.join(basePath, 'user', '.secrets')
    try {
      fs.chmodSync(secretsPath, 0o700)
    } catch {
      logInfo('installer', 'Could not set .secrets permissions (non-critical)')
    }

    logOk('installer', `Folder structure created (${((Date.now() - start) / 1000).toFixed(1)}s)`)
    return { success: true, message: 'Folder structure created', duration: (Date.now() - start) / 1000 }
  } catch (err: any) {
    logError('installer', `Scaffold failed: ${err.message}`)
    return { success: false, message: err.message, duration: (Date.now() - start) / 1000 }
  }
}

export async function distributeGoogleCredentials(basePath: string, bundlePath: string): Promise<StepResult> {
  const start = Date.now()
  const srcPath = path.join(bundlePath, 'data', 'google_client_secret.json')
  const destPath = path.join(basePath, 'user', '.secrets', 'credentials.json')

  if (!fs.existsSync(srcPath)) {
    logInfo('installer', 'No bundled Google credentials to distribute')
    return { success: true, message: 'No credentials to distribute', duration: 0 }
  }

  if (fs.existsSync(destPath)) {
    logInfo('installer', 'Google credentials already exist — skipping')
    return { success: true, message: 'Already exists', duration: 0 }
  }

  try {
    const destDir = path.dirname(destPath)
    fs.mkdirSync(destDir, { recursive: true })
    fs.copyFileSync(srcPath, destPath)
    fs.chmodSync(destDir, 0o700)
    logOk('installer', 'Google credentials distributed')
    return { success: true, message: 'Credentials distributed', duration: (Date.now() - start) / 1000 }
  } catch (err: any) {
    logError('installer', `Credentials distribution failed: ${err.message}`)
    return { success: false, message: err.message, duration: (Date.now() - start) / 1000 }
  }
}
