import { useRef, useState, type FormEvent } from 'react'
import { AuditReport } from './components/AuditReport'
import { Icon } from './components/Icon'
import { runClaimGuardAgent } from './services/api'
import type { AuditResponse, Invoice } from './types/audit'

type ChatMessage = { role: 'agent' | 'user' | 'activity'; text: string; detail?: string }
const sampleInvoice: Invoice = { numero: 'FAC-2026-001', siniestro_id: 'SIN-001', taller: 'Taller Aurora', items: [{ codigo: 'REP-001', descripcion: 'Parachoques delantero', cantidad: 1, precio_unitario: 450 }, { codigo: 'MAN-001', descripcion: 'Mano de obra', cantidad: 1, precio_unitario: 50 }] }
const initialMessages: ChatMessage[] = [{ role: 'agent', text: 'Hola, soy ClaimGuard.', detail: 'Puedo revisar una factura contra el siniestro y el tarifario. Adjunta una factura o dime qué quieres investigar.' }]

export default function App() {
  const [invoice, setInvoice] = useState<Invoice>(sampleInvoice)
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [prompt, setPrompt] = useState('Audita la factura adjunta para el siniestro SIN-001')
  const [isWorking, setIsWorking] = useState(false)
  const [report, setReport] = useState<AuditResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [claimDetail, setClaimDetail] = useState('Siniestro SIN-001 · Pendiente de consulta')
  const fileInput = useRef<HTMLInputElement>(null)
  const addMessage = (message: ChatMessage) => setMessages((current) => [...current, message])
  const importInvoice = async (file: File) => {
    try {
      const imported = JSON.parse(await file.text()) as Invoice
      if (!imported.numero || !imported.siniestro_id || !Array.isArray(imported.items)) throw new Error('El archivo no contiene una factura estructurada válida.')
      setInvoice(imported); setError(null)
      addMessage({ role: 'agent', text: `Factura ${imported.numero} adjuntada.`, detail: `${imported.items.length} conceptos listos para revisar.` })
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo leer el adjunto.') }
  }
  const runAgent = async (event: FormEvent) => {
    event.preventDefault()
    if (!prompt.trim() || isWorking) return
    setError(null); setReport(null); setIsWorking(true)
    addMessage({ role: 'user', text: prompt })
    try {
      const result = await runClaimGuardAgent({ prompt, invoice })
      for (const step of result.steps) addMessage({ role: 'activity', text: step.message, detail: [step.tool, step.status].filter(Boolean).join(' · ') })
      if (result.claim) setClaimDetail(`${result.claim.id} · ${result.claim.placa} · ${result.claim.descripcion_dano}`)
      setReport(result.audit)
      addMessage({ role: 'agent', text: result.message })
      if (result.status === 'failed') setError(result.error?.message ?? result.message)
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'No se pudo completar la auditoría.'
      setError(message); addMessage({ role: 'agent', text: 'No pude terminar esa revisión.', detail: message })
    } finally { setIsWorking(false) }
  }
  return <main className="agent-shell"><Header /><section className="agent-layout"><aside className="agent-sidebar"><div><span className="eyebrow">Agente de auditoría</span><h1>Tu analista<br /><em>siempre listo.</em></h1><p>Investiga cargos de taller con fuentes trazables y conclusiones revisables.</p></div><div className="agent-capabilities"><span>Puede ayudarte con</span><button onClick={() => setPrompt('Audita la factura adjunta para el siniestro SIN-001')}>Auditar una factura <Icon name="arrow" size={15} /></button><button onClick={() => setPrompt('¿Qué conceptos están autorizados en el siniestro SIN-001?')}>Consultar un siniestro <Icon name="arrow" size={15} /></button></div><div className="privacy-note"><Icon name="shield" size={17} /><p><b>Revisión responsable</b>El agente no aprueba pagos ni declara fraude.</p></div></aside><section className="chat-surface"><div className="chat-header"><div><span className="agent-avatar"><Icon name="sparkle" size={17} /></span><div><b>ClaimGuard</b><small><span /> Agente conectado</small></div></div><button className="new-chat" onClick={() => { setMessages(initialMessages); setReport(null); setError(null) }}><Icon name="refresh" size={15} /> Nueva conversación</button></div><div className="chat-thread" aria-live="polite">{messages.map((message, index) => message.role === 'activity' ? <div className="tool-event" key={`${message.text}-${index}`}><span><Icon name="check" size={14} /></span><div><b>{message.text}</b><small>{message.detail}</small></div></div> : <article className={`message ${message.role}`} key={`${message.role}-${index}`}><span className="message-avatar">{message.role === 'agent' ? <Icon name="sparkle" size={15} /> : 'Tú'}</span><div><p>{message.text}</p>{message.detail && <small>{message.detail}</small>}</div></article>)}{isWorking && <div className="typing"><i /><i /><i /></div>}{report && <AuditReport report={report} onReset={() => { setReport(null); setPrompt('Audita otra factura para el siniestro SIN-001') }} />}</div><form className="composer" onSubmit={runAgent}><div className="attachment"><input ref={fileInput} type="file" accept="application/json" onChange={(event) => event.target.files?.[0] && importInvoice(event.target.files[0])} /><button type="button" onClick={() => fileInput.current?.click()} aria-label="Adjuntar factura JSON"><Icon name="upload" size={19} /></button><span><b>{invoice.numero}</b><small>{invoice.items.length} conceptos · JSON</small></span><button type="button" className="remove-attachment" onClick={() => setInvoice(sampleInvoice)} aria-label="Restaurar factura de ejemplo">×</button></div><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Pídele algo al agente…" rows={2} /><div className="composer-footer"><span>Usa solo datos sintéticos para la demo.</span><button className="send-button" disabled={isWorking || !prompt.trim()} type="submit">Enviar <Icon name="arrow" size={17} /></button></div></form>{error && <p className="chat-error"><Icon name="alert" size={16} />{error}</p>}</section><aside className="context-panel"><span className="eyebrow">Contexto activo</span><section><div className="context-title"><span className="context-icon"><Icon name="shield" size={17} /></span><div><b>Siniestro</b><small>{claimDetail}</small></div></div><div className="context-divider" /><dl><div><dt>Factura</dt><dd>{invoice.numero}</dd></div><div><dt>Taller</dt><dd>{invoice.taller}</dd></div><div><dt>Conceptos</dt><dd>{invoice.items.length}</dd></div></dl></section><section className="trace-card"><span>TRAZABILIDAD</span><p>Las herramientas y fuentes consultadas aparecen en la conversación.</p></section></aside></section></main>
}
function Header() { return <header className="agent-header"><a className="brand" href="/"><span><Icon name="shield" size={19} /></span>ClaimGuard <b>AI</b></a><div className="header-status"><span />Entorno local seguro</div></header> }
