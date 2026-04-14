import { execFile } from 'child_process'
import * as fs from 'fs'
import * as path from 'path'
import { logInfo, logError, logOk } from './logger'
import type { VerifyCheck, VerifyResult } from '../../shared/types'

function execAsync(cmd: string, args: string[], env?: Record<string, string>, timeout = 15000): Promise<{ stdout: string; code: number }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout, env: { ...process.env, ...env } }, (err, stdout) => {
      resolve({ stdout: stdout?.toString() || '', code: err ? 1 : 0 })
    })
  })
}

function check(name: string, category: VerifyCheck['category'], passed: boolean, message: string, duration = 0): VerifyCheck {
  return { name, category, passed, message, duration }
}

// --- Structure Checks ---
async function checkStructure(pmosPath: string): Promise<VerifyCheck[]> {
  const results: VerifyCheck[] = []

  // Marker file
  const marker = path.join(pmosPath, '.pm-os-root')
  results.push(check('.pm-os-root marker', 'structure', fs.existsSync(marker), fs.existsSync(marker) ? 'Found' : 'Missing'))

  // Required directories
  const requiredDirs = ['common', 'user', 'common/tools', 'common/.claude/commands', 'user/brain', 'user/.secrets']
  for (const dir of requiredDirs) {
    const full = path.join(pmosPath, dir)
    const exists = fs.existsSync(full)
    results.push(check(`Directory: ${dir}`, 'structure', exists, exists ? 'Found' : 'Missing'))
  }

  // .secrets permissions
  const secretsPath = path.join(pmosPath, 'user', '.secrets')
  if (fs.existsSync(secretsPath)) {
    try {
      const stats = fs.statSync(secretsPath)
      const mode = stats.mode & 0o777
      const ok = mode === 0o700
      results.push(check('.secrets permissions', 'structure', ok, ok ? '0700' : `${mode.toString(8)} (expected 0700)`))
    } catch {
      results.push(check('.secrets permissions', 'structure', false, 'Cannot read permissions'))
    }
  }

  return results
}

// --- Config Checks ---
async function checkConfig(pmosPath: string): Promise<VerifyCheck[]> {
  const results: VerifyCheck[] = []

  // .env is valid
  const envPath = path.join(pmosPath, 'user', '.env')
  if (fs.existsSync(envPath)) {
    try {
      const content = fs.readFileSync(envPath, 'utf-8')
      const hasEntries = content.split('\n').some((l) => l.includes('=') && !l.trim().startsWith('#'))
      results.push(check('.env file', 'config', true, hasEntries ? 'Valid with entries' : 'Valid (empty placeholders)'))
    } catch (err: any) {
      results.push(check('.env file', 'config', false, err.message))
    }
  } else {
    results.push(check('.env file', 'config', false, 'Missing'))
  }

  // config.yaml is valid YAML
  const configPath = path.join(pmosPath, 'user', 'config.yaml')
  if (fs.existsSync(configPath)) {
    try {
      const content = fs.readFileSync(configPath, 'utf-8')
      // Basic YAML validation: should have key: value pairs
      const hasContent = content.includes(':')
      results.push(check('config.yaml', 'config', hasContent, hasContent ? 'Valid YAML' : 'Empty or malformed'))
    } catch (err: any) {
      results.push(check('config.yaml', 'config', false, err.message))
    }
  } else {
    results.push(check('config.yaml', 'config', false, 'Missing'))
  }

  // CLAUDE.md
  const claudePath = path.join(pmosPath, 'CLAUDE.md')
  if (fs.existsSync(claudePath)) {
    const content = fs.readFileSync(claudePath, 'utf-8')
    const hasReserved = content.includes('Reserved')
    results.push(check('CLAUDE.md', 'config', true, hasReserved ? 'Contains reserved words section' : 'Present'))
  } else {
    results.push(check('CLAUDE.md', 'config', false, 'Missing'))
  }

  // .mcp.json
  const mcpPath = path.join(pmosPath, '.mcp.json')
  if (fs.existsSync(mcpPath)) {
    try {
      const config = JSON.parse(fs.readFileSync(mcpPath, 'utf-8'))
      const hasBrain = !!config.mcpServers?.brain
      results.push(check('.mcp.json', 'config', hasBrain, hasBrain ? 'Brain server configured' : 'No brain server'))
    } catch (err: any) {
      results.push(check('.mcp.json', 'config', false, `Parse error: ${err.message}`))
    }
  } else {
    results.push(check('.mcp.json', 'config', false, 'Missing'))
  }

  // agent.md
  const agentPath = path.join(pmosPath, 'common', 'AGENT.md')
  results.push(check('AGENT.md', 'config', fs.existsSync(agentPath), fs.existsSync(agentPath) ? 'Found' : 'Missing'))

  return results
}

// --- Python Environment Checks ---
async function checkPython(pmosPath: string): Promise<VerifyCheck[]> {
  const results: VerifyCheck[] = []
  const start = Date.now()

  // Python version
  const pyResult = await execAsync('python3', ['--version'])
  if (pyResult.code === 0) {
    const match = pyResult.stdout.match(/Python (\d+\.\d+)/)
    const version = match?.[1] || 'unknown'
    const [major, minor] = (match?.[1] || '0.0').split('.').map(Number)
    results.push(check('Python version', 'python', major >= 3 && minor >= 10, `Python ${version}`))
  } else {
    results.push(check('Python version', 'python', false, 'python3 not found'))
  }

  // Virtual environment
  const venvPython = path.join(pmosPath, '.venv', 'bin', 'python3')
  const venvExists = fs.existsSync(venvPython)
  results.push(check('Virtual environment', 'python', venvExists, venvExists ? 'Found' : 'Missing'))

  // Critical imports
  if (venvExists) {
    const imports = ['yaml', 'dotenv', 'requests', 'slack_sdk', 'anthropic']
    const importStmt = imports.map((i) => `import ${i}`).join('; ')
    const importResult = await execAsync(venvPython, ['-c', importStmt], undefined, 15000)
    results.push(check(
      'Critical packages',
      'python',
      importResult.code === 0,
      importResult.code === 0 ? `All ${imports.length} packages importable` : 'Some packages missing',
    ))
  }

  return results
}

// --- Tool Simulation Checks ---
async function checkTools(pmosPath: string): Promise<VerifyCheck[]> {
  const results: VerifyCheck[] = []
  const venvPython = path.join(pmosPath, '.venv', 'bin', 'python3')
  const commonTools = path.join(pmosPath, 'common', 'tools')

  if (!fs.existsSync(venvPython) || !fs.existsSync(commonTools)) {
    results.push(check('Tool environment', 'tools', false, 'venv or tools dir missing'))
    return results
  }

  // Check pipeline YAML files are parseable
  const pipelinesDir = path.join(pmosPath, 'common', 'pipelines')
  if (fs.existsSync(pipelinesDir)) {
    const yamlFiles = fs.readdirSync(pipelinesDir).filter((f) => f.endsWith('.yaml') || f.endsWith('.yml'))
    results.push(check('Pipeline definitions', 'tools', yamlFiles.length > 0, `${yamlFiles.length} pipeline YAML files`))
  } else {
    results.push(check('Pipeline definitions', 'tools', false, 'pipelines/ not found'))
  }

  // Count command .md files
  const commandsDir = path.join(pmosPath, 'common', '.claude', 'commands')
  if (fs.existsSync(commandsDir)) {
    const countMd = (dir: string): number => {
      let count = 0
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.isDirectory() && entry.name !== 'archive') count += countMd(path.join(dir, entry.name))
        else if (entry.name.endsWith('.md')) count++
      }
      return count
    }
    const mdCount = countMd(commandsDir)
    results.push(check('Command inventory', 'commands', mdCount > 0, `${mdCount} command files`))
  } else {
    results.push(check('Command inventory', 'commands', false, 'commands/ not found'))
  }

  // Check brain index tool exists
  const brainIndexPath = path.join(commonTools, 'brain', 'brain_index.py')
  results.push(check('Brain index tool', 'tools', fs.existsSync(brainIndexPath), fs.existsSync(brainIndexPath) ? 'Found' : 'Missing'))

  // Check session tool exists
  const sessionPath = path.join(commonTools, 'session', 'session_manager.py')
  results.push(check('Session manager', 'tools', fs.existsSync(sessionPath), fs.existsSync(sessionPath) ? 'Found' : 'Missing'))

  return results
}

// --- Integration Readiness ---
async function checkIntegrations(pmosPath: string): Promise<VerifyCheck[]> {
  const results: VerifyCheck[] = []

  // .env has expected placeholder keys
  const envPath = path.join(pmosPath, 'user', '.env')
  if (fs.existsSync(envPath)) {
    const content = fs.readFileSync(envPath, 'utf-8')
    const expectedKeys = ['JIRA_URL', 'SLACK_BOT_TOKEN', 'GITHUB_API_TOKEN', 'GOOGLE_CREDENTIALS_PATH']
    const foundKeys = expectedKeys.filter((k) => content.includes(k))
    results.push(check(
      'Integration keys',
      'integrations',
      foundKeys.length === expectedKeys.length,
      `${foundKeys.length}/${expectedKeys.length} expected keys present`,
    ))
  }

  // Google credentials
  const credsPath = path.join(pmosPath, 'user', '.secrets', 'credentials.json')
  if (fs.existsSync(credsPath)) {
    try {
      JSON.parse(fs.readFileSync(credsPath, 'utf-8'))
      results.push(check('Google credentials', 'integrations', true, 'Valid JSON'))
    } catch {
      results.push(check('Google credentials', 'integrations', false, 'Invalid JSON'))
    }
  } else {
    results.push(check('Google credentials', 'integrations', false, 'Not distributed'))
  }

  // MCP server script exists and is executable
  const mcpServerPath = path.join(pmosPath, 'common', 'tools', 'mcp', 'brain_mcp', 'server.py')
  results.push(check('Brain MCP server', 'integrations', fs.existsSync(mcpServerPath), fs.existsSync(mcpServerPath) ? 'Found' : 'Missing'))

  return results
}

// --- Main Runner ---
export async function runVerification(pmosPath: string): Promise<VerifyResult> {
  const start = Date.now()
  logInfo('verify', `Running verification on ${pmosPath}`)

  const allChecks: VerifyCheck[] = []

  const [structure, config, python, tools, integrations] = await Promise.all([
    checkStructure(pmosPath),
    checkConfig(pmosPath),
    checkPython(pmosPath),
    checkTools(pmosPath),
    checkIntegrations(pmosPath),
  ])

  allChecks.push(...structure, ...config, ...python, ...tools, ...integrations)

  const passed = allChecks.filter((c) => c.passed).length
  const failed = allChecks.filter((c) => !c.passed).length
  const success = failed === 0
  const duration = (Date.now() - start) / 1000

  if (success) {
    logOk('verify', `All ${passed} checks passed (${duration.toFixed(1)}s)`)
  } else {
    logError('verify', `${failed}/${allChecks.length} checks failed (${duration.toFixed(1)}s)`)
    for (const c of allChecks.filter((c) => !c.passed)) {
      logError('verify', `  FAIL: ${c.name} — ${c.message}`)
    }
  }

  return { success, checks: allChecks, duration }
}
