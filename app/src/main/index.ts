// Suppress EPIPE crashes — Electron's stdout pipe can break when launched from certain terminals
process.on('uncaughtException', (err) => {
  if (err.message === 'write EPIPE') return
  throw err
})
process.stdout?.on?.('error', () => {})
process.stderr?.on?.('error', () => {})

import { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, dialog } from 'electron'
import path from 'path'
import { showSplashThenMain, showOnboardingSplash, splashShowPreInstallCheck, splashShowPrompt, splashShowPathInput, splashShowPathError, splashShowSuccess, splashShowError } from './splash'
import { registerIpcHandlers, setEnvPathInternal, getEnvPathInternal } from './ipc-handlers'
import { detectPmosPath } from './env/path-detector'
import { migrateGithubToken } from './env/env-manager'
import { startHealthPolling } from './connections/scheduler'
import { checkConnection } from './connections/health-checker'
import { parseEnvFile, readAllEnvValues } from './env/env-manager'
import { getAllEnvKeys, CONNECTION_CONFIGS } from '../shared/connection-configs'
import { detectPmosInstallation, validateCustomPath } from './installer/detection'
import { getInstallConfig, setInstallConfig } from './installer/config-store'
import { isDevMode, cleanupDevInstall, ensureDevDirs } from './installer/dev-mode'
import { runInstallation } from './installer/orchestrator'
import { ensureVenv } from './installer/venv-ensure'
import { logInfo, logError } from './installer/logger'
import { logSessionStart, logMachineInfo, logPmosVersion, cleanupOldTelemetry } from './telemetry/telemetry-logger'
import type { HealthStatus } from '../shared/types'

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let stopPolling: (() => void) | null = null
let latestStatuses: HealthStatus[] = []

const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })

  function createMainWindow(): BrowserWindow {
    const iconPath = path.join(__dirname, '../../assets/icons/icon.png')
    mainWindow = new BrowserWindow({
      width: 1000,
      height: 700,
      minWidth: 800,
      minHeight: 600,
      show: false,
      icon: iconPath,
      webPreferences: {
        preload: path.join(__dirname, '../preload/preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
      },
    })

    if (process.env.ELECTRON_RENDERER_URL) {
      mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
    } else {
      mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
    }

    // Hide to tray instead of closing
    mainWindow.on('close', (event) => {
      if (!app.isQuitting) {
        event.preventDefault()
        mainWindow?.hide()
      }
    })

    mainWindow.on('closed', () => {
      mainWindow = null
    })

    return mainWindow
  }

  function createTray() {
    const trayIconPath = path.join(__dirname, '../../assets/icons/tray-icon.png')
    const trayIcon = nativeImage.createFromPath(trayIconPath)
    trayIcon.setTemplateImage(true)
    tray = new Tray(trayIcon)
    tray.setToolTip('PM-OS')
    updateTrayMenu()

    tray.on('click', () => {
      if (mainWindow) {
        mainWindow.show()
        mainWindow.focus()
      }
    })
  }

  function updateTrayMenu() {
    if (!tray) return

    const healthy = latestStatuses.filter((s) => s.status === 'healthy').length
    const configured = latestStatuses.filter((s) => s.status !== 'unknown').length
    const tooltipText = configured > 0 ? `PM-OS — ${healthy}/${configured} connections healthy` : 'PM-OS'
    tray.setToolTip(tooltipText)

    const statusItems: Electron.MenuItemConstructorOptions[] = latestStatuses
      .filter((s) => s.status !== 'unknown')
      .map((s) => {
        const config = CONNECTION_CONFIGS.find((c) => c.id === s.connectionId)
        const icon = s.status === 'healthy' ? '✓' : '✗'
        return { label: `${icon} ${config?.name || s.connectionId}`, enabled: false }
      })

    const template: Electron.MenuItemConstructorOptions[] = [
      { label: 'Open PM-OS', click: () => { mainWindow?.show(); mainWindow?.focus() } },
      { type: 'separator' },
      ...(statusItems.length > 0 ? [...statusItems, { type: 'separator' as const }] : []),
      { label: 'Quit', click: () => { (app as any).isQuitting = true; app.quit() } },
    ]

    tray.setContextMenu(Menu.buildFromTemplate(template))
  }

  function onHealthUpdate(statuses: HealthStatus[]) {
    latestStatuses = statuses
    updateTrayMenu()
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('health-update', statuses)
    }
  }

  function loadOnboardingOrConnections(envPath: string) {
    const config = getInstallConfig()
    if (config.installComplete && !config.onboardingComplete) {
      // v0.2: onboarding mode — main window opens with onboarding wizard
      logInfo('app', 'Loading onboarding mode')
      setEnvPathInternal(envPath)
      const win = createMainWindow()
      win.once('ready-to-show', () => win.show())
      return
    }
    loadConnectionsManager(envPath)
  }

  function loadConnectionsManager(envPath: string) {
    setEnvPathInternal(envPath)
    const win = createMainWindow()
    win.once('ready-to-show', () => win.show())

    win.webContents.on('did-finish-load', () => {
      setTimeout(() => {
        stopPolling = startHealthPolling(envPath, onHealthUpdate)
      }, 1000)
    })
  }

  async function runOnboardingFlow(splash: BrowserWindow) {
    logInfo('app', 'Starting onboarding flow')

    // v0.9: Pre-installation checklist (first screen shown)
    await splashShowPreInstallCheck(splash)
    logInfo('app', 'Pre-installation checklist confirmed')

    // Ask: "Do you have PM-OS installed?"
    const answer = await splashShowPrompt(splash)
    logInfo('app', `User answered: "${answer}"`)

    if (answer === 'yes') {
      // "Yes, I have PM-OS" → ask for path (back button returns to prompt)
      let resolved = false
      while (!resolved) {
        const customPath = await splashShowPathInput(splash)

        // Back button sends __BACK__ sentinel — restart from prompt
        if (customPath === '__BACK__') {
          return runOnboardingFlow(splash)
        }

        const detection = validateCustomPath(customPath)

        if (detection.valid) {
          const envPath = path.join(customPath, 'user', '.env')
          setInstallConfig({ pmosPath: customPath, installComplete: true, installedAt: new Date().toISOString() })
          ensureVenv(customPath).catch((err) => logError('app', `Venv ensure failed: ${err.message}`))
          loadOnboardingOrConnections(envPath)
          await new Promise((r) => setTimeout(r, 300))
          splash.destroy()
          if (mainWindow) mainWindow.focus()
          await migrateGithubToken(envPath)
          resolved = true
        } else if (detection.found) {
          splashShowPathError(splash, `Partial installation — missing: ${detection.missing.join(', ')}`)
        } else {
          splashShowPathError(splash, 'PM-OS not found at this path')
        }
      }
    } else {
      // "No, I don't have PM-OS" → run full installation
      logInfo('app', 'User chose to install PM-OS')
      if (isDevMode()) ensureDevDirs()

      const result = await runInstallation(splash)

      if (result.success) {
        // Success animation already shown by orchestrator
        // Wait for animation then transition to onboarding
        await new Promise((r) => setTimeout(r, 3000))
        const envPath = path.join(result.pmosPath, 'user', '.env')
        try {
          loadOnboardingOrConnections(envPath)
        } catch (err: any) {
          logError('app', `Failed to load onboarding: ${err.message}`)
        }
        // Always destroy splash — even if onboarding load fails
        try { if (!splash.isDestroyed()) splash.destroy() } catch {}
        if (mainWindow) mainWindow.focus()
      } else {
        // Error already shown by orchestrator — wait for retry/quit
        const action = await splashShowError(splash, result.errors.join('\n'))
        if (action === 'retry') {
          // Retry installation
          const retryResult = await runInstallation(splash)
          if (retryResult.success) {
            await new Promise((r) => setTimeout(r, 3000))
            const envPath = path.join(retryResult.pmosPath, 'user', '.env')
            loadOnboardingOrConnections(envPath)
            splash.destroy()
          } else {
            // Failed again — quit
            ;(app as any).isQuitting = true
            app.quit()
          }
        } else {
          ;(app as any).isQuitting = true
          app.quit()
        }
      }
    }
  }

  app.whenReady().then(async () => {
    // Set dock icon in dev mode (production uses .icns from electron-builder)
    if (process.platform === 'darwin') {
      const dockIcon = nativeImage.createFromPath(path.join(__dirname, '../../assets/icons/icon.png'))
      if (!dockIcon.isEmpty()) app.dock?.setIcon(dockIcon)
    }

    registerIpcHandlers()
    createTray()

    // v0.10: Telemetry startup
    cleanupOldTelemetry()
    logSessionStart(app.getVersion(), process.versions.electron)
    logMachineInfo()
    const startupConfig = getInstallConfig()
    if (startupConfig.pmosPath) logPmosVersion(startupConfig.pmosPath)

    ipcMain.on('hide-window', () => { mainWindow?.hide() })
    ipcMain.on('quit-app', () => { (app as any).isQuitting = true; app.quit() })

    // Wire test-connection to actual health checker
    ipcMain.removeHandler('test-connection')
    ipcMain.handle('test-connection', async (_event, id: string) => {
      const envPath = getEnvPathInternal()
      if (!envPath) return { success: false, message: 'No .env configured' }
      const envFile = await parseEnvFile(envPath)
      const allValues = readAllEnvValues(envFile, getAllEnvKeys())
      const fields: Record<string, string> = {}
      const config = CONNECTION_CONFIGS.find((c) => c.id === id)
      if (config) {
        for (const f of config.fields) fields[f.envKey] = allValues[f.envKey] || ''
      }
      const basePath = path.dirname(envPath)
      const status = await checkConnection(id, fields, basePath)
      latestStatuses = latestStatuses.map((s) => s.connectionId === id ? status : s)
      if (latestStatuses.every((s) => s.connectionId !== id)) latestStatuses.push(status)
      onHealthUpdate(latestStatuses)
      return { success: status.status === 'healthy', message: status.message || '' }
    })

    // Wire start-installation IPC (for renderer-driven install)
    ipcMain.handle('start-installation', async () => {
      logInfo('app', 'Installation triggered via IPC')
      const result = await runInstallation(null, {
        onProgress: (step, total, name, pct, steps) => {
          mainWindow?.webContents.send('install-progress', { step, total, currentStep: steps[step - 1], steps, overallPct: pct })
        },
        onComplete: (result) => {
          mainWindow?.webContents.send('install-complete', result)
        },
      })
      return result
    })

    const skipSplash = process.env.SKIP_SPLASH === 'true'

    if (skipSplash) {
      // Skip splash — detect and go straight
      const testEnvPath = process.env.PMOS_TEST_ENV_PATH
      if (testEnvPath) {
        loadConnectionsManager(testEnvPath)
      } else {
        const detection = detectPmosInstallation()
        if (detection.valid && detection.path) {
          const envPath = path.join(detection.path, 'user', '.env')
          loadConnectionsManager(envPath)
        } else {
          const win = createMainWindow()
          win.show()
        }
      }
    } else {
      // Normal flow: splash → detect → onboarding or connections
      const testEnvPath = process.env.PMOS_TEST_ENV_PATH

      if (testEnvPath) {
        // Test override: splash → connections
        showSplashThenMain(() => {
          const win = createMainWindow()
          setEnvPathInternal(testEnvPath)
          return win
        })
        const envPath = testEnvPath
        if (mainWindow) {
          mainWindow.webContents.on('did-finish-load', () => {
            setTimeout(() => { stopPolling = startHealthPolling(envPath, onHealthUpdate) }, 1000)
          })
        }
      } else {
        // Detect PM-OS
        const detection = detectPmosInstallation()

        if (detection.valid && detection.path) {
          // PM-OS found — normal splash → connections manager
          logInfo('app', `PM-OS found at ${detection.path}`)
          const envPath = path.join(detection.path, 'user', '.env')
          await migrateGithubToken(envPath)

          // Ensure Python venv + deps exist (non-blocking for existing installs)
          ensureVenv(detection.path).catch((err) => logError('app', `Venv ensure failed: ${err.message}`))

          showSplashThenMain(() => {
            setEnvPathInternal(envPath)
            const win = createMainWindow()
            return win
          })

          // Start health polling after main window loads
          if (mainWindow) {
            mainWindow.webContents.on('did-finish-load', () => {
              setTimeout(() => { stopPolling = startHealthPolling(envPath, onHealthUpdate) }, 1000)
            })
          }
        } else {
          // PM-OS not found — onboarding flow
          logInfo('app', 'PM-OS not found — starting onboarding')
          const splash = showOnboardingSplash()
          runOnboardingFlow(splash)
        }
      }
    }
  })

  app.on('before-quit', async () => {
    (app as any).isQuitting = true
    if (stopPolling) stopPolling()

    // Dev mode cleanup prompt
    if (isDevMode()) {
      const { response } = await dialog.showMessageBox({
        type: 'question',
        buttons: ['Yes', 'No'],
        defaultId: 0,
        title: 'Dev Mode Cleanup',
        message: 'Clean up dev installation?',
        detail: 'This will delete the temporary PM-OS directory.',
      })
      if (response === 0) {
        cleanupDevInstall()
      }
    }
  })

  app.on('window-all-closed', () => {
    // Don't quit on macOS — keep tray alive
  })

  app.on('activate', () => {
    if (mainWindow) {
      mainWindow.show()
    } else {
      const win = createMainWindow()
      win.show()
    }
  })
}
