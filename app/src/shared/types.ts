export interface ConnectionConfig {
  id: string
  name: string
  icon: string
  brandColor: string
  linkedTo?: string
  fields: FieldConfig[]
  helpText: string
  testEndpoint: {
    method: 'GET' | 'POST'
    urlTemplate: string
    headers: Record<string, string>
    authType: 'basic' | 'bearer' | 'file-check'
  }
}

export interface FieldConfig {
  envKey: string
  label: string
  type: 'text' | 'password' | 'path'
  required: boolean
  placeholder?: string
  autoPopulated?: boolean
  confirmBeforeEdit?: string
}

export interface ConnectionState {
  id: string
  name: string
  icon: string
  brandColor: string
  active: boolean
  fields: Record<string, string>
  health: HealthStatus
}

export interface HealthStatus {
  connectionId: string
  status: 'healthy' | 'unhealthy' | 'unknown' | 'checking'
  message?: string
  lastChecked?: number
}

export interface SaveResult {
  success: boolean
  error?: string
}

export interface TestResult {
  success: boolean
  message: string
  statusCode?: number
}

// --- Installer types (v0.1) ---

export interface InstallConfig {
  pmosPath: string | null
  installComplete: boolean
  installedAt: string | null
  version: string
  devMode: boolean
}

export interface DetectionResult {
  found: boolean
  path: string | null
  valid: boolean
  missing: string[]
}

export interface InstallStep {
  id: string
  name: string
  status: 'pending' | 'running' | 'done' | 'error'
  pct: number
  message?: string
}

export interface InstallProgress {
  step: number
  total: number
  currentStep: InstallStep
  steps: InstallStep[]
  overallPct: number
}

export interface InstallResult {
  success: boolean
  errors: string[]
  duration: number
  pmosPath: string
}

export interface VerifyCheck {
  name: string
  category: 'structure' | 'config' | 'python' | 'tools' | 'commands' | 'integrations'
  passed: boolean
  message: string
  duration: number
}

export interface VerifyResult {
  success: boolean
  checks: VerifyCheck[]
  duration: number
}

// --- Onboarding types (v0.2) ---

export type AppMode = 'onboarding' | 'user-setup' | 'connections'

export interface OnboardingState {
  currentStep: number
  totalSteps: number
  completedSteps: string[]
  skippedSteps: string[]
}

export interface OnboardingStepConfig {
  id: string
  title: string
  connectionIds: string[]
  authOptions: Array<{ id: string; label: string; enabled: boolean }>
}

// --- User Setup types (v0.3) ---

export type UserSetupStepId = 'profile' | 'atlassian' | 'github-slack' | 'gdrive' | 'brain' | 'org-people' | 'success'

export interface ConfigValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

// --- Brain Health types (v0.5) ---

export type HealthIndicator = 'green' | 'yellow' | 'red'

export interface BrainMetric {
  label: string
  value: number | string
  unit?: string
  target?: number
  indicator: HealthIndicator
}

export interface OrphanBreakdown {
  reason: string
  count: number
}

export interface RelationshipTypeCount {
  type: string
  count: number
}

export interface BrainHealthData {
  // Core metrics
  connectivityRate: number        // % of entities with relationships
  entityCount: number
  medianRelationships: number
  graphComponents: number         // connected components count
  graphDiameter: number | null    // longest shortest path (null if disconnected)
  orphanCount: number
  orphanRate: number              // %
  orphansByReason: OrphanBreakdown[]
  staleEntityRate: number         // %
  enrichmentVelocity7d: number    // entities updated in last 7 days
  lastEnrichmentTimestamp: string | null
  densityScore: number            // 0-1

  // Distribution data
  relationshipTypes: RelationshipTypeCount[]
  entitiesByType: Record<string, number>

  // Targets (from config or defaults)
  targets: {
    connectivityRate: number      // default 85
    entityCount: number           // default 500
    medianRelationships: number   // default 3
    graphComponents: number       // default 1
    orphanRate: number            // default 10
    staleEntityRate: number       // default 15
    enrichmentVelocity7d: number  // default 10
  }
}

export interface BrainHealthResult {
  success: boolean
  data: BrainHealthData | null
  error?: string
  devMode?: boolean
}

// --- Homepage / Daily Context types (v0.6) ---

export interface MeetingItem {
  time: string
  event: string
}

export interface ActionItem {
  owner: string
  text: string
  group: string  // 'Today' | 'This Week' | 'This Sprint'
}

export interface AlertItem {
  priority: string  // 'P0' | 'P1'
  title: string
  description: string
}

export interface DailyContextData {
  date: string                    // YYYY-MM-DD
  generatedAt: string             // e.g. "2026-03-30 10:31 CET"
  userName: string
  meetings: MeetingItem[]
  actionItems: ActionItem[]
  alerts: AlertItem[]
}

export interface DailyContextResult {
  success: boolean
  data: DailyContextData | null
  error?: string
  devMode?: boolean
}

// --- CCE Hub types (v0.7) ---

export interface CCEFeatureAction {
  date: string
  action: string
  status: string
}

export interface CCEFeatureMeta {
  title: string
  status: string
  owner: string | null
  priority: string | null
  deadline: string | null
  lastUpdated: string | null
  description: string | null
  actionCount: number
  latestAction: CCEFeatureAction | null
}

export interface CCEFeature {
  id: string
  name: string
  path: string
  meta: CCEFeatureMeta
}

export interface CCEProductMeta {
  status: string | null
  owner: string | null
  type: string | null
  lastUpdated: string | null
}

export interface CCEProduct {
  id: string
  name: string
  org: string
  path: string
  meta: CCEProductMeta
  features: CCEFeature[]
  isWcrProduct: boolean
  wcrMeta?: { squad?: string; tribe?: string; market?: string }
}

export interface CCEHubData {
  generatedAt: string
  summary: { products: number; features: number; active: number }
  products: CCEProduct[]
}

export interface CCEHubResult {
  success: boolean
  data: CCEHubData | null
  error?: string
  devMode?: boolean
}

// --- App Updater types (v0.8) ---

export type UpdateStatus = 'idle' | 'checking' | 'update-available' | 'downloading' | 'verifying' | 'installing' | 'relaunching' | 'up-to-date' | 'error'

export interface UpdateManifest {
  version: string
  platform: {
    [os: string]: {
      url: string
      filename: string
      size: number
      sha256: string
    }
  }
  releaseNotes: string
  minPmosVersion: string
  publishedAt: string
}

export interface UpdateCheckResult {
  available: boolean
  currentVersion: string
  latestVersion: string
  releaseNotes?: string
  error?: string
}

export interface UpdateProgress {
  status: UpdateStatus
  percent: number
  message: string
}

export interface AppVersionInfo {
  version: string
  electronVersion: string
}

// --- Plugin types (v0.11) ---

export interface PluginInfo {
  id: string
  name: string
  version: string
  description: string
  author: string
  dependencies: string[]
  status: 'installed' | 'available' | 'disabled'
  commands: string[]
  skills: string[]
  mcpServers: string[]
  health?: PluginHealth
  requires?: { python?: string; config_keys?: string[] }
}

export interface PluginHealth {
  status: 'healthy' | 'degraded' | 'error' | 'unknown'
  message?: string
  metrics?: Record<string, string | number>
  lastChecked?: number
}

export interface PluginActionResult {
  success: boolean
  pluginId: string
  action: 'install' | 'disable' | 'enable'
  error?: string
}

// --- Migration types (v0.11) ---

export type MigrationStep =
  'analyzing' | 'confirming' | 'backing-up' |
  'migrating' | 'validating' | 'done' | 'error'

export interface MigrationProgress {
  step: MigrationStep
  percent: number
  message: string
  report?: {
    keepCount: number
    archiveCount: number
    deleteCount: number
    cleanupBytes: number
    pluginsToInstall: string[]
  }
}

export interface MigrationResult {
  success: boolean
  backupTag: string
  pluginsInstalled: string[]
  error?: string
}

// --- API ---

export interface PmosAPI {
  getEnvPath(): Promise<string | null>
  setEnvPath(path: string): Promise<void>
  detectPmosInstallation(): Promise<string[]>
  getConnections(): Promise<ConnectionState[]>
  saveConnection(id: string, fields: Record<string, string>): Promise<SaveResult>
  testConnection(id: string): Promise<TestResult>
  copyFromJira(targetId: string): Promise<Record<string, string>>
  onHealthUpdate(callback: (statuses: HealthStatus[]) => void): void
  removeHealthUpdateListener(): void
  hideWindow(): void
  quitApp(): void

  // Onboarding (v0.2)
  getAppMode(): Promise<AppMode>
  completeOnboarding(): Promise<void>
  isDevMode(): Promise<boolean>
  loadDevCredentials(): Promise<Record<string, string>>
  uploadGoogleCredentials(filePath: string): Promise<{ success: boolean; error?: string }>
  triggerGoogleOAuth(): Promise<{ success: boolean; error?: string }>
  onAppModeChanged(callback: (mode: AppMode) => void): void
  removeAppModeChangedListener(): void

  // User Setup (v0.3)
  saveUserSetupStep(stepId: string, data: Record<string, any>): Promise<SaveResult>
  loadDevConfig(): Promise<Record<string, any>>
  validateConfig(): Promise<ConfigValidationResult>
  completeUserSetup(): Promise<void>
  getEnvValues(keys: string[]): Promise<Record<string, string>>

  // Settings (v0.4)
  loadConfigYaml(): Promise<{ success: boolean; data: Record<string, any>; error?: string }>
  saveConfigYaml(data: Record<string, any>): Promise<SaveResult>
  getPmosPath(): Promise<string | null>
  setPmosPath(path: string): Promise<SaveResult>

  // Homepage (v0.6)
  getDailyContext(): Promise<DailyContextResult>

  // Brain (v0.5)
  getBrainHealth(): Promise<BrainHealthResult>
  openBrainFolder(): Promise<{ success: boolean; error?: string }>

  // CCE Hub (v0.7)
  getCCEProjects(): Promise<CCEHubResult>
  openFeatureFolder(featurePath: string): Promise<{ success: boolean; error?: string }>

  // Telemetry (v0.10)
  getDiagnosticBundle(): Promise<{ success: boolean; data: string; error?: string }>
  logTelemetryClick(target: string): void

  // App Updater (v0.8)
  getAppVersion(): Promise<AppVersionInfo>
  checkForUpdates(): Promise<UpdateCheckResult>
  startUpdate(): Promise<void>
  onUpdateProgress(callback: (progress: UpdateProgress) => void): void
  removeUpdateProgressListener(): void

  // Plugins (v0.11)
  getInstalledPlugins(): Promise<PluginInfo[]>
  getAvailablePlugins(): Promise<PluginInfo[]>
  installPlugin(pluginId: string): Promise<PluginActionResult>
  disablePlugin(pluginId: string): Promise<PluginActionResult>
  getPluginHealth(pluginId: string): Promise<PluginHealth>

  // Migration (v0.11)
  detectV4Installation(): Promise<{ isV4: boolean; path?: string }>
  startMigration(): Promise<void>
  onMigrationProgress(callback: (progress: MigrationProgress) => void): void
  removeMigrationProgressListener(): void
  rollbackMigration(): Promise<{ success: boolean; error?: string }>

  // Installer (v0.1)
  getInstallConfig(): Promise<InstallConfig>
  detectPmos(): Promise<DetectionResult>
  validatePath(path: string): Promise<DetectionResult>
  startInstallation(): Promise<void>
  onInstallProgress(callback: (progress: InstallProgress) => void): void
  removeInstallProgressListener(): void
  onInstallComplete(callback: (result: InstallResult) => void): void
  removeInstallCompleteListener(): void
  getRecentLogs(category: string, lines?: number): Promise<string>
}
