import Store from 'electron-store'

export interface InstallConfig {
  pmosPath: string | null
  installComplete: boolean
  installedAt: string | null
  version: string
  devMode: boolean
  onboardingComplete: boolean
  userSetupComplete: boolean
}

const defaults: InstallConfig = {
  pmosPath: null,
  installComplete: false,
  installedAt: null,
  version: '0.1.0',
  devMode: false,
  onboardingComplete: false,
  userSetupComplete: false,
}

const store = new Store<InstallConfig>({
  name: 'pmos-install',
  defaults,
})

export function getInstallConfig(): InstallConfig {
  return {
    pmosPath: store.get('pmosPath'),
    installComplete: store.get('installComplete'),
    installedAt: store.get('installedAt'),
    version: store.get('version'),
    devMode: store.get('devMode'),
    onboardingComplete: store.get('onboardingComplete', false),
    userSetupComplete: store.get('userSetupComplete', false),
  }
}

export function setInstallConfig(config: Partial<InstallConfig>): void {
  for (const [key, value] of Object.entries(config)) {
    store.set(key as keyof InstallConfig, value)
  }
}

export function resetInstallConfig(): void {
  store.clear()
}
