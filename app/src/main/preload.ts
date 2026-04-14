import { contextBridge, ipcRenderer } from 'electron'
import type { PmosAPI } from '../shared/types'

const api: PmosAPI = {
  getEnvPath: () => ipcRenderer.invoke('get-env-path'),
  setEnvPath: (path) => ipcRenderer.invoke('set-env-path', path),
  detectPmosInstallation: () => ipcRenderer.invoke('detect-pmos'),
  getConnections: () => ipcRenderer.invoke('get-connections'),
  saveConnection: (id, fields) => ipcRenderer.invoke('save-connection', id, fields),
  testConnection: (id) => ipcRenderer.invoke('test-connection', id),
  copyFromJira: (targetId) => ipcRenderer.invoke('copy-from-jira', targetId),
  onHealthUpdate: (callback) => {
    ipcRenderer.on('health-update', (_event, statuses) => callback(statuses))
  },
  removeHealthUpdateListener: () => {
    ipcRenderer.removeAllListeners('health-update')
  },
  hideWindow: () => ipcRenderer.send('hide-window'),
  quitApp: () => ipcRenderer.send('quit-app'),

  // Onboarding (v0.2)
  getAppMode: () => ipcRenderer.invoke('get-app-mode'),
  completeOnboarding: () => ipcRenderer.invoke('complete-onboarding'),
  isDevMode: () => ipcRenderer.invoke('is-dev-mode'),
  loadDevCredentials: () => ipcRenderer.invoke('load-dev-credentials'),
  uploadGoogleCredentials: (filePath: string) => ipcRenderer.invoke('upload-google-credentials', filePath),
  triggerGoogleOAuth: () => ipcRenderer.invoke('trigger-google-oauth'),
  onAppModeChanged: (callback: (mode: string) => void) => {
    ipcRenderer.on('app-mode-changed', (_event, mode) => callback(mode))
  },
  removeAppModeChangedListener: () => {
    ipcRenderer.removeAllListeners('app-mode-changed')
  },

  // User Setup (v0.3)
  saveUserSetupStep: (stepId: string, data: Record<string, any>) => ipcRenderer.invoke('save-user-setup-step', stepId, data),
  loadDevConfig: () => ipcRenderer.invoke('load-dev-config'),
  validateConfig: () => ipcRenderer.invoke('validate-config'),
  completeUserSetup: () => ipcRenderer.invoke('complete-user-setup'),
  getEnvValues: (keys: string[]) => ipcRenderer.invoke('get-env-values', keys),

  // Settings (v0.4)
  loadConfigYaml: () => ipcRenderer.invoke('load-config-yaml'),
  saveConfigYaml: (data: Record<string, any>) => ipcRenderer.invoke('save-config-yaml', data),
  getPmosPath: () => ipcRenderer.invoke('get-pmos-path'),
  setPmosPath: (path: string) => ipcRenderer.invoke('set-pmos-path', path),

  // Homepage (v0.6)
  getDailyContext: () => ipcRenderer.invoke('get-daily-context'),

  // Brain (v0.5)
  getBrainHealth: () => ipcRenderer.invoke('get-brain-health'),
  openBrainFolder: () => ipcRenderer.invoke('open-brain-folder'),

  // CCE Hub (v0.7)
  getCCEProjects: () => ipcRenderer.invoke('get-cce-projects'),
  openFeatureFolder: (featurePath: string) => ipcRenderer.invoke('open-feature-folder', featurePath),

  // Telemetry (v0.10)
  getDiagnosticBundle: () => ipcRenderer.invoke('get-diagnostic-bundle'),
  logTelemetryClick: (target: string) => ipcRenderer.send('log-telemetry-click', target),

  // App Updater (v0.8)
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  startUpdate: () => ipcRenderer.invoke('start-update'),
  onUpdateProgress: (callback: (progress: any) => void) => {
    ipcRenderer.on('update-progress', (_event, progress) => callback(progress))
  },
  removeUpdateProgressListener: () => {
    ipcRenderer.removeAllListeners('update-progress')
  },

  // Plugins (v0.11)
  getInstalledPlugins: () => ipcRenderer.invoke('get-installed-plugins'),
  getAvailablePlugins: () => ipcRenderer.invoke('get-available-plugins'),
  installPlugin: (pluginId: string) => ipcRenderer.invoke('install-plugin', pluginId),
  disablePlugin: (pluginId: string) => ipcRenderer.invoke('disable-plugin', pluginId),
  getPluginHealth: (pluginId: string) => ipcRenderer.invoke('get-plugin-health', pluginId),

  // Migration (v0.11)
  detectV4Installation: () => ipcRenderer.invoke('detect-v4-installation'),
  startMigration: () => ipcRenderer.invoke('start-migration'),
  onMigrationProgress: (callback: (progress: any) => void) => {
    ipcRenderer.on('migration-progress', (_event, progress) => callback(progress))
  },
  removeMigrationProgressListener: () => {
    ipcRenderer.removeAllListeners('migration-progress')
  },
  rollbackMigration: () => ipcRenderer.invoke('rollback-migration'),

  // Installer (v0.1)
  getInstallConfig: () => ipcRenderer.invoke('get-install-config'),
  detectPmos: () => ipcRenderer.invoke('detect-pmos-install'),
  validatePath: (path) => ipcRenderer.invoke('validate-pmos-path', path),
  startInstallation: () => ipcRenderer.invoke('start-installation'),
  onInstallProgress: (callback) => {
    ipcRenderer.on('install-progress', (_event, progress) => callback(progress))
  },
  removeInstallProgressListener: () => {
    ipcRenderer.removeAllListeners('install-progress')
  },
  onInstallComplete: (callback) => {
    ipcRenderer.on('install-complete', (_event, result) => callback(result))
  },
  removeInstallCompleteListener: () => {
    ipcRenderer.removeAllListeners('install-complete')
  },
  getRecentLogs: (category, lines) => ipcRenderer.invoke('get-recent-logs', category, lines),
}

contextBridge.exposeInMainWorld('api', api)
