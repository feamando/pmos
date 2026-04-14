import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import { parseEnvContent, parseEnvFile, readEnvValue, readAllEnvValues, writeEnvValues, migrateGithubToken } from '../../src/main/env/env-manager'

let tmpDir: string

beforeEach(() => {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pmos-test-'))
})

afterEach(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true })
})

describe('parseEnvContent', () => {
  it('parses key=value lines', () => {
    const lines = parseEnvContent('FOO=bar\nBAZ=qux')
    expect(lines).toHaveLength(2)
    expect(lines[0]).toMatchObject({ type: 'entry', key: 'FOO', value: 'bar' })
    expect(lines[1]).toMatchObject({ type: 'entry', key: 'BAZ', value: 'qux' })
  })

  it('preserves comments', () => {
    const lines = parseEnvContent('# This is a comment\nFOO=bar')
    expect(lines[0]).toMatchObject({ type: 'comment', raw: '# This is a comment' })
    expect(lines[1]).toMatchObject({ type: 'entry', key: 'FOO', value: 'bar' })
  })

  it('preserves blank lines', () => {
    const lines = parseEnvContent('FOO=bar\n\nBAZ=qux')
    expect(lines).toHaveLength(3)
    expect(lines[1]).toMatchObject({ type: 'blank' })
  })

  it('handles quoted values', () => {
    const lines = parseEnvContent('NAME="Nikita Gorshkov"\nSINGLE=\'hello\'')
    expect(lines[0]).toMatchObject({ type: 'entry', key: 'NAME', value: 'Nikita Gorshkov' })
    expect(lines[1]).toMatchObject({ type: 'entry', key: 'SINGLE', value: 'hello' })
  })

  it('handles empty values', () => {
    const lines = parseEnvContent('EMPTY=\nALSO_EMPTY=')
    expect(lines[0]).toMatchObject({ type: 'entry', key: 'EMPTY', value: '' })
    expect(lines[1]).toMatchObject({ type: 'entry', key: 'ALSO_EMPTY', value: '' })
  })

  it('treats malformed lines as comments', () => {
    const lines = parseEnvContent('this is not valid')
    expect(lines[0]).toMatchObject({ type: 'comment' })
  })

  it('handles values with equals signs', () => {
    const lines = parseEnvContent('TOKEN=abc=def=ghi')
    expect(lines[0]).toMatchObject({ type: 'entry', key: 'TOKEN', value: 'abc=def=ghi' })
  })
})

describe('parseEnvFile', () => {
  it('returns empty lines for missing file', async () => {
    const result = await parseEnvFile(path.join(tmpDir, 'nonexistent.env'))
    expect(result.lines).toHaveLength(0)
  })

  it('parses a real file', async () => {
    const filePath = path.join(tmpDir, '.env')
    fs.writeFileSync(filePath, '# comment\nFOO=bar\n\nBAZ=qux')
    const result = await parseEnvFile(filePath)
    expect(result.lines).toHaveLength(4)
    expect(result.filePath).toBe(filePath)
  })
})

describe('readEnvValue', () => {
  it('reads a specific key', async () => {
    const env = await parseEnvFile(path.join(tmpDir, 'x'))
    env.lines = parseEnvContent('A=1\nB=2\nC=3')
    expect(readEnvValue(env, 'B')).toBe('2')
  })

  it('returns null for missing key', async () => {
    const env = await parseEnvFile(path.join(tmpDir, 'x'))
    env.lines = parseEnvContent('A=1')
    expect(readEnvValue(env, 'MISSING')).toBeNull()
  })
})

describe('readAllEnvValues', () => {
  it('reads multiple keys', async () => {
    const env = await parseEnvFile(path.join(tmpDir, 'x'))
    env.lines = parseEnvContent('A=1\nB=2\nC=3')
    const result = readAllEnvValues(env, ['A', 'C', 'MISSING'])
    expect(result).toEqual({ A: '1', C: '3' })
  })
})

describe('writeEnvValues', () => {
  it('updates existing keys', async () => {
    const filePath = path.join(tmpDir, '.env')
    fs.writeFileSync(filePath, '# header\nFOO=old\nBAR=keep')
    await writeEnvValues(filePath, { FOO: 'new' })
    const content = fs.readFileSync(filePath, 'utf-8')
    expect(content).toContain('FOO=new')
    expect(content).toContain('BAR=keep')
    expect(content).toContain('# header')
  })

  it('adds new keys at the end', async () => {
    const filePath = path.join(tmpDir, '.env')
    fs.writeFileSync(filePath, 'FOO=bar')
    await writeEnvValues(filePath, { NEW_KEY: 'new_value' })
    const content = fs.readFileSync(filePath, 'utf-8')
    expect(content).toContain('FOO=bar')
    expect(content).toContain('NEW_KEY=new_value')
  })

  it('preserves comments and blank lines', async () => {
    const filePath = path.join(tmpDir, '.env')
    fs.writeFileSync(filePath, '# Comment\nFOO=bar\n\n# Another\nBAZ=qux')
    await writeEnvValues(filePath, { FOO: 'updated' })
    const content = fs.readFileSync(filePath, 'utf-8')
    expect(content).toContain('# Comment')
    expect(content).toContain('# Another')
    expect(content).toContain('FOO=updated')
    expect(content).toContain('BAZ=qux')
  })

  it('creates file if it does not exist', async () => {
    const filePath = path.join(tmpDir, 'new', '.env')
    await writeEnvValues(filePath, { KEY: 'val' })
    expect(fs.existsSync(filePath)).toBe(true)
    expect(fs.readFileSync(filePath, 'utf-8')).toContain('KEY=val')
  })
})

describe('migrateGithubToken', () => {
  it('renames GITHUB_HF_PM_OS to GITHUB_API_TOKEN', async () => {
    const filePath = path.join(tmpDir, '.env')
    fs.writeFileSync(filePath, 'GITHUB_HF_PM_OS=my_token\nOTHER=keep')
    const migrated = await migrateGithubToken(filePath)
    expect(migrated).toBe(true)
    const content = fs.readFileSync(filePath, 'utf-8')
    expect(content).toContain('GITHUB_API_TOKEN=my_token')
    expect(content).not.toContain('GITHUB_HF_PM_OS')
    expect(content).toContain('OTHER=keep')
  })

  it('returns false if old key does not exist', async () => {
    const filePath = path.join(tmpDir, '.env')
    fs.writeFileSync(filePath, 'OTHER=val')
    expect(await migrateGithubToken(filePath)).toBe(false)
  })

  it('returns false if new key already exists', async () => {
    const filePath = path.join(tmpDir, '.env')
    fs.writeFileSync(filePath, 'GITHUB_HF_PM_OS=old\nGITHUB_API_TOKEN=new')
    expect(await migrateGithubToken(filePath)).toBe(false)
  })
})
