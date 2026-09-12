export default function ConnectionStatus({ status }) {
  const connected = status === 'connected'
  return <div className={`connection ${connected ? 'online' : 'offline'}`}><span>●</span> {connected ? 'Raspberry Connected' : status === 'connecting' ? 'Connecting to edge node…' : 'Disconnected'}</div>
}

