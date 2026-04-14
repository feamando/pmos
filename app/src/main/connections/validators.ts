import fs from 'fs'
import type { TestResult } from '../../shared/types'

const TIMEOUT_MS = 10_000

async function fetchWithTimeout(url: string, options: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

export async function validateJira(fields: Record<string, string>): Promise<TestResult> {
  const { JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN } = fields
  if (!JIRA_URL || !JIRA_USERNAME || !JIRA_API_TOKEN) {
    return { success: false, message: 'Missing required fields' }
  }
  try {
    const url = `${JIRA_URL.replace(/\/$/, '')}/rest/api/2/myself`
    const auth = Buffer.from(`${JIRA_USERNAME}:${JIRA_API_TOKEN}`).toString('base64')
    const res = await fetchWithTimeout(url, { headers: { Authorization: `Basic ${auth}` } })
    if (res.ok) return { success: true, message: 'Connected', statusCode: res.status }
    return { success: false, message: `${res.status} ${res.statusText}`, statusCode: res.status }
  } catch (err: any) {
    if (err.name === 'AbortError') return { success: false, message: 'Connection timeout' }
    return { success: false, message: err.message }
  }
}

export async function validateConfluence(fields: Record<string, string>): Promise<TestResult> {
  const { JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN } = fields
  if (!JIRA_URL || !JIRA_USERNAME || !JIRA_API_TOKEN) {
    return { success: false, message: 'Missing required fields' }
  }
  try {
    const url = `${JIRA_URL.replace(/\/$/, '')}/wiki/rest/api/space?limit=1`
    const auth = Buffer.from(`${JIRA_USERNAME}:${JIRA_API_TOKEN}`).toString('base64')
    const res = await fetchWithTimeout(url, { headers: { Authorization: `Basic ${auth}` } })
    if (res.ok) return { success: true, message: 'Connected', statusCode: res.status }
    return { success: false, message: `${res.status} ${res.statusText}`, statusCode: res.status }
  } catch (err: any) {
    if (err.name === 'AbortError') return { success: false, message: 'Connection timeout' }
    return { success: false, message: err.message }
  }
}

export async function validateGoogle(fields: Record<string, string>, basePath: string): Promise<TestResult> {
  const { GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH } = fields
  if (!GOOGLE_CREDENTIALS_PATH || !GOOGLE_TOKEN_PATH) {
    return { success: false, message: 'Missing required fields' }
  }
  try {
    const credPath = GOOGLE_CREDENTIALS_PATH.startsWith('/') ? GOOGLE_CREDENTIALS_PATH : `${basePath}/${GOOGLE_CREDENTIALS_PATH}`
    const tokenPath = GOOGLE_TOKEN_PATH.startsWith('/') ? GOOGLE_TOKEN_PATH : `${basePath}/${GOOGLE_TOKEN_PATH}`

    if (!fs.existsSync(credPath)) return { success: false, message: `Credentials file not found: ${GOOGLE_CREDENTIALS_PATH}` }
    if (!fs.existsSync(tokenPath)) return { success: false, message: `Token file not found: ${GOOGLE_TOKEN_PATH}` }

    // Verify token is valid JSON
    const tokenContent = fs.readFileSync(tokenPath, 'utf-8')
    JSON.parse(tokenContent)

    return { success: true, message: 'Files found and valid' }
  } catch (err: any) {
    return { success: false, message: err.message }
  }
}

export async function validateSlack(fields: Record<string, string>): Promise<TestResult> {
  const { SLACK_BOT_TOKEN } = fields
  if (!SLACK_BOT_TOKEN) return { success: false, message: 'Missing bot token' }
  try {
    const res = await fetchWithTimeout('https://slack.com/api/auth.test', {
      method: 'POST',
      headers: { Authorization: `Bearer ${SLACK_BOT_TOKEN}`, 'Content-Type': 'application/json' },
    })
    const data = await res.json() as any
    if (data.ok) return { success: true, message: `Connected as ${data.user || 'bot'}`, statusCode: 200 }
    return { success: false, message: data.error || 'Auth test failed', statusCode: 200 }
  } catch (err: any) {
    if (err.name === 'AbortError') return { success: false, message: 'Connection timeout' }
    return { success: false, message: err.message }
  }
}

export async function validateGithub(fields: Record<string, string>): Promise<TestResult> {
  const { GITHUB_API_TOKEN } = fields
  if (!GITHUB_API_TOKEN) return { success: false, message: 'Missing API token' }
  try {
    const res = await fetchWithTimeout('https://api.github.com/user', {
      headers: { Authorization: `Bearer ${GITHUB_API_TOKEN}`, 'User-Agent': 'PM-OS-Connector' },
    })
    if (res.ok) {
      const data = await res.json() as any
      return { success: true, message: `Connected as ${data.login}`, statusCode: res.status }
    }
    return { success: false, message: `${res.status} ${res.statusText}`, statusCode: res.status }
  } catch (err: any) {
    if (err.name === 'AbortError') return { success: false, message: 'Connection timeout' }
    return { success: false, message: err.message }
  }
}

export async function validateFigma(fields: Record<string, string>): Promise<TestResult> {
  const { FIGMA_ACCESS_TOKEN } = fields
  if (!FIGMA_ACCESS_TOKEN) return { success: false, message: 'Missing access token' }
  try {
    const res = await fetchWithTimeout('https://api.figma.com/v1/me', {
      headers: { 'X-Figma-Token': FIGMA_ACCESS_TOKEN },
    })
    if (res.ok) {
      const data = await res.json() as any
      return { success: true, message: `Connected as ${data.handle || data.email}`, statusCode: res.status }
    }
    return { success: false, message: `${res.status} ${res.statusText}`, statusCode: res.status }
  } catch (err: any) {
    if (err.name === 'AbortError') return { success: false, message: 'Connection timeout' }
    return { success: false, message: err.message }
  }
}
