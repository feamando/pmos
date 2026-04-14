import { readFileSync, existsSync } from 'fs'
import path from 'path'
import { logInfo, logError } from '../installer/logger'
import { pullPmosRepo } from './git-updater'
import { downloadBinary, verifyChecksum, getUpdateDir } from './downloader'
import { replaceApp, relaunchApp } from './installer'
import type { UpdateManifest, UpdateCheckResult } from '../../shared/types'

type ProgressCallback = (status: string, percent: number, message: string) => void

export function readManifest(pmosPath: string): UpdateManifest {
  const manifestPath = path.join(pmosPath, 'common', 'releases', 'pmos-manifest.json')
  if (!existsSync(manifestPath)) {
    throw new Error('Update manifest not found')
  }
  const raw = readFileSync(manifestPath, 'utf-8')
  return JSON.parse(raw) as UpdateManifest
}

/**
 * Compare versions. Format: {semver}-{YYYYMMDD}
 * Returns true if manifestVersion is newer than currentVersion.
 */
export function isNewerVersion(currentVersion: string, manifestVersion: string): boolean {
  // Strip any leading 'v'
  const current = currentVersion.replace(/^v/, '')
  const manifest = manifestVersion.replace(/^v/, '')

  // Split into semver and date parts
  const [currentSemver, currentDate] = current.split('-')
  const [manifestSemver, manifestDate] = manifest.split('-')

  // Compare semver parts first
  const cParts = (currentSemver || '').split('.').map(Number)
  const mParts = (manifestSemver || '').split('.').map(Number)

  for (let i = 0; i < 3; i++) {
    const c = cParts[i] || 0
    const m = mParts[i] || 0
    if (m > c) return true
    if (m < c) return false
  }

  // Semver equal — compare date stamps
  if (manifestDate && currentDate) {
    return manifestDate > currentDate
  }
  // If manifest has date but current doesn't, manifest is newer
  if (manifestDate && !currentDate) return true

  return false
}

export function checkForUpdates(pmosPath: string, currentVersion: string): UpdateCheckResult {
  try {
    const manifest = readManifest(pmosPath)
    const available = isNewerVersion(currentVersion, manifest.version)
    return {
      available,
      currentVersion,
      latestVersion: manifest.version,
      releaseNotes: manifest.releaseNotes,
    }
  } catch (err: any) {
    return {
      available: false,
      currentVersion,
      latestVersion: currentVersion,
      error: err.message,
    }
  }
}

export async function performUpdate(
  pmosPath: string,
  currentVersion: string,
  devMode: boolean,
  sendProgress: ProgressCallback
): Promise<void> {
  // Step 1: Git pull PM-OS (updates manifest + tools)
  if (devMode) {
    sendProgress('checking', 15, 'Dev mode — skipping git pull')
  } else {
    sendProgress('checking', 5, 'Pulling latest PM-OS changes...')
    const gitResult = await pullPmosRepo(pmosPath)
    if (!gitResult.success) {
      throw new Error(`Git pull failed: ${gitResult.message}`)
    }
    sendProgress('checking', 15, `PM-OS updated: ${gitResult.message}`)
  }

  // Step 2: Read manifest and check version
  sendProgress('checking', 20, 'Reading update manifest...')
  let manifest: UpdateManifest
  try {
    manifest = readManifest(pmosPath)
  } catch (err: any) {
    if (devMode) {
      sendProgress('up-to-date', 100, `Dev mode — no manifest available. Current version: ${currentVersion}`)
      return
    }
    throw new Error(`Failed to read manifest: ${err.message}`)
  }

  const newer = isNewerVersion(currentVersion, manifest.version)
  if (!newer) {
    sendProgress('up-to-date', 100, `Already on latest version (${currentVersion})`)
    return
  }

  logInfo('updater', `Update available: ${currentVersion} → ${manifest.version}`)

  // Get platform-specific info
  const platformInfo = manifest.platform['darwin']
  if (!platformInfo) {
    throw new Error('No macOS binary available in manifest')
  }

  // Step 3: Download binary
  sendProgress('downloading', 25, `Downloading ${manifest.version}...`)
  const destPath = path.join(getUpdateDir(), platformInfo.filename)
  await downloadBinary(platformInfo.url, destPath, (downloaded, total) => {
    const pct = Math.round(25 + (downloaded / total) * 50)
    sendProgress('downloading', pct, `Downloading... ${Math.round((downloaded / total) * 100)}%`)
  })

  // Step 4: Verify checksum
  sendProgress('verifying', 80, 'Verifying checksum...')
  const checksumResult = await verifyChecksum(destPath, platformInfo.sha256)
  if (!checksumResult.valid) {
    throw new Error(`Checksum mismatch: expected ${platformInfo.sha256}, got ${checksumResult.actual}`)
  }

  // Step 5: Replace app (skip in dev mode)
  if (devMode) {
    sendProgress('up-to-date', 100, `Update downloaded and verified (${manifest.version}). Dev mode — skipping app replacement. Restart manually.`)
    logInfo('updater', 'Dev mode: skipping app replacement and relaunch')
    return
  }

  sendProgress('installing', 90, 'Installing update...')
  await replaceApp(destPath)

  // Step 6: Relaunch
  sendProgress('relaunching', 100, 'Relaunching PM-OS...')
  // Small delay so the UI can show the status
  await new Promise((r) => setTimeout(r, 1000))
  relaunchApp()
}
