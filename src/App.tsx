import { useRef, useState, type FormEvent } from 'react'
import { AuditReport } from './components/AuditReport'
import { Icon } from './components/Icon'
import { runClaimGuardAgent, runClaimGuardPdfAgent } from './services/api'
import type { AgentStep, AuditResponse, Invoice } from './types/audit'

type ChatMessage = { role: 'agent' | 'user' | 'activity'; text: string; detail?: string; status?: AgentStep['status'] }
const sampleInvoice: Invoice = { numero: 'FAC-2026-001', siniestro_id: 'SIN-001', taller: 'Taller Aurora', items: [{ codigo: 'REP-001', descripcion: 'Parachoques delantero', cantidad: 1, precio_unitario: 450 }, { codigo: 'MAN-001', descripcion: 'Mano de obra', cantidad: 1, precio_unitario: 50 }] }
const initialMessages: ChatMessage[] = [{ role: 'agent', text: 'Hola, soy ClaimGuard.', detail: 'Puedo revisar una factura contra el siniestro y el tarifario. Adjunta una factura o dime qué quieres investigar.' }]

export default function App() {
  const [invoice, setInvoice] = useState<Invoice>(sampleInvoice)
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [prompt, setPrompt] = useState('Audita la factura adjunta para el siniestro SIN-001')
  const [isWorking, setIsWorking] = useState(false)
  const [report, setReport] = useState<AuditResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [claimDetail, setClaimDetail] = useState('Siniestro SIN-001 · Pendiente de consulta')
  const fileInput = useRef<HTMLInputElement>(null)
  const addMessage = (message: ChatMessage) => setMessages((current) => [...current, message])
  const attachFile = (file: File) => {
    if (file.type === 'application/pdf' || (file.type === '' && file.name.toLowerCase().endsWith('.pdf'))) {
      setPdfFile(file); setError(null)
    } else if (file.type === 'application/json' || (file.type === '' && file.name.toLowerCase().endsWith('.json'))) void importInvoice(file)
    else setError('Solo se admiten archivos JSON o PDF.')
    if (fileInput.current) fileInput.current.value = ''
  }
  const importInvoice = async (file: File) => {
    try {
      const imported = JSON.parse(await file.text()) as Invoice
      if (!imported.numero || !imported.siniestro_id || !Array.isArray(imported.items)) throw new Error('El archivo no contiene una factura estructurada válida.')
      setInvoice(imported); setPdfFile(null); setError(null)
      addMessage({ role: 'agent', text: `Factura ${imported.numero} adjuntada.`, detail: `${imported.items.length} conceptos listos para revisar.` })
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo leer el adjunto.') }
  }
  const runAgent = async (event: FormEvent) => {
    event.preventDefault()
    if (!prompt.trim() || isWorking) return
    setError(null); setReport(null); setIsWorking(true)
    addMessage({ role: 'user', text: prompt })
    try {
      const result = pdfFile ? await runClaimGuardPdfAgent(pdfFile, prompt) : await runClaimGuardAgent({ prompt, invoice })
      for (const step of result.steps) addMessage({ role: 'activity', text: step.message, detail: [step.tool, step.status].filter(Boolean).join(' · '), status: step.status })
      if (result.claim) setClaimDetail(`${result.claim.id} · ${result.claim.placa} · ${result.claim.descripcion_dano}`)
      setReport(result.audit)
      addMessage({ role: 'agent', text: result.message })
      if (result.status === 'failed') setError(result.error?.message ?? result.message)
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'No se pudo completar la auditoría.'
      setError(message); addMessage({ role: 'agent', text: 'No pude terminar esa revisión.', detail: message })
    } finally { setIsWorking(false) }
  }
  return <main className="agent-shell"><Header /><section className="agent-layout"><aside className="agent-sidebar"><span className="eyebrow">Agente de auditoría</span><h1>Tu analista<br /><em>siempre listo.</em></h1><p>Investiga cargos de taller con fuentes trazables y conclusiones revisables.</p></aside><section className="chat-surface"><div className="chat-header"><div><span className="agent-avatar"><Icon name="sparkle" size={17} /></span><div><b>ClaimGuard</b><small><span /> Agente conectado</small></div></div><button className="new-chat" onClick={() => { setMessages(initialMessages); setReport(null); setError(null) }}><Icon name="refresh" size={15} /> Nueva conversación</button></div><div className="chat-thread" aria-live="polite">{messages.map((message, index) => message.role === 'activity' ? <div className={`tool-event tool-event-${message.status ?? 'completed'}`} key={`${message.text}-${index}`}><span><Icon name={message.status === 'failed' ? 'alert' : 'check'} size={14} /></span><div><b>{message.text}</b><small>{message.detail}</small></div></div> : <article className={`message ${message.role}`} key={`${message.role}-${index}`}><span className="message-avatar">{message.role === 'agent' ? <Icon name="sparkle" size={15} /> : 'Tú'}</span><div><p>{message.text}</p>{message.detail && <small>{message.detail}</small>}</div></article>)}{isWorking && <div className="typing"><i /><i /><i /></div>}{report && <AuditReport report={report} onReset={() => { setReport(null); setPrompt('Audita otra factura para el siniestro SIN-001') }} />}</div><form className="composer" onSubmit={runAgent}><div className="attachment"><input ref={fileInput} type="file" aria-label="Adjuntar factura JSON o PDF" accept="application/json,application/pdf,.json,.pdf" onChange={(event) => event.target.files?.[0] && attachFile(event.target.files[0])} /><button type="button" onClick={() => fileInput.current?.click()} aria-label="Seleccionar factura JSON o PDF"><Icon name="upload" size={19} /></button><span><b>{pdfFile ? pdfFile.name : invoice.numero}</b><small>{pdfFile ? 'PDF' : `${invoice.items.length} conceptos · JSON`}</small></span><button type="button" className="remove-attachment" onClick={() => { setInvoice(sampleInvoice); setPdfFile(null); setError(null) }} aria-label="Restaurar factura de ejemplo">×</button></div><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Pídele algo al agente…" rows={2} /><div className="composer-footer"><span>Usa solo datos sintéticos para la demo.</span><button className="send-button" disabled={isWorking || !prompt.trim()} type="submit">Enviar <Icon name="arrow" size={17} /></button></div></form>{error && <p className="chat-error"><Icon name="alert" size={16} />{error}</p>}</section><aside className="context-panel"><span className="eyebrow">Contexto activo</span><section><dl><div><dt>Siniestro</dt><dd>{claimDetail}</dd></div><div><dt>Factura</dt><dd>{pdfFile ? pdfFile.name : invoice.numero}</dd></div><div><dt>Taller</dt><dd>{pdfFile ? 'Pendiente de extracción' : invoice.taller}</dd></div><div><dt>Conceptos</dt><dd>{pdfFile ? 'Pendiente de extracción' : invoice.items.length}</dd></div></dl></section><section className="trace-card"><span>TRAZABILIDAD</span><p>Las herramientas y fuentes consultadas aparecen en la conversación.</p></section></aside></section></main>
}
function Header() { return <header className="agent-header"><a className="brand" href="/"><span><Icon name="shield" size={19} /></span>ClaimGuard <b>AI</b></a><div className="header-status"><span />Entorno local seguro</div></header> }
