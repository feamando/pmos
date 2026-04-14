import { ipcMain, BrowserWindow, shell, app } from 'electron'
import { parseEnvFile, readAllEnvValues, writeEnvValues, migrateGithubToken } from './env/env-manager'
import { detectPmosPath, validateEnvPath } from './env/path-detector'
import { CONNECTION_CONFIGS, getAllEnvKeys } from '../shared/connection-configs'
import { getInstallConfig, setInstallConfig } from './installer/config-store'
import { detectPmosInstallation, validateCustomPath } from './installer/detection'
import { getRecentLogs, logInfo, logError } from './installer/logger'
import { buildDiagnosticBundle, logClick, logOutputError } from './telemetry/telemetry-logger'
import { isDevMode } from './installer/dev-mode'
import type { ConnectionState, HealthStatus, SaveResult, TestResult, AppMode, ConfigValidationResult, BrainHealthResult, DailyContextResult, CCEHubResult, AppVersionInfo, UpdateCheckResult, PluginInfo, PluginHealth, PluginActionResult } from '../shared/types'
import { getInstalledPlugins, getAvailablePlugins, installPlugin, disablePlugin, getPluginHealth } from './plugin-manager'
import { detectV4Installation, startMigration, rollbackMigration } from './migration-manager'
import { computeBrainHealth, getSyntheticBrainHealth } from './brain/brain-health'
import { findLatestContextFile, parseContextFile, readUserName, getSyntheticContext } from './homepage/context-parser'
import { getCCEProjects, getSyntheticCCEData } from './cce/cce-data'
import { readConfigYaml, writeConfigYaml, validateConfigYaml } from './config-yaml-manager'
import path from 'path'
import { existsSync, readFileSync, copyFileSync, mkdirSync } from 'fs'

let currentEnvPath: string | null = null

export function setEnvPathInternal(p: string) { currentEnvPath = p }
export function getEnvPathInternal() { return currentEnvPath }

export function registerIpcHandlers() {
  ipcMain.handle('get-env-path', () => currentEnvPath)

  ipcMain.handle('set-env-path', async (_event, envPath: string) => {
    const valid = await validateEnvPath(envPath)
    if (valid) {
      currentEnvPath = envPath
      await migrateGithubToken(envPath)
    }
    return valid
  })

  ipcMain.handle('detect-pmos', async () => {
    return detectPmosPath()
  })

  ipcMain.handle('get-connections', async (): Promise<ConnectionState[]> => {
    if (!currentEnvPath) {
      return CONNECTION_CONFIGS.map((config) => ({
        id: config.id,
        name: config.name,
        icon: config.icon,
        brandColor: config.brandColor,
        active: false,
        fields: {},
        health: { connectionId: config.id, status: 'unknown' as const },
      }))
    }

    const envFile = await parseEnvFile(currentEnvPath)
    const allValues = readAllEnvValues(envFile, getAllEnvKeys())

    return CONNECTION_CONFIGS.map((config) => {
      const fields: Record<string, string> = {}
      let hasAnyValue = false
      for (const field of config.fields) {
        fields[field.envKey] = allValues[field.envKey] || ''
        if (allValues[field.envKey]) hasAnyValue = true
      }

      return {
        id: config.id,
        name: config.name,
        icon: config.icon,
        brandColor: config.brandColor,
        active: hasAnyValue,
        fields,
        health: { connectionId: config.id, status: 'unknown' as const },
      }
    })
  })

  ipcMain.handle('save-connection', async (_event, id: string, fields: Record<string, string>): Promise<SaveResult> => {
    if (!currentEnvPath) return { success: false, error: 'No .env file configured' }
    try {
      await writeEnvValues(currentEnvPath, fields)
      return { success: true }
    } catch (err: any) {
      logOutputError('ipc:save-connection', err.message)
      return { success: false, error: err.message }
    }
  })

  ipcMain.handle('test-connection', async (_event, id: string): Promise<TestResult> => {
    // Health checker will be wired in Loop 6
    return { success: false, message: 'Health checking not yet implemented' }
  })

  ipcMain.handle('copy-from-jira', async (): Promise<Record<string, string>> => {
    if (!currentEnvPath) return {}
    const envFile = await parseEnvFile(currentEnvPath)
    const values = readAllEnvValues(envFile, ['JIRA_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN'])
    return values
  })

  // --- Installer IPC handlers (v0.1) ---

  ipcMain.handle('get-install-config', () => {
    return getInstallConfig()
  })

  ipcMain.handle('detect-pmos-install', () => {
    return detectPmosInstallation()
  })

  ipcMain.handle('validate-pmos-path', (_event, customPath: string) => {
    return validateCustomPath(customPath)
  })

  ipcMain.handle('get-recent-logs', (_event, category: string, lines?: number) => {
    return getRecentLogs(category as any, lines)
  })

  // --- Onboarding IPC handlers (v0.2) ---

  ipcMain.handle('get-app-mode', (): AppMode => {
    const config = getInstallConfig()
    if (config.installComplete && !config.onboardingComplete) return 'onboarding'
    if (config.onboardingComplete && !config.userSetupComplete) return 'user-setup'
    return 'connections'
  })

  ipcMain.handle('complete-onboarding', () => {
    setInstallConfig({ onboardingComplete: true })
    logInfo('onboarding', 'Connections onboarding complete')
    // Transition to user-setup (v0.3), not connections
    const windows = BrowserWindow.getAllWindows()
    for (const win of windows) {
      if (!win.isDestroyed()) {
        win.webContents.send('app-mode-changed', 'user-setup' as AppMode)
      }
    }
  })

  ipcMain.handle('is-dev-mode', () => {
    return isDevMode()
  })

  ipcMain.handle('load-dev-credentials', async () => {
    // Read real ~/pm-os/user/.env for dev testing
    const homeDir = process.env.HOME || process.env.USERPROFILE || ''
    const realEnvPath = path.join(homeDir, 'pm-os', 'user', '.env')
    if (!existsSync(realEnvPath)) return {}
    try {
      const envFile = await parseEnvFile(realEnvPath)
      const allKeys = getAllEnvKeys()
      return readAllEnvValues(envFile, allKeys)
    } catch (err: any) {
      logError('onboarding', `Failed to load dev credentials: ${err.message}`)
      return {}
    }
  })

  ipcMain.handle('upload-google-credentials', async (_event, filePath: string) => {
    try {
      if (!existsSync(filePath)) {
        return { success: false, error: 'File not found' }
      }
      const content = readFileSync(filePath, 'utf-8')
      const json = JSON.parse(content)
      if (!json.installed && !json.web) {
        return { success: false, error: 'Invalid Google OAuth credentials file. Must contain "installed" or "web" key.' }
      }
      const config = getInstallConfig()
      if (!config.pmosPath) {
        return { success: false, error: 'PM-OS path not configured' }
      }
      const secretsDir = path.join(config.pmosPath, 'user', '.secrets')
      mkdirSync(secretsDir, { recursive: true, mode: 0o700 })
      const destPath = path.join(secretsDir, 'credentials.json')
      copyFileSync(filePath, destPath)
      logInfo('onboarding', 'Google credentials uploaded to .secrets/credentials.json')
      return { success: true }
    } catch (err: any) {
      logError('onboarding', `Google credentials upload failed: ${err.message}`)
      logOutputError('ipc:upload-google-credentials', err.message)
      return { success: false, error: err.message }
    }
  })

  // --- User Setup IPC handlers (v0.3) ---

  ipcMain.handle('save-user-setup-step', async (_event, stepId: string, data: Record<string, any>): Promise<SaveResult> => {
    const config = getInstallConfig()
    if (!config.pmosPath) return { success: false, error: 'PM-OS path not configured' }
    try {
      writeConfigYaml(config.pmosPath, data)
      logInfo('user-setup', `Step "${stepId}" saved to config.yaml`)
      return { success: true }
    } catch (err: any) {
      logError('user-setup', `Failed to save step "${stepId}": ${err.message}`)
      logOutputError('ipc:save-user-setup-step', err.message)
      return { success: false, error: err.message }
    }
  })

  ipcMain.handle('load-dev-config', async (): Promise<Record<string, any>> => {
    const homeDir = process.env.HOME || process.env.USERPROFILE || ''
    const realPmosPath = path.join(homeDir, 'pm-os')
    try {
      return readConfigYaml(realPmosPath)
    } catch (err: any) {
      logError('user-setup', `Failed to load dev config: ${err.message}`)
      return {}
    }
  })

  ipcMain.handle('validate-config', async (): Promise<ConfigValidationResult> => {
    const config = getInstallConfig()
    if (!config.pmosPath) return { valid: false, errors: ['PM-OS path not configured'], warnings: [] }
    try {
      const data = readConfigYaml(config.pmosPath)
      return validateConfigYaml(data)
    } catch (err: any) {
      return { valid: false, errors: [`Failed to read config: ${err.message}`], warnings: [] }
    }
  })

  ipcMain.handle('complete-user-setup', () => {
    setInstallConfig({ userSetupComplete: true })
    logInfo('user-setup', 'User setup complete')
    const windows = BrowserWindow.getAllWindows()
    for (const win of windows) {
      if (!win.isDestroyed()) {
        win.webContents.send('app-mode-changed', 'connections' as AppMode)
      }
    }
  })

  // --- Settings IPC handlers (v0.4) ---

  ipcMain.handle('load-config-yaml', async () => {
    const config = getInstallConfig()
    if (!config.pmosPath) return { success: false, data: {}, error: 'PM-OS path not configured' }
    try {
      const data = readConfigYaml(config.pmosPath)
      return { success: true, data }
    } catch (err: any) {
      logError('settings', `Failed to load config.yaml: ${err.message}`)
      logOutputError('ipc:load-config-yaml', err.message)
      return { success: false, data: {}, error: err.message }
    }
  })

  ipcMain.handle('save-config-yaml', async (_event, data: Record<string, any>): Promise<SaveResult> => {
    const config = getInstallConfig()
    if (!config.pmosPath) return { success: false, error: 'PM-OS path not configured' }
    try {
      writeConfigYaml(config.pmosPath, data)
      logInfo('settings', 'Config.yaml saved from settings panel')
      return { success: true }
    } catch (err: any) {
      logError('settings', `Failed to save config.yaml: ${err.message}`)
      logOutputError('ipc:save-config-yaml', err.message)
      return { success: false, error: err.message }
    }
  })

  ipcMain.handle('get-pmos-path', async () => {
    const config = getInstallConfig()
    return config.pmosPath
  })

  ipcMain.handle('set-pmos-path', async (_event, newPath: string): Promise<SaveResult> => {
    try {
      const detection = validateCustomPath(newPath)
      if (!detection.valid) {
        return { success: false, error: detection.missing?.length ? `Missing: ${detection.missing.join(', ')}` : 'Invalid PM-OS path' }
      }
      setInstallConfig({ pmosPath: newPath })
      // Also update the in-memory env path
      const envPath = path.join(newPath, 'user', '.env')
      if (existsSync(envPath)) {
        currentEnvPath = envPath
      }
      logInfo('settings', `PM-OS path updated to: ${newPath}`)
      return { success: true }
    } catch (err: any) {
      return { success: false, error: err.message }
    }
  })

  ipcMain.handle('get-env-values', async (_event, keys: string[]): Promise<Record<string, string>> => {
    if (!currentEnvPath) return {}
    try {
      const envFile = await parseEnvFile(currentEnvPath)
      return readAllEnvValues(envFile, keys)
    } catch {
      return {}
    }
  })

  // --- Homepage IPC handlers (v0.6) ---

  ipcMain.handle('get-daily-context', async (): Promise<DailyContextResult> => {
    const config = getInstallConfig()
    const devModeEnabled = isDevMode()

    if (devModeEnabled && !config.pmosPath) {
      return { success: true, data: getSyntheticContext(), devMode: true }
    }

    const pmosPath = config.pmosPath || path.join(process.env.HOME || '', 'pm-os')
    const contextDir = path.join(pmosPath, 'user', 'personal', 'context')
    const latestFile = findLatestContextFile(contextDir)

    if (!latestFile) {
      if (devModeEnabled) {
        return { success: true, data: getSyntheticContext(), devMode: true }
      }
      return { success: false, data: null, error: 'No daily context files found. Run a context update to generate one.' }
    }

    try {
      const userName = readUserName(pmosPath)
      const data = parseContextFile(latestFile, userName)
      return { success: true, data, devMode: devModeEnabled }
    } catch (err: any) {
      logError('homepage', `Failed to parse context: ${err.message}`)
      logOutputError('ipc:get-daily-context', err.message)
      if (devModeEnabled) {
        return { success: true, data: getSyntheticContext(), devMode: true }
      }
      return { success: false, data: null, error: err.message }
    }
  })

  // --- Brain IPC handlers (v0.5) ---

  ipcMain.handle('get-brain-health', async (): Promise<BrainHealthResult> => {
    const config = getInstallConfig()
    const devModeEnabled = isDevMode()

    if (devModeEnabled && !config.pmosPath) {
      return { success: true, data: getSyntheticBrainHealth(), devMode: true }
    }

    const pmosPath = config.pmosPath || path.join(process.env.HOME || '', 'pm-os')
    const brainPath = path.join(pmosPath, 'user', 'brain')

    if (!existsSync(brainPath)) {
      if (devModeEnabled) {
        return { success: true, data: getSyntheticBrainHealth(), devMode: true }
      }
      return { success: false, data: null, error: 'Brain folder not found' }
    }

    try {
      const data = await computeBrainHealth(pmosPath)
      return { success: true, data, devMode: devModeEnabled }
    } catch (err: any) {
      logError('brain', `Failed to compute brain health: ${err.message}`)
      logOutputError('ipc:get-brain-health', err.message)
      if (devModeEnabled) {
        return { success: true, data: getSyntheticBrainHealth(), devMode: true }
      }
      return { success: false, data: null, error: err.message }
    }
  })

  ipcMain.handle('open-brain-folder', async () => {
    const config = getInstallConfig()
    const pmosPath = config.pmosPath || path.join(process.env.HOME || '', 'pm-os')
    const brainPath = path.join(pmosPath, 'user', 'brain')

    if (!existsSync(brainPath)) {
      return { success: false, error: 'Brain folder not found' }
    }

    try {
      await shell.openPath(brainPath)
      return { success: true }
    } catch (err: any) {
      return { success: false, error: err.message }
    }
  })

  // --- CCE Hub IPC handlers (v0.7) ---

  ipcMain.handle('get-cce-projects', async (): Promise<CCEHubResult> => {
    const config = getInstallConfig()
    const devModeEnabled = isDevMode()

    if (devModeEnabled && !config.pmosPath) {
      return { success: true, data: getSyntheticCCEData(), devMode: true }
    }

    const pmosPath = config.pmosPath || path.join(process.env.HOME || '', 'pm-os')
    const productsPath = path.join(pmosPath, 'user', 'products')

    if (!existsSync(productsPath)) {
      if (devModeEnabled) {
        return { success: true, data: getSyntheticCCEData(), devMode: true }
      }
      return { success: false, data: null, error: 'Products folder not found. Ensure PM-OS is properly configured.' }
    }

    try {
      const data = await getCCEProjects(pmosPath)
      return { success: true, data, devMode: devModeEnabled }
    } catch (err: any) {
      logError('cce', `Failed to load CCE projects: ${err.message}`)
      logOutputError('ipc:get-cce-projects', err.message)
      if (devModeEnabled) {
        return { success: true, data: getSyntheticCCEData(), devMode: true }
      }
      return { success: false, data: null, error: err.message }
    }
  })

  ipcMain.handle('open-feature-folder', async (_event, featurePath: string) => {
    const config = getInstallConfig()
    const pmosPath = config.pmosPath || path.join(process.env.HOME || '', 'pm-os')
    const fullPath = path.join(pmosPath, 'user', 'products', featurePath)

    if (!existsSync(fullPath)) {
      return { success: false, error: 'Feature folder not found' }
    }

    try {
      await shell.openPath(fullPath)
      return { success: true }
    } catch (err: any) {
      return { success: false, error: err.message }
    }
  })

  // --- App Updater IPC handlers (v0.8) ---

  ipcMain.handle('get-app-version', (): AppVersionInfo => {
    return {
      version: app.getVersion(),
      electronVersion: process.versions.electron,
    }
  })

  ipcMain.handle('check-for-updates', async (): Promise<UpdateCheckResult> => {
    try {
      const { checkForUpdates } = await import('./updater/update-manager')
      const config = getInstallConfig()
      if (!config.pmosPath) {
        return { available: false, currentVersion: app.getVersion(), latestVersion: app.getVersion(), error: 'PM-OS path not configured' }
      }
      return checkForUpdates(config.pmosPath, app.getVersion())
    } catch (err: any) {
      logOutputError('ipc:check-for-updates', err.message)
      return { available: false, currentVersion: app.getVersion(), latestVersion: app.getVersion(), error: err.message }
    }
  })

  ipcMain.handle('start-update', async () => {
    try {
      const { performUpdate } = await import('./updater/update-manager')
      const config = getInstallConfig()
      if (!config.pmosPath) throw new Error('PM-OS path not configured')

      const windows = BrowserWindow.getAllWindows()
      const sendProgress = (status: string, percent: number, message: string) => {
        for (const win of windows) {
          if (!win.isDestroyed()) {
            win.webContents.send('update-progress', { status, percent, message })
          }
        }
      }

      await performUpdate(config.pmosPath, app.getVersion(), isDevMode(), sendProgress)
    } catch (err: any) {
      logOutputError('ipc:start-update', err.message)
      const windows = BrowserWindow.getAllWindows()
      for (const win of windows) {
        if (!win.isDestroyed()) {
          win.webContents.send('update-progress', { status: 'error', percent: 0, message: err.message })
        }
      }
    }
  })

  // --- Plugin IPC handlers (v0.11) ---

  ipcMain.handle('get-installed-plugins', async (): Promise<PluginInfo[]> => {
    const config = getInstallConfig()
    const pmosPath = config.pmosPath || path.join(process.env.HOME || '', 'pm-os')
    return getInstalledPlugins(pmosPath)
  })

  ipcMain.handle('get-available-plugins', async (): Promise<PluginInfo[]> => {
    const config = getInstallConfig()
    const pmosPath = config.pmosPath || path.join(process.env.HOME || '', 'pm-os')
    return getAvailablePlugins(pmosPath)
  })

  ipcMain.handle('install-plugin', async (_event, pluginId: string): Promise<PluginActionResult> => {
    const config = getInstallConfig()
    if (!config.pmosPath) return { success: false, pluginId, action: 'install', error: 'PM-OS path not configured' }
    logInfo('plugins', `Installing plugin: ${pluginId}`)
    const result = installPlugin(config.pmosPath, pluginId)
    if (result.success) {
      logInfo('plugins', `Plugin installed: ${pluginId}`)
    } else {
      logError('plugins', `Plugin install failed: ${pluginId} — ${result.error}`)
    }
    return result
  })

  ipcMain.handle('disable-plugin', async (_event, pluginId: string): Promise<PluginActionResult> => {
    const config = getInstallConfig()
    if (!config.pmosPath) return { success: false, pluginId, action: 'disable', error: 'PM-OS path not configured' }
    logInfo('plugins', `Disabling plugin: ${pluginId}`)
    const result = disablePlugin(config.pmosPath, pluginId)
    if (result.success) {
      logInfo('plugins', `Plugin disabled: ${pluginId}`)
    } else {
      logError('plugins', `Plugin disable failed: ${pluginId} — ${result.error}`)
    }
    return result
  })

  ipcMain.handle('get-plugin-health', async (_event, pluginId: string): Promise<PluginHealth> => {
    const config = getInstallConfig()
    const pmosPath = config.pmosPath || path.join(process.env.HOME || '', 'pm-os')
    return getPluginHealth(pmosPath, pluginId)
  })

  // --- Migration IPC handlers (v0.11) ---

  ipcMain.handle('detect-v4-installation', async () => {
    const config = getInstallConfig()
    if (!config.pmosPath) return { isV4: false }
    return detectV4Installation(config.pmosPath)
  })

  ipcMain.handle('start-migration', async () => {
    const config = getInstallConfig()
    if (!config.pmosPath) throw new Error('PM-OS path not configured')
    logInfo('migration', 'Starting v4→v5 migration')
    startMigration(config.pmosPath)
  })

  ipcMain.handle('rollback-migration', async () => {
    const config = getInstallConfig()
    if (!config.pmosPath) return { success: false, error: 'PM-OS path not configured' }
    logInfo('migration', 'Rolling back migration')
    return rollbackMigration(config.pmosPath)
  })

  // --- Telemetry IPC handlers (v0.10) ---

  ipcMain.handle('get-diagnostic-bundle', async () => {
    try {
      const data = await buildDiagnosticBundle()
      return { success: true, data }
    } catch (err: any) {
      return { success: false, data: '', error: err.message }
    }
  })

  ipcMain.on('log-telemetry-click', (_event, target: string) => {
    logClick(target)
  })

  ipcMain.handle('trigger-google-oauth', async () => {
    try {
      const config = getInstallConfig()
      if (!config.pmosPath) {
        return { success: false, error: 'PM-OS path not configured' }
      }
      const pmosPath = config.pmosPath!
      const venvPython = path.join(pmosPath, '.venv', 'bin', 'python3')
      const pythonBin = existsSync(venvPython) ? venvPython : 'python3'

      // PYTHONPATH must include the pm_os package source so `from pm_os.google_auth` resolves
      const packageSrc = path.join(pmosPath, 'common', 'package', 'src')
      const toolsPath = path.join(pmosPath, 'common', 'tools')
      const pythonPath = [packageSrc, toolsPath, process.env.PYTHONPATH || ''].filter(Boolean).join(':')

      const credsPath = path.join(pmosPath, 'user', '.secrets', 'credentials.json')
      const tokenPath = path.join(pmosPath, 'user', '.secrets', 'token.json')

      const script = [
        'from pathlib import Path',
        'from pm_os.google_auth import run_oauth_flow',
        `run_oauth_flow(Path("${credsPath}"), Path("${tokenPath}"))`,
      ].join('; ')

      const { execFile } = await import('child_process')
      return new Promise<{ success: boolean; error?: string }>((resolve) => {
        execFile(pythonBin, ['-c', script], {
          timeout: 120000,
          env: { ...process.env, PM_OS_ROOT: pmosPath, PYTHONPATH: pythonPath },
          cwd: pmosPath,
        }, (err) => {
          if (err) {
            logError('onboarding', `Google OAuth failed: ${err.message}`)
            logOutputError('ipc:trigger-google-oauth', err.message)
            resolve({ success: false, error: err.message })
          } else {
            logInfo('onboarding', 'Google OAuth completed')
            resolve({ success: true })
          }
        })
      })
    } catch (err: any) {
      return { success: false, error: err.message }
    }
  })
}
