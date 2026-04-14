import DynamicList from './DynamicList'
import NoteText from './NoteText'

export interface ManagerData {
  name: string
  email: string
}

export interface ReportData {
  name: string
  email: string
  jira_project: string
}

interface ReportingChainProps {
  manager: ManagerData
  reports: ReportData[]
  onManagerChange: (manager: ManagerData) => void
  onReportsChange: (reports: ReportData[]) => void
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  background: '#0a1929',
  border: '1px solid #ff008844',
  borderRadius: 4,
  fontSize: 14,
  fontFamily: "'Inter', sans-serif",
  boxSizing: 'border-box' as const,
  outline: 'none',
  color: '#ffffff',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text-primary)',
  marginBottom: 4,
  fontFamily: "'Inter', sans-serif",
}

export default function ReportingChain({ manager, reports, onManagerChange, onReportsChange }: ReportingChainProps) {
  return (
    <div>
      <h3 style={{ fontSize: 16, fontWeight: 700, fontFamily: "'Krub', sans-serif", marginBottom: 16, marginTop: 0 }}>
        Reporting Chain
      </h3>

      {/* Manager */}
      <div style={{ marginBottom: 20, padding: 16, border: '1px solid #ff008844', borderRadius: 6 }}>
        <h4 style={{ fontSize: 14, fontWeight: 600, marginTop: 0, marginBottom: 12, fontFamily: "'Inter', sans-serif" }}>
          Manager
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <label style={labelStyle}>Name</label>
            <input
              type="text"
              value={manager.name}
              onChange={(e) => onManagerChange({ ...manager, name: e.target.value })}
              placeholder="Manager name"
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>Email</label>
            <input
              type="text"
              value={manager.email}
              onChange={(e) => onManagerChange({ ...manager, email: e.target.value })}
              placeholder="manager@company.com"
              style={inputStyle}
            />
          </div>
        </div>
      </div>

      {/* Reports */}
      <div style={{ padding: 16, border: '1px solid #ff008844', borderRadius: 6 }}>
        <h4 style={{ fontSize: 14, fontWeight: 600, marginTop: 0, marginBottom: 12, fontFamily: "'Inter', sans-serif" }}>
          Direct Reports
        </h4>
        <DynamicList
          items={reports}
          maxItems={15}
          minItems={0}
          addLabel="Add Report"
          onAdd={() => onReportsChange([...reports, { name: '', email: '', jira_project: '' }])}
          onRemove={(i) => onReportsChange(reports.filter((_, idx) => idx !== i))}
          onUpdate={(i, item) => {
            const updated = [...reports]
            updated[i] = item
            onReportsChange(updated)
          }}
          renderItem={(report, _index, onUpdate) => (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <div>
                <label style={labelStyle}>Name</label>
                <input
                  type="text"
                  value={report.name}
                  onChange={(e) => onUpdate({ ...report, name: e.target.value })}
                  placeholder="Name"
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Email</label>
                <input
                  type="text"
                  value={report.email}
                  onChange={(e) => onUpdate({ ...report, email: e.target.value })}
                  placeholder="email@company.com"
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Project</label>
                <input
                  type="text"
                  value={report.jira_project}
                  onChange={(e) => onUpdate({ ...report, jira_project: e.target.value })}
                  placeholder="PROJ"
                  style={inputStyle}
                />
                {_index === 0 && <NoteText text="Use Jira project keys" />}
              </div>
            </div>
          )}
        />
      </div>
    </div>
  )
}
