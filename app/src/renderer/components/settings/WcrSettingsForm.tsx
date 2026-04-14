import { useState } from 'react'
import { Plus, Trash2, ChevronDown, ChevronRight } from 'lucide-react'
import { SettingsField, SettingsToggle, SettingsSelect, SettingsSection } from './SettingsField'

interface WcrSettingsFormProps {
  data: Record<string, any>
  onChange: (section: string, value: any) => void
}

const PRODUCT_TYPE_OPTIONS = [
  { value: 'brand', label: 'Brand' },
  { value: 'product', label: 'Product' },
  { value: 'feature', label: 'Feature' },
  { value: 'project', label: 'Project' },
  { value: 'system', label: 'System' },
]

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'archived', label: 'Archived' },
]

const CADENCE_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'biweekly', label: 'Biweekly' },
  { value: 'monthly', label: 'Monthly' },
]

const RELATIONSHIP_OPTIONS = [
  { value: 'leadership_partner', label: 'Leadership Partner' },
  { value: 'peer', label: 'Peer' },
  { value: 'stakeholder', label: 'Stakeholder' },
]

const iconBtnStyle: React.CSSProperties = {
  width: 24, height: 24, borderRadius: 4, border: '1px solid var(--border)',
  background: '#0a1929', display: 'flex', alignItems: 'center', justifyContent: 'center',
  cursor: 'pointer', flexShrink: 0,
}

export default function WcrSettingsForm({ data, onChange }: WcrSettingsFormProps) {
  const products = data.products || {}
  const org = products.organization || {}
  const items = products.items || []
  const team = data.team || {}
  const manager = team.manager || {}
  const reports = team.reports || []
  const stakeholders = team.stakeholders || []
  const workspace = data.workspace || {}
  const contextSync = workspace.context_sync || {}
  const masterSheet = data.master_sheet || {}
  const tabs = masterSheet.tabs || {}

  const [expandedProduct, setExpandedProduct] = useState<number | null>(null)

  /* ---- Products ---- */

  const updateOrg = (field: string, value: any) => {
    onChange('products', { ...products, organization: { ...org, [field]: value }, items })
  }

  const updateItem = (index: number, field: string, value: any) => {
    const updated = [...items]
    updated[index] = { ...updated[index], [field]: value }
    onChange('products', { ...products, organization: org, items: updated })
  }

  const addItem = () => {
    const id = `item-${Date.now()}`
    onChange('products', {
      ...products, organization: org,
      items: [...items, { id, name: '', type: 'product', market: '', status: 'active' }],
    })
    setExpandedProduct(items.length)
  }

  const removeItem = (index: number) => {
    onChange('products', { ...products, organization: org, items: items.filter((_: any, i: number) => i !== index) })
    if (expandedProduct === index) setExpandedProduct(null)
  }

  /* ---- Team ---- */

  const updateManager = (field: string, value: any) => {
    onChange('team', { ...team, manager: { ...manager, [field]: value }, reports, stakeholders })
  }

  const updateReport = (index: number, field: string, value: any) => {
    const updated = [...reports]
    updated[index] = { ...updated[index], [field]: value }
    onChange('team', { ...team, manager, reports: updated, stakeholders })
  }

  const addReport = () => {
    if (reports.length >= 15) return
    const id = `report-${Date.now()}`
    onChange('team', { ...team, manager, reports: [...reports, { id, name: '', email: '', role: '' }], stakeholders })
  }

  const removeReport = (index: number) => {
    onChange('team', { ...team, manager, reports: reports.filter((_: any, i: number) => i !== index), stakeholders })
  }

  const updateStakeholder = (index: number, field: string, value: any) => {
    const updated = [...stakeholders]
    updated[index] = { ...updated[index], [field]: value }
    onChange('team', { ...team, manager, reports, stakeholders: updated })
  }

  const addStakeholder = () => {
    const id = `sh-${Date.now()}`
    onChange('team', {
      ...team, manager, reports,
      stakeholders: [...stakeholders, { id, name: '', email: '', role: '', relationship: 'stakeholder' }],
    })
  }

  const removeStakeholder = (index: number) => {
    onChange('team', { ...team, manager, reports, stakeholders: stakeholders.filter((_: any, i: number) => i !== index) })
  }

  /* ---- Workspace & Master Sheet ---- */

  const updateWorkspace = (field: string, value: any) => {
    onChange('workspace', { ...workspace, [field]: value })
  }

  const updateContextSync = (field: string, value: any) => {
    onChange('workspace', { ...workspace, context_sync: { ...contextSync, [field]: value } })
  }

  const updateMasterSheet = (field: string, value: any) => {
    onChange('master_sheet', { ...masterSheet, [field]: value })
  }

  const updateMasterSheetTab = (field: string, value: any) => {
    onChange('master_sheet', { ...masterSheet, tabs: { ...tabs, [field]: value } })
  }

  return (
    <div style={{ paddingTop: 16 }}>
      {/* Organization */}
      <SettingsSection title="Organization">
        <SettingsField label="Name" value={org.name || ''} onChange={(v) => updateOrg('name', v)} placeholder="My Organization" />
        <SettingsField label="Jira Project" value={org.jira_project || ''} onChange={(v) => updateOrg('jira_project', v)} placeholder="ORG" />
      </SettingsSection>

      {/* Products */}
      <SettingsSection title="Products">
        {items.map((item: any, i: number) => {
          const isExp = expandedProduct === i
          return (
            <div key={item.id || i} style={{ marginBottom: 4, border: '1px solid var(--border)', borderRadius: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px' }}>
                <button
                  onClick={() => setExpandedProduct(isExp ? null : i)}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', cursor: 'pointer', fontFamily: "'Inter', sans-serif", fontSize: 13, fontWeight: 600 }}
                >
                  {isExp ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  {item.name || `Product ${i + 1}`}
                </button>
                <button onClick={() => removeItem(i)} style={iconBtnStyle} title="Remove">
                  <Trash2 size={12} color="#dc2626" />
                </button>
              </div>
              {isExp && (
                <div style={{ padding: '0 12px 12px' }}>
                  <SettingsField label="Name" value={item.name || ''} onChange={(v) => updateItem(i, 'name', v)} placeholder="Product name" />
                  <SettingsSelect label="Type" value={item.type || 'product'} onChange={(v) => updateItem(i, 'type', v)} options={PRODUCT_TYPE_OPTIONS} />
                  <SettingsField label="Market" value={item.market || ''} onChange={(v) => updateItem(i, 'market', v)} placeholder="e.g. Global" />
                  <SettingsSelect label="Status" value={item.status || 'active'} onChange={(v) => updateItem(i, 'status', v)} options={STATUS_OPTIONS} />
                  <SettingsField label="Jira Project" value={item.jira_project || ''} onChange={(v) => updateItem(i, 'jira_project', v)} placeholder="PROJ" />
                  <SettingsField label="Squad" value={item.squad || ''} onChange={(v) => updateItem(i, 'squad', v)} placeholder="e.g. Growth Squad" />
                  <SettingsField label="Tribe" value={item.tribe || ''} onChange={(v) => updateItem(i, 'tribe', v)} placeholder="e.g. Platform" />
                  <SettingsField label="Board ID" value={item.board_id || ''} onChange={(v) => updateItem(i, 'board_id', v)} placeholder="Board ID" />
                </div>
              )}
            </div>
          )
        })}
        <button onClick={addItem} style={{ ...iconBtnStyle, width: '100%', height: 32, gap: 6, fontSize: 12, fontFamily: "'Inter', sans-serif", marginTop: 4 }}>
          <Plus size={12} /> Add Product
        </button>
      </SettingsSection>

      {/* Manager */}
      <SettingsSection title="Manager">
        <SettingsField label="Name" value={manager.name || ''} onChange={(v) => updateManager('name', v)} placeholder="Manager name" />
        <SettingsField label="Email" value={manager.email || ''} onChange={(v) => updateManager('email', v)} placeholder="email@company.com" />
        <SettingsField label="Slack ID" value={manager.slack_id || ''} onChange={(v) => updateManager('slack_id', v)} placeholder="U0123ABC" />
        <SettingsField label="Role" value={manager.role || ''} onChange={(v) => updateManager('role', v)} placeholder="e.g. VP Product" />
      </SettingsSection>

      {/* Direct Reports */}
      <SettingsSection title={`Direct Reports (${reports.length}/15)`}>
        {reports.map((r: any, i: number) => (
          <div key={r.id || i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 8, padding: 10, border: '1px solid var(--border)', borderRadius: 6 }}>
            <div style={{ flex: 1 }}>
              <SettingsField label="Name" value={r.name || ''} onChange={(v) => updateReport(i, 'name', v)} placeholder="Name" />
              <SettingsField label="Email" value={r.email || ''} onChange={(v) => updateReport(i, 'email', v)} placeholder="email@company.com" />
              <SettingsField label="Role" value={r.role || ''} onChange={(v) => updateReport(i, 'role', v)} placeholder="Role" />
              <SettingsField label="Squad" value={r.squad || ''} onChange={(v) => updateReport(i, 'squad', v)} placeholder="Squad" />
              <SettingsField label="Slack ID" value={r.slack_id || ''} onChange={(v) => updateReport(i, 'slack_id', v)} placeholder="U0123ABC" />
              <SettingsSelect label="1:1 Cadence" value={r.one_on_one_cadence || ''} onChange={(v) => updateReport(i, 'one_on_one_cadence', v)} options={CADENCE_OPTIONS} />
            </div>
            <button onClick={() => removeReport(i)} style={{ ...iconBtnStyle, marginTop: 20 }} title="Remove">
              <Trash2 size={12} color="#dc2626" />
            </button>
          </div>
        ))}
        {reports.length < 15 && (
          <button onClick={addReport} style={{ ...iconBtnStyle, width: '100%', height: 32, gap: 6, fontSize: 12, fontFamily: "'Inter', sans-serif" }}>
            <Plus size={12} /> Add Report
          </button>
        )}
      </SettingsSection>

      {/* Stakeholders */}
      <SettingsSection title="Stakeholders">
        {stakeholders.map((s: any, i: number) => (
          <div key={s.id || i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 8, padding: 10, border: '1px solid var(--border)', borderRadius: 6 }}>
            <div style={{ flex: 1 }}>
              <SettingsField label="Name" value={s.name || ''} onChange={(v) => updateStakeholder(i, 'name', v)} placeholder="Name" />
              <SettingsField label="Email" value={s.email || ''} onChange={(v) => updateStakeholder(i, 'email', v)} placeholder="email@company.com" />
              <SettingsField label="Role" value={s.role || ''} onChange={(v) => updateStakeholder(i, 'role', v)} placeholder="Role" />
              <SettingsSelect label="Relationship" value={s.relationship || 'stakeholder'} onChange={(v) => updateStakeholder(i, 'relationship', v)} options={RELATIONSHIP_OPTIONS} />
              <SettingsSelect label="1:1 Cadence" value={s.one_on_one_cadence || ''} onChange={(v) => updateStakeholder(i, 'one_on_one_cadence', v)} options={CADENCE_OPTIONS} />
            </div>
            <button onClick={() => removeStakeholder(i)} style={{ ...iconBtnStyle, marginTop: 20 }} title="Remove">
              <Trash2 size={12} color="#dc2626" />
            </button>
          </div>
        ))}
        <button onClick={addStakeholder} style={{ ...iconBtnStyle, width: '100%', height: 32, gap: 6, fontSize: 12, fontFamily: "'Inter', sans-serif" }}>
          <Plus size={12} /> Add Stakeholder
        </button>
      </SettingsSection>

      {/* Workspace */}
      <SettingsSection title="Workspace">
        <SettingsToggle label="Auto-create Folders" checked={workspace.auto_create_folders ?? true} onChange={(v) => updateWorkspace('auto_create_folders', v)} />
        <SettingsField
          label="Standard Subfolders"
          value={Array.isArray(workspace.standard_subfolders) ? workspace.standard_subfolders.join(', ') : ''}
          onChange={(v) => updateWorkspace('standard_subfolders', v.split(',').map((s: string) => s.trim()).filter(Boolean))}
          placeholder="docs, specs, designs"
        />
        <SettingsToggle label="Context Sync Enabled" checked={contextSync.enabled ?? false} onChange={(v) => updateContextSync('enabled', v)} />
        <SettingsToggle label="Sync on Boot" checked={contextSync.sync_on_boot ?? false} onChange={(v) => updateContextSync('sync_on_boot', v)} />
        <SettingsToggle label="Bidirectional Sync" checked={contextSync.bidirectional ?? false} onChange={(v) => updateContextSync('bidirectional', v)} />
      </SettingsSection>

      {/* Master Sheet */}
      <SettingsSection title="Master Sheet">
        <SettingsToggle label="Enabled" checked={masterSheet.enabled ?? false} onChange={(v) => updateMasterSheet('enabled', v)} />
        <SettingsField label="Spreadsheet ID" value={masterSheet.spreadsheet_id || ''} onChange={(v) => updateMasterSheet('spreadsheet_id', v)} placeholder="Google Sheets ID" />
        <SettingsField label="Instructions Tab" value={tabs.instructions || ''} onChange={(v) => updateMasterSheetTab('instructions', v)} placeholder="Instructions" />
        <SettingsField label="Topics Tab" value={tabs.topics || ''} onChange={(v) => updateMasterSheetTab('topics', v)} placeholder="Topics" />
        <SettingsField label="Recurring Tab" value={tabs.recurring || ''} onChange={(v) => updateMasterSheetTab('recurring', v)} placeholder="Recurring" />
        <SettingsField label="Slack Channel" value={masterSheet.slack_channel || ''} onChange={(v) => updateMasterSheet('slack_channel', v)} placeholder="C0XXXXXXXXX" />
        <SettingsField label="Timezone" value={masterSheet.timezone || ''} onChange={(v) => updateMasterSheet('timezone', v)} placeholder="Europe/Berlin" />
      </SettingsSection>
    </div>
  )
}
