import { useState, useRef, useEffect } from 'react'
import OnboardingHeader from '../components/onboarding/OnboardingHeader'
import AuthMethodTabs from '../components/onboarding/AuthMethodTabs'
import OnboardingNav from '../components/onboarding/OnboardingNav'
import StepForm, { StepFormRef } from '../components/onboarding/StepForm'
import VerifyButton from '../components/onboarding/VerifyButton'
import FileUpload from '../components/onboarding/FileUpload'
import DevCredentials from '../components/onboarding/DevCredentials'
import { CONNECTION_CONFIGS } from '@shared/connection-configs'
import type { OnboardingStepConfig } from '@shared/types'

const STEPS: OnboardingStepConfig[] = [
  {
    id: 'claude-connectors',
    title: 'Claude Connectors',
    connectionIds: [],
    authOptions: [],
  },
  {
    id: 'google',
    title: 'Google OAuth',
    connectionIds: ['google'],
    authOptions: [
      { id: 'direct', label: 'Direct API', enabled: true },
      { id: 'pmos-oauth', label: 'PM-OS OAuth', enabled: true },
      { id: 'sso', label: 'SSO / OAuth', enabled: false },
    ],
  },
  {
    id: 'jira-confluence',
    title: 'Jira & Confluence',
    connectionIds: ['jira', 'confluence'],
    authOptions: [
      { id: 'direct', label: 'Direct API', enabled: true },
      { id: 'sso', label: 'SSO / OAuth', enabled: false },
    ],
  },
  {
    id: 'github',
    title: 'GitHub',
    connectionIds: ['github'],
    authOptions: [
      { id: 'direct', label: 'Direct API', enabled: true },
      { id: 'sso', label: 'SSO / OAuth', enabled: false },
    ],
  },
  {
    id: 'slack',
    title: 'Slack',
    connectionIds: ['slack'],
    authOptions: [
      { id: 'direct', label: 'Direct API', enabled: true },
      { id: 'sso', label: 'SSO / OAuth', enabled: false },
    ],
  },
  {
    id: 'figma',
    title: 'Figma',
    connectionIds: ['figma'],
    authOptions: [
      { id: 'direct', label: 'Direct API', enabled: true },
      { id: 'sso', label: 'SSO / OAuth', enabled: false },
    ],
  },
]

export default function OnboardingPage() {
  const [currentStep, setCurrentStep] = useState(0)
  const [activeTab, setActiveTab] = useState('direct')
  const [saving, setSaving] = useState(false)
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [devMode, setDevMode] = useState(false)
  const [googleOAuthStatus, setGoogleOAuthStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [googleOAuthError, setGoogleOAuthError] = useState('')
  const formRef = useRef<StepFormRef>(null)

  const step = STEPS[currentStep]
  const configs = step.connectionIds
    .map((id) => CONNECTION_CONFIGS.find((c) => c.id === id))
    .filter((c): c is NonNullable<typeof c> => c != null)

  // For Jira/Confluence step, only show Jira fields (Confluence shares them)
  const formConfigs = step.id === 'jira-confluence'
    ? configs.filter((c) => c.id === 'jira')
    : configs

  useEffect(() => {
    window.api.isDevMode().then(setDevMode)
  }, [])

  // Reset tab when changing steps
  useEffect(() => {
    setActiveTab('direct')
    setValidationErrors([])
    setGoogleOAuthStatus('idle')
    setGoogleOAuthError('')
  }, [currentStep])

  const handleSaveAndContinue = async () => {
    const values = formRef.current?.getValues() || {}
    const hasAnyValues = Object.values(values).some((v) => v.trim() !== '')

    if (!hasAnyValues) {
      // No values = treat as skip
      handleSkip()
      return
    }

    // Validate required fields
    const errors: string[] = []
    for (const config of formConfigs) {
      for (const field of config.fields) {
        if (field.required && !values[field.envKey]?.trim()) {
          errors.push(field.envKey)
        }
      }
    }
    if (errors.length > 0) {
      setValidationErrors(errors)
      return
    }

    setSaving(true)
    try {
      // Save fields for each connection in this step
      for (const config of configs) {
        const connectionFields: Record<string, string> = {}
        for (const field of config.fields) {
          connectionFields[field.envKey] = values[field.envKey] || ''
        }
        await window.api.saveConnection(config.id, connectionFields)
      }
      advance()
    } finally {
      setSaving(false)
    }
  }

  const handleSkip = () => {
    advance()
  }

  const handleBack = () => {
    if (currentStep > 0) setCurrentStep(currentStep - 1)
  }

  const advance = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      // Last step — complete onboarding
      window.api.completeOnboarding()
    }
  }

  const handleVerify = async (connectionId: string) => {
    // Save fields first so the test-connection IPC can read them
    const values = formRef.current?.getValues() || {}
    const config = CONNECTION_CONFIGS.find((c) => c.id === connectionId)
    if (config) {
      const connectionFields: Record<string, string> = {}
      for (const field of config.fields) {
        connectionFields[field.envKey] = values[field.envKey] || ''
      }
      await window.api.saveConnection(connectionId, connectionFields)
    }
    return window.api.testConnection(connectionId)
  }

  const handleGoogleOAuth = async () => {
    setGoogleOAuthStatus('loading')
    setGoogleOAuthError('')
    try {
      const result = await window.api.triggerGoogleOAuth()
      if (result.success) {
        setGoogleOAuthStatus('success')
      } else {
        setGoogleOAuthStatus('error')
        setGoogleOAuthError(result.error || 'OAuth failed')
      }
    } catch (err: any) {
      setGoogleOAuthStatus('error')
      setGoogleOAuthError(err.message || 'OAuth failed')
    }
  }

  const handleDevCredentials = async () => {
    return window.api.loadDevCredentials()
  }

  const handleApplyDevCredentials = (creds: Record<string, string>) => {
    const relevantValues: Record<string, string> = {}
    for (const config of configs) {
      for (const field of config.fields) {
        if (creds[field.envKey]) {
          relevantValues[field.envKey] = creds[field.envKey]
        }
      }
    }
    formRef.current?.setValues(relevantValues)
  }

  const renderGoogleDirectAPI = () => (
    <div>
      <div style={{ marginBottom: 20 }}>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
          Create a Google Cloud Console project with OAuth credentials. Download the <code>credentials.json</code> file and upload it below.
        </p>
        <FileUpload
          label="Google OAuth Credentials File"
          accept=".json"
          onUpload={(path) => window.api.uploadGoogleCredentials(path)}
        />
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5 }}>
        After uploading, click "Authenticate with Google" to complete the OAuth consent flow.
      </div>
      <button
        onClick={handleGoogleOAuth}
        disabled={googleOAuthStatus === 'loading'}
        style={{
          marginTop: 12,
          padding: '10px 24px',
          background: 'var(--btn-primary-bg)',
          color: 'var(--btn-primary-text)',
          border: 'none',
          borderRadius: 4,
          fontSize: 14,
          fontWeight: 500,
          cursor: googleOAuthStatus === 'loading' ? 'not-allowed' : 'pointer',
          opacity: googleOAuthStatus === 'loading' ? 0.6 : 1,
          fontFamily: "'Inter', sans-serif",
        }}
      >
        {googleOAuthStatus === 'loading' ? 'Authenticating...' : 'Authenticate with Google'}
      </button>
      {renderGoogleOAuthResult()}
    </div>
  )

  const renderGooglePmosOAuth = () => (
    <div>
      <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
        Use the bundled PM-OS credentials to authenticate with Google. This will open your browser for consent.
      </p>
      <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
        Scopes requested: Calendar, Drive, Documents, Sheets, Gmail (read-only)
      </p>
      <button
        onClick={handleGoogleOAuth}
        disabled={googleOAuthStatus === 'loading'}
        style={{
          padding: '10px 24px',
          background: 'var(--btn-primary-bg)',
          color: 'var(--btn-primary-text)',
          border: 'none',
          borderRadius: 4,
          fontSize: 14,
          fontWeight: 500,
          cursor: googleOAuthStatus === 'loading' ? 'not-allowed' : 'pointer',
          opacity: googleOAuthStatus === 'loading' ? 0.6 : 1,
          fontFamily: "'Inter', sans-serif",
        }}
      >
        {googleOAuthStatus === 'loading' ? 'Authenticating...' : 'Authenticate with Google'}
      </button>
      {renderGoogleOAuthResult()}
    </div>
  )

  const renderGoogleOAuthResult = () => {
    if (googleOAuthStatus === 'success') {
      return (
        <div style={{ marginTop: 12, padding: '8px 12px', background: '#0a2a1a', border: '1px solid #bbf7d0', borderRadius: 4, fontSize: 13, color: '#4ade80' }}>
          Google authentication successful
        </div>
      )
    }
    if (googleOAuthStatus === 'error') {
      return (
        <div style={{ marginTop: 12, padding: '8px 12px', background: '#2a0a0a', border: '1px solid #fecaca', borderRadius: 4, fontSize: 13, color: '#dc2626' }}>
          {googleOAuthError}
        </div>
      )
    }
    return null
  }

  const renderJiraConfluenceNote = () => (
    <div style={{
      marginTop: 16,
      padding: 12,
      background: '#0a1929',
      border: '1px solid #bae6fd',
      borderRadius: 4,
      fontSize: 13,
      color: '#0369a1',
    }}>
      Confluence uses the same Atlassian credentials as Jira. Both will be configured automatically.
    </div>
  )

  const renderClaudeConnectorsStep = () => (
    <div>
      <div style={{
        padding: 16, background: '#0a2a1a', border: '1px solid #bbf7d0', borderRadius: 8,
        marginBottom: 20,
      }}>
        <h4 style={{
          margin: '0 0 8px', fontSize: 14, fontWeight: 600,
          fontFamily: "'Inter', sans-serif", color: '#166534',
        }}>
          Claude Connectors (Primary)
        </h4>
        <p style={{
          margin: '0 0 12px', fontSize: 13, color: '#166534', lineHeight: 1.5,
          fontFamily: "'Inter', sans-serif",
        }}>
          PM-OS v5.0 integrates directly with Claude via MCP servers. Configure your connections
          in Claude Settings to enable Brain, CCE, and other PM-OS capabilities.
        </p>
        <button
          onClick={() => {
            // Open Claude settings — use shell.openExternal via the API or a direct URL
            window.open('https://claude.ai/settings', '_blank')
          }}
          style={{
            padding: '8px 16px', fontSize: 13, fontWeight: 600, border: 'none',
            borderRadius: 4, background: 'black', color: 'white', cursor: 'pointer',
            fontFamily: "'Inter', sans-serif",
          }}
        >
          Open Claude Settings
        </button>
      </div>

      <div style={{
        padding: 16, background: '#0d2137', border: '1px solid var(--border)', borderRadius: 8,
      }}>
        <h4 style={{
          margin: '0 0 8px', fontSize: 14, fontWeight: 600,
          fontFamily: "'Inter', sans-serif", color: '#aabbcc',
        }}>
          API Tokens (Optional)
        </h4>
        <p style={{
          margin: 0, fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5,
          fontFamily: "'Inter', sans-serif",
        }}>
          API tokens for Jira, GitHub, Slack, and other services are configured in the following steps.
          These are optional if you use Claude Connectors.
        </p>
      </div>
    </div>
  )

  const renderStepContent = () => {
    if (step.id === 'claude-connectors') return renderClaudeConnectorsStep()

    if (step.id === 'google') {
      if (activeTab === 'direct') return renderGoogleDirectAPI()
      if (activeTab === 'pmos-oauth') return renderGooglePmosOAuth()
      return null
    }

    return (
      <div>
        <StepForm
          ref={formRef}
          configs={formConfigs}
          initialValues={{}}
          validationErrors={validationErrors}
        />
        {step.id === 'jira-confluence' && renderJiraConfluenceNote()}
        <VerifyButton
          connectionIds={step.id === 'jira-confluence' ? ['jira'] : step.connectionIds}
          onVerify={handleVerify}
          fieldValues={formRef.current?.getValues() || {}}
        />
      </div>
    )
  }

  // Steps that don't use StepForm
  const isGoogleStep = step.id === 'google'
  const isClaudeConnectorsStep = step.id === 'claude-connectors'

  return (
    <div style={{
      width: '100%',
      height: '100vh',
      background: 'var(--bg-onboarding)',
      display: 'flex',
      justifyContent: 'center',
      overflow: 'auto',
    }}>
      <div style={{
        width: '100%',
        maxWidth: 640,
        padding: '48px 32px 0',
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100%',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{
            fontFamily: "'Krub', sans-serif",
            fontWeight: 700,
            fontSize: 16,
            color: 'var(--text-muted)',
          }}>
            Connections & Plugins
          </span>
          <DevCredentials
            isDevMode={devMode}
            onLoadCredentials={handleDevCredentials}
            onApplyCredentials={handleApplyDevCredentials}
          />
        </div>

        <OnboardingHeader
          stepTitle={step.title}
          currentStep={currentStep}
          totalSteps={STEPS.length}
        />

        <AuthMethodTabs
          options={step.authOptions}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <div style={{ flex: 1 }}>
          {renderStepContent()}
        </div>

        <OnboardingNav
          onContinue={isGoogleStep || isClaudeConnectorsStep ? advance : handleSaveAndContinue}
          onSkip={handleSkip}
          onBack={handleBack}
          isFirstStep={currentStep === 0}
          isLastStep={currentStep === STEPS.length - 1}
          continueDisabled={saving}
        />
      </div>
    </div>
  )
}
