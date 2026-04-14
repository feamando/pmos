import { useState, useEffect } from 'react'
import OnboardingHeader from '../components/onboarding/OnboardingHeader'
import OnboardingNav from '../components/onboarding/OnboardingNav'
import DevCredentials from '../components/onboarding/DevCredentials'
import UserSetupStep1 from '../components/user-setup/UserSetupStep1'
import UserSetupStep2 from '../components/user-setup/UserSetupStep2'
import UserSetupStep3 from '../components/user-setup/UserSetupStep3'
import UserSetupStep4 from '../components/user-setup/UserSetupStep4'
import UserSetupStep5 from '../components/user-setup/UserSetupStep5'
import UserSetupStep6 from '../components/user-setup/UserSetupStep6'
import UserSetupStep7 from '../components/user-setup/UserSetupStep7'
import type { UserSetupStepId } from '@shared/types'

interface StepConfig {
  id: UserSetupStepId
  title: string
}

const STEPS: StepConfig[] = [
  { id: 'profile', title: 'User Profile' },
  { id: 'atlassian', title: 'Atlassian Integration' },
  { id: 'github-slack', title: 'GitHub & Slack' },
  { id: 'gdrive', title: 'Core GDrive Files' },
  { id: 'brain', title: 'Brain Enrichment Settings' },
  { id: 'org-people', title: 'Organization & People' },
  { id: 'success', title: 'Setup Complete' },
]

export default function UserSetupPage() {
  const [currentStep, setCurrentStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [devMode, setDevMode] = useState(false)
  const [stepData, setStepData] = useState<Record<string, any>>({})

  const step = STEPS[currentStep]

  useEffect(() => {
    window.api.isDevMode().then(setDevMode)
  }, [])

  const mapStepToConfig = (stepId: string, raw: Record<string, any>): Record<string, any> => {
    switch (stepId) {
      case 'profile': {
        const u = raw.user || {}
        return {
          user: {
            name: u.name || '',
            email: u.email || '',
            function: u.function || '',
            career_step: u.career_step ? Number(u.career_step) : undefined,
            position: u.position || '',
            tribe: u.tribe || '',
          },
        }
      }
      case 'atlassian': {
        const parseCSV = (s: string) => s.split(',').map((v: string) => v.trim()).filter(Boolean)
        return {
          integrations: {
            jira: { tracked_projects: parseCSV(raw.jira_tracked_projects || '') },
            confluence: { spaces: parseCSV(raw.confluence_tracked_spaces || '') },
          },
        }
      }
      case 'github-slack': {
        const gh = raw.github || {}
        const sl = raw.slack || {}
        return {
          integrations: {
            github: {
              org: gh.org || '',
              tracked_repos: gh.tracked_repos ? gh.tracked_repos.split(',').map((v: string) => v.trim()).filter(Boolean) : [],
            },
            slack: {
              channel: sl.channel || '',
              context_output_channel: sl.context_output_channel || '',
            },
          },
        }
      }
      case 'gdrive': {
        const urls = (raw.seed_documents || []).filter((u: string) => u.trim())
        return { brain: { seed_documents: urls } }
      }
      case 'brain': {
        return {
          brain: {
            target_entity_count: Number(raw.target_entity_count) || 500,
            hot_topics_limit: Number(raw.hot_topics_limit) || 10,
            workers: Number(raw.workers) || 5,
          },
          context: { retention_days: Number(raw.retention_days) || 30 },
          meeting_prep: {
            prep_hours: Number(raw.prep_hours) || 12,
            default_depth: raw.default_depth || 'standard',
            workers: Number(raw.prep_workers) || 3,
          },
        }
      }
      case 'org-people': {
        // Data comes directly from WcrSettingsForm in products/team/workspace/master_sheet shape
        const result: Record<string, any> = {}
        if (raw.products) result.products = raw.products
        if (raw.team) result.team = raw.team
        if (raw.workspace) result.workspace = raw.workspace
        if (raw.master_sheet) result.master_sheet = raw.master_sheet
        return result
      }
      default:
        return raw
    }
  }

  const handleSaveAndContinue = async () => {
    const raw = stepData[step.id]
    if (!raw || Object.keys(raw).length === 0) {
      advance()
      return
    }
    setSaving(true)
    try {
      const configData = mapStepToConfig(step.id, raw)
      const result = await window.api.saveUserSetupStep(step.id, configData)
      if (result.success) {
        advance()
      }
    } finally {
      setSaving(false)
    }
  }

  const handleSkip = () => advance()
  const handleBack = () => { if (currentStep > 0) setCurrentStep(currentStep - 1) }

  const advance = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1)
    }
  }

  const updateStepData = (data: Record<string, any>) => {
    setStepData((prev) => ({ ...prev, [step.id]: data }))
  }

  const handleDevLoadConfig = async () => {
    return window.api.loadDevConfig()
  }

  const handleApplyDevConfig = (config: Record<string, any>) => {
    // Each step component reads from the config and populates its own fields
    setStepData((prev) => ({ ...prev, _devConfig: config }))
  }

  const isSuccessStep = step.id === 'success'

  if (isSuccessStep) {
    return <UserSetupStep7 />
  }

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
            User Setup
          </span>
          <DevCredentials
            isDevMode={devMode}
            onLoadCredentials={handleDevLoadConfig}
            onApplyCredentials={handleApplyDevConfig}
          />
        </div>

        <OnboardingHeader
          stepTitle={step.title}
          currentStep={currentStep}
          totalSteps={STEPS.length}
        />

        <div style={{ flex: 1, marginTop: 24 }}>
          {step.id === 'profile' && (
            <UserSetupStep1
              data={stepData['profile'] || {}}
              devConfig={stepData['_devConfig']}
              onChange={updateStepData}
            />
          )}
          {step.id === 'atlassian' && (
            <UserSetupStep2
              data={stepData['atlassian'] || {}}
              devConfig={stepData['_devConfig']}
              onChange={updateStepData}
            />
          )}
          {step.id === 'github-slack' && (
            <UserSetupStep3
              data={stepData['github-slack'] || {}}
              devConfig={stepData['_devConfig']}
              onChange={updateStepData}
            />
          )}
          {step.id === 'gdrive' && (
            <UserSetupStep4
              data={stepData['gdrive'] || {}}
              devConfig={stepData['_devConfig']}
              onChange={updateStepData}
            />
          )}
          {step.id === 'brain' && (
            <UserSetupStep5
              data={stepData['brain'] || {}}
              devConfig={stepData['_devConfig']}
              onChange={updateStepData}
            />
          )}
          {step.id === 'org-people' && (
            <UserSetupStep6
              data={stepData['org-people'] || {}}
              devConfig={stepData['_devConfig']}
              onChange={updateStepData}
            />
          )}
        </div>

        <OnboardingNav
          onContinue={handleSaveAndContinue}
          onSkip={handleSkip}
          onBack={handleBack}
          isFirstStep={currentStep === 0}
          isLastStep={currentStep === STEPS.length - 2}
          continueDisabled={saving}
        />
      </div>
    </div>
  )
}
