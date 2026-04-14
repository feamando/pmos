interface NoteTextProps {
  text: string
}

export default function NoteText({ text }: NoteTextProps) {
  return (
    <p style={{
      fontSize: 12,
      fontStyle: 'italic',
      color: '#aabbcc',
      marginTop: 4,
      marginBottom: 12,
      fontFamily: "'Inter', sans-serif",
    }}>
      {text}
    </p>
  )
}
