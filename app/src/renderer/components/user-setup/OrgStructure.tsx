import DynamicList from './DynamicList'

export interface SquadData {
  name: string
  jira_project: string
  board_id: string
}

export interface TribeData {
  name: string
  confluence_space: string
  squads: SquadData[]
}

export interface OrgData {
  mega_alliance: string
  tribes: TribeData[]
}

interface OrgStructureProps {
  data: OrgData
  onChange: (data: OrgData) => void
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

export default function OrgStructure({ data, onChange }: OrgStructureProps) {
  const updateTribe = (index: number, tribe: TribeData) => {
    const tribes = [...data.tribes]
    tribes[index] = tribe
    onChange({ ...data, tribes })
  }

  return (
    <div>
      <h3 style={{ fontSize: 16, fontWeight: 700, fontFamily: "'Krub', sans-serif", marginBottom: 16, marginTop: 24 }}>
        Organization
      </h3>

      {/* Mega-Alliance */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ ...labelStyle, fontSize: 13 }}>Mega-Alliance Name</label>
        <input
          type="text"
          value={data.mega_alliance}
          onChange={(e) => onChange({ ...data, mega_alliance: e.target.value })}
          placeholder="e.g. Platform & Growth"
          style={inputStyle}
        />
      </div>

      {/* Tribes */}
      <DynamicList
        items={data.tribes}
        maxItems={5}
        minItems={0}
        addLabel="Add Tribe"
        onAdd={() => onChange({ ...data, tribes: [...data.tribes, { name: '', confluence_space: '', squads: [] }] })}
        onRemove={(i) => onChange({ ...data, tribes: data.tribes.filter((_, idx) => idx !== i) })}
        onUpdate={(i, tribe) => updateTribe(i, tribe)}
        renderItem={(tribe, tribeIndex, onTribeUpdate) => (
          <div style={{ padding: 16, border: '1px solid #ff008844', borderRadius: 6, marginBottom: 8 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
              <div>
                <label style={labelStyle}>Tribe Name</label>
                <input
                  type="text"
                  value={tribe.name}
                  onChange={(e) => onTribeUpdate({ ...tribe, name: e.target.value })}
                  placeholder="Tribe name"
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Confluence Space</label>
                <input
                  type="text"
                  value={tribe.confluence_space}
                  onChange={(e) => onTribeUpdate({ ...tribe, confluence_space: e.target.value })}
                  placeholder="e.g. TNV"
                  style={inputStyle}
                />
              </div>
            </div>

            {/* Squads within tribe */}
            <div style={{ marginLeft: 16, borderLeft: '2px solid #ff008844', paddingLeft: 16 }}>
              <label style={{ ...labelStyle, fontSize: 12, marginBottom: 8 }}>Squads</label>
              <DynamicList
                items={tribe.squads}
                maxItems={10}
                minItems={0}
                addLabel="Add Squad"
                onAdd={() => onTribeUpdate({ ...tribe, squads: [...tribe.squads, { name: '', jira_project: '', board_id: '' }] })}
                onRemove={(i) => onTribeUpdate({ ...tribe, squads: tribe.squads.filter((_, idx) => idx !== i) })}
                onUpdate={(i, squad) => {
                  const squads = [...tribe.squads]
                  squads[i] = squad
                  onTribeUpdate({ ...tribe, squads })
                }}
                renderItem={(squad, _sqIdx, onSquadUpdate) => (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                    <div>
                      <label style={labelStyle}>Squad Name</label>
                      <input
                        type="text"
                        value={squad.name}
                        onChange={(e) => onSquadUpdate({ ...squad, name: e.target.value })}
                        placeholder="Squad name"
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Jira Project</label>
                      <input
                        type="text"
                        value={squad.jira_project}
                        onChange={(e) => onSquadUpdate({ ...squad, jira_project: e.target.value })}
                        placeholder="GOC"
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Board ID</label>
                      <input
                        type="text"
                        value={squad.board_id}
                        onChange={(e) => onSquadUpdate({ ...squad, board_id: e.target.value })}
                        placeholder="123"
                        style={inputStyle}
                      />
                    </div>
                  </div>
                )}
              />
            </div>
          </div>
        )}
      />
    </div>
  )
}
