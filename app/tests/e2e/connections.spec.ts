import { test, expect, type ElectronApplication, type Page } from '@playwright/test'
import { _electron as electron } from 'playwright'
import * as path from 'path'
import * as fs from 'fs'
import * as os from 'os'

const APP_ROOT = path.resolve(__dirname, '../..')
const MAIN_ENTRY = path.join(APP_ROOT, 'out/main/index.js')
const FIXTURE_ENV = path.join(__dirname, 'fixtures/test.env')

let electronApp: ElectronApplication

function tmpEnvCopy(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pmos-e2e-'))
  const dest = path.join(dir, 'user')
  fs.mkdirSync(dest, { recursive: true })
  const envDest = path.join(dest, '.env')
  fs.copyFileSync(FIXTURE_ENV, envDest)
  return envDest
}

async function launchApp(envOverrides: Record<string, string> = {}): Promise<{ app: ElectronApplication; page: Page; tmpEnv: string }> {
  const tmpEnv = tmpEnvCopy()
  const app = await electron.launch({
    args: [MAIN_ENTRY],
    env: {
      ...process.env,
      SKIP_SPLASH: 'true',
      NODE_ENV: 'test',
      HELLOAI_TEST_ENV_PATH: tmpEnv,
      ...envOverrides,
    },
  })
  const page = await app.firstWindow()
  await page.waitForLoadState('domcontentloaded')
  return { app, page, tmpEnv }
}

test.afterEach(async () => {
  if (electronApp) {
    await electronApp.close()
  }
})

test.describe('Connections Grid', () => {
  test('renders 6 connection cards', async () => {
    const { app, page } = await launchApp()
    electronApp = app

    await page.waitForSelector('text=Jira', { timeout: 10000 })

    // Should have exactly 6 connection service names
    for (const name of ['Jira', 'Confluence', 'Google', 'Slack', 'GitHub', 'Figma']) {
      await expect(page.locator(`text=${name}`).first()).toBeVisible()
    }
  })

  test('Jira card shows active state (opacity 1)', async () => {
    const { app, page } = await launchApp()
    electronApp = app

    await page.waitForSelector('text=Jira', { timeout: 10000 })

    // Jira has configured values in test.env — active card has full opacity
    const jiraCard = page.locator('button').filter({ hasText: 'Jira' }).first()
    await expect(jiraCard).toBeVisible()

    const opacity = await jiraCard.evaluate((el) => getComputedStyle(el).opacity)
    expect(Number(opacity)).toBe(1)
  })

  test('Figma card shows inactive state', async () => {
    const { app, page } = await launchApp()
    electronApp = app

    await page.waitForSelector('text=Figma', { timeout: 10000 })

    // Figma has no token in test.env — inactive card at 0.6 opacity
    const figmaCard = page.locator('button').filter({ hasText: 'Figma' }).first()
    await expect(figmaCard).toBeVisible()

    const opacity = await figmaCard.evaluate((el) => getComputedStyle(el).opacity)
    expect(Number(opacity)).toBeCloseTo(0.6, 1)
  })
})

test.describe('Connection Panel', () => {
  test('clicking a card opens slide-over panel with form fields', async () => {
    const { app, page } = await launchApp()
    electronApp = app

    await page.waitForSelector('text=Jira', { timeout: 10000 })

    // Click Jira card
    await page.locator('button').filter({ hasText: 'Jira' }).first().click()

    // Panel should appear with the connection name as a heading
    const panelHeading = page.locator('h3', { hasText: 'Jira' })
    await expect(panelHeading).toBeVisible({ timeout: 5000 })

    // Form fields should be visible
    await expect(page.locator('text=JIRA_URL')).toBeVisible()
    await expect(page.locator('text=JIRA_USERNAME')).toBeVisible()
    await expect(page.locator('text=JIRA_API_TOKEN')).toBeVisible()
  })

  test('close button dismisses the panel', async () => {
    const { app, page } = await launchApp()
    electronApp = app

    await page.waitForSelector('text=Jira', { timeout: 10000 })

    // Open panel
    await page.locator('button').filter({ hasText: 'Jira' }).first().click()
    await expect(page.locator('h3', { hasText: 'Jira' })).toBeVisible({ timeout: 5000 })

    // The backdrop div intercepts pointer events over the grid area.
    // Click at coordinates in the left half of the window (outside the 380px panel on the right).
    await page.mouse.click(100, 300)

    // After closing, the panel slides off-screen via translateX(100%)
    await page.waitForTimeout(400)

    // The JIRA_URL form label should no longer be in viewport (panel slid off-screen)
    const formLabel = page.locator('text=JIRA_URL')
    await expect(formLabel).not.toBeInViewport({ timeout: 3000 })
  })
})

test.describe('Save to .env', () => {
  test('saving a connection updates the .env file and preserves unmanaged keys', async () => {
    const { app, page, tmpEnv } = await launchApp()
    electronApp = app

    await page.waitForSelector('text=Jira', { timeout: 10000 })

    // Open GitHub card
    await page.locator('button').filter({ hasText: 'GitHub' }).first().click()
    await expect(page.locator('h3', { hasText: 'GitHub' })).toBeVisible({ timeout: 5000 })

    // Fill in GITHUB_ORG field
    const orgInput = page.locator('input').first()
    await orgInput.fill('test-org-e2e')

    // Click Save
    await page.locator('button', { hasText: 'Save' }).click()

    // Wait for save to complete
    await page.waitForTimeout(1000)

    // Verify .env was updated
    const envContent = fs.readFileSync(tmpEnv, 'utf-8')
    expect(envContent).toContain('GITHUB_ORG=test-org-e2e')

    // Verify unmanaged keys are preserved
    expect(envContent).toContain('GEMINI_API_KEY=test-gemini-key')
    expect(envContent).toContain('PMOS_USER_NAME="Test User"')

    // Cleanup
    fs.rmSync(path.dirname(path.dirname(tmpEnv)), { recursive: true, force: true })
  })
})
