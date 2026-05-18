interface NoteTextProps {
  text: string
}

export default function NoteText({ text }: NoteTextProps) {
  return (
    <p style={{
      fontSize: 12,
      fontStyle: 'italic',
      color: '#666666',
      marginTop: 4,
      marginBottom: 12,
      fontFamily: "'Source Sans Pro', sans-serif",
    }}>
      {text}
    </p>
  )
}
