import { BrowserWindow } from 'electron'
import path from 'path'
import { existsSync } from 'fs'
import { detectPmosPath } from './env/path-detector'
import { isDevMode } from './installer/dev-mode'
import type { InstallStep } from '../shared/types'

function updateCheck(splash: BrowserWindow, id: string, status: 'running' | 'done' | 'fail') {
  if (splash.isDestroyed()) return
  splash.webContents.executeJavaScript(`window.updateCheck('${id}', '${status}')`)
}

async function runPreflightChecks(splash: BrowserWindow): Promise<void> {
  updateCheck(splash, 'env', 'running')
  try {
    const candidates = await detectPmosPath()
    if (candidates.length === 0) {
      updateCheck(splash, 'env', 'fail')
      return
    }
    updateCheck(splash, 'env', 'done')
    const pmosRoot = path.dirname(path.dirname(candidates[0]))

    updateCheck(splash, 'brain', 'running')
    const brainPath = path.join(pmosRoot, 'user', 'brain', 'BRAIN.md')
    updateCheck(splash, 'brain', existsSync(brainPath) ? 'done' : 'fail')

    updateCheck(splash, 'connections', 'running')
    updateCheck(splash, 'connections', existsSync(candidates[0]) ? 'done' : 'fail')

    updateCheck(splash, 'session', 'running')
    const sessionTool = path.join(pmosRoot, 'common', 'tools', 'session', 'session_manager.py')
    if (existsSync(sessionTool)) {
      const { execFile } = await import('child_process')
      // Use venv python if available — bare 'python3' isn't on PATH in packaged Electron apps
      const venvPython = path.join(pmosRoot, '.venv', 'bin', 'python3')
      const pythonBin = existsSync(venvPython) ? venvPython : '/usr/bin/python3'
      await new Promise<void>((resolve) => {
        execFile(pythonBin, [sessionTool, '--status'], { timeout: 5000, env: { ...process.env, PM_OS_ROOT: pmosRoot } }, (err) => {
          updateCheck(splash, 'session', err ? 'fail' : 'done')
          resolve()
        })
      })
    } else {
      updateCheck(splash, 'session', 'fail')
    }

    updateCheck(splash, 'health', 'running')
    await new Promise((r) => setTimeout(r, 200))
    updateCheck(splash, 'health', 'done')
  } catch {
    // Non-blocking
  }
}

export function createSplashWindow(): BrowserWindow {
  const splash = new BrowserWindow({
    width: 600,
    height: 400,
    frame: false,
    alwaysOnTop: true,
    center: true,
    resizable: false,
    skipTaskbar: true,
    transparent: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: false, // needed for executeJavaScript to set window APIs
    },
  })

  splash.loadFile(path.join(__dirname, '../../splash/index.html'))

  return splash
}

// v0 flow: splash with preflight → main window after timeout
export function showSplashThenMain(
  createMainWindow: () => BrowserWindow,
  splashDuration: number = 4000,
): void {
  const splash = createSplashWindow()

  splash.webContents.on('did-finish-load', () => {
    runPreflightChecks(splash)
  })

  const mainWindow = createMainWindow()
  mainWindow.hide()

  setTimeout(() => {
    mainWindow.show()
    splash.destroy()
  }, splashDuration)
}

// v0.1 flow: splash stays open for onboarding
export function showOnboardingSplash(): BrowserWindow {
  const splash = createSplashWindow()

  splash.webContents.on('did-finish-load', () => {
    if (isDevMode()) {
      splash.webContents.executeJavaScript('window.setDevMode(true)')
    }
  })

  return splash
}

// v0.9: Pre-installation checklist
export function splashShowPreInstallCheck(splash: BrowserWindow): Promise<void> {
  return new Promise(async (resolve) => {
    await splash.webContents.executeJavaScript(`
      document.title = 'IDLE';
      window.showPreInstallCheck(function() {
        document.title = 'PRECHECK:continue';
      });
    `)
    const handler = (_event: Electron.Event, title: string) => {
      if (title === 'PRECHECK:continue') {
        splash.removeListener('page-title-updated', handler)
        resolve()
      }
    }
    splash.on('page-title-updated', handler)
  })
}

// Onboarding screen helpers — called from main process
export function splashShowPrompt(splash: BrowserWindow): Promise<'yes' | 'no'> {
  return new Promise(async (resolve) => {
    // Await executeJavaScript so stale title events from page load are ignored
    await splash.webContents.executeJavaScript(`
      document.title = 'IDLE';
      window.showPrompt(function(answer) {
        document.title = 'ANSWER:' + answer;
      });
    `)
    // Use event title parameter (not getTitle()) — getTitle() can lag behind the event
    const handler = (_event: Electron.Event, title: string) => {
      if (title.startsWith('ANSWER:')) {
        const answer = title.replace('ANSWER:', '') as 'yes' | 'no'
        splash.removeListener('page-title-updated', handler)
        resolve(answer)
      }
    }
    splash.on('page-title-updated', handler)
  })
}

export function splashShowPathInput(splash: BrowserWindow): Promise<string> {
  return new Promise(async (resolve) => {
    await splash.webContents.executeJavaScript(`
      document.title = 'IDLE';
      window.showPathInput(function(path) {
        document.title = 'PATH:' + path;
      });
    `)
    // Use event title parameter (not getTitle()) — getTitle() can lag behind the event
    const handler = (_event: Electron.Event, title: string) => {
      if (title.startsWith('PATH:')) {
        splash.removeListener('page-title-updated', handler)
        resolve(title.replace('PATH:', ''))
      }
    }
    splash.on('page-title-updated', handler)
  })
}

export function splashShowPathError(splash: BrowserWindow, message: string): void {
  if (splash.isDestroyed()) return
  const escaped = message.replace(/'/g, "\\'")
  splash.webContents.executeJavaScript(`window.showPathError('${escaped}')`)
}

export function splashShowProgress(splash: BrowserWindow): void {
  if (splash.isDestroyed()) return
  splash.webContents.executeJavaScript('window.showProgress()')
}

export function splashUpdateProgress(splash: BrowserWindow, stepName: string, pct: number, steps: InstallStep[]): void {
  if (splash.isDestroyed()) return
  const stepsJson = JSON.stringify(steps)
  splash.webContents.executeJavaScript(`window.updateProgress('${stepName.replace(/'/g, "\\'")}', ${pct}, ${stepsJson})`)
}

export function splashShowSuccess(splash: BrowserWindow): void {
  if (splash.isDestroyed()) return
  splash.webContents.executeJavaScript('window.showSuccess()')
}

export function splashShowError(splash: BrowserWindow, errorText: string): Promise<'retry' | 'quit'> {
  return new Promise(async (resolve) => {
    const escaped = errorText.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n')
    await splash.webContents.executeJavaScript(`
      document.title = 'IDLE';
      window.showError('${escaped}', function() {
        document.title = 'ACTION:retry';
      }, function() {
        document.title = 'ACTION:quit';
      });
    `)
    // Use event title parameter (not getTitle()) — getTitle() can lag behind the event
    const handler = (_event: Electron.Event, title: string) => {
      if (title.startsWith('ACTION:')) {
        splash.removeListener('page-title-updated', handler)
        resolve(title.replace('ACTION:', '') as 'retry' | 'quit')
      }
    }
    splash.on('page-title-updated', handler)
  })
}
