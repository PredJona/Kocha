import { useRef, useState, type FormEvent } from 'react'
import { AuditReport } from './components/AuditReport'
import { Icon } from './components/Icon'
import { consultedSources, ProcessTrace } from './components/ProcessTrace'
import { runClaimGuardAgent, runClaimGuardPdfAgent } from './services/api'
import type { AgentResponse, Invoice } from './types/audit'

type ChatMessage = { role: 'agent' | 'user'; text: string; detail?: string }
const initialMessages: ChatMessage[] = [{ role: 'agent', text: 'Hola, soy Kocha.', detail: 'Adjunta una factura JSON o PDF para revisar el siniestro y el tarifario.' }]

function fileSize(size: number) { return size >= 1024 * 1024 ? `${(size / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(size / 1024))} KB` }

export default function App() {
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [prompt, setPrompt] = useState('Audita la factura adjunta')
  const [isWorking, setIsWorking] = useState(false)
  const [result, setResult] = useState<AgentResponse | null>(null)
  const report = result?.audit ?? null
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const addMessage = (message: ChatMessage) => setMessages((current) => [...current, message])
  const reset = () => { setInvoice(null); setPdfFile(null); setMessages(initialMessages); setResult(null); setError(null); setPrompt('Audita la factura adjunta') }
  const attachFile = (file: File) => {
    if (file.type === 'application/pdf' || (file.type === '' && file.name.toLowerCase().endsWith('.pdf'))) {
      setPdfFile(file); setError(null); setResult(null)
    } else if (file.type === 'application/json' || (file.type === '' && file.name.toLowerCase().endsWith('.json'))) {
      void importInvoice(file)
    } else {
      setError('Solo se admiten archivos JSON o PDF.')
    }
    if (fileInput.current) fileInput.current.value = ''
  }
  const importInvoice = async (file: File) => {
    try {
      const imported = JSON.parse(await file.text()) as Invoice
      if (!imported.numero || !imported.siniestro_id || !Array.isArray(imported.items)) throw new Error('El archivo no contiene una factura estructurada válida.')
      setInvoice(imported); setPdfFile(null); setError(null); setResult(null)
      addMessage({ role: 'agent', text: `Factura ${imported.numero} adjuntada.`, detail: `${imported.items.length} conceptos listos para revisar.` })
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo leer el adjunto.') }
  }
  const runAgent = async (event: FormEvent) => {
    event.preventDefault()
    if (!prompt.trim() || isWorking || (!pdfFile && !invoice)) return
    setError(null); setResult(null); setIsWorking(true)
    addMessage({ role: 'user', text: prompt })
    try {
      const response = pdfFile ? await runClaimGuardPdfAgent(pdfFile, prompt) : await runClaimGuardAgent({ prompt, invoice: invoice! })
      setResult(response)
      addMessage({ role: 'agent', text: response.message })
      if (response.status === 'failed') setError(response.error?.message ?? response.message)
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'No se pudo completar la auditoría.'
      setError(message); addMessage({ role: 'agent', text: 'No pude terminar esa revisión.', detail: message })
    } finally { setIsWorking(false) }
  }
  const caseInvoice = report?.factura ?? (pdfFile ? pdfFile.name : invoice?.numero ?? 'Sin factura adjunta')
  const caseClaim = result?.claim?.id ?? (pdfFile ? 'Pendiente de consulta' : invoice?.siniestro_id ?? 'Sin siniestro')
  const caseWorkshop = pdfFile ? 'Pendiente de extracción' : invoice?.taller ?? 'Sin taller'
  const sources = result ? consultedSources(result) : (pdfFile || invoice ? ['Factura'] : [])
  const caseState = result?.status === 'failed' ? 'No validado' : report?.estado === 'CON_INCONSISTENCIAS' ? 'En revisión' : report?.estado === 'CORRECTA' ? 'Sin observaciones' : pdfFile || invoice ? 'Pendiente' : 'Sin caso activo'

  return <main className="workspace">
    <aside className="left-sidebar" aria-label="Navegación de auditorías">
      <div className="sidebar-brand"><span className="brand-mark"><Icon name="sparkle" size={21} /></span><strong>Kocha</strong></div>
      <button className="new-audit" type="button" onClick={reset}><Icon name="plus" size={18} /> Nueva auditoría</button>
      <div className="sidebar-section-title">Auditorías recientes</div>
      {result ? <div className="recent-item" aria-current="page"><Icon name="file" size={18} /><div><strong>{caseInvoice}</strong><small>{report ? `${report.cantidad_inconsistencias} ${report.cantidad_inconsistencias === 1 ? 'inconsistencia' : 'inconsistencias'}` : 'Consulta actual'}</small></div></div> : <p className="empty-recent">Sin auditorías en esta sesión.</p>}
    </aside>

    <section className="main-workspace" aria-label="Conversación de auditoría">
      <header className="workspace-header"><span className="agent-avatar"><Icon name="sparkle" size={20} /></span><div><strong>Kocha</strong><small><span className="status-dot" /> Agente auditor · Conectado</small></div></header>
      <div className="conversation" aria-live="polite">
        {messages.map((message, index) => <article className={`message message-${message.role}`} key={`${message.role}-${index}`}>
          {message.role === 'agent' && <span className="message-avatar"><Icon name="sparkle" size={16} /></span>}
          <div className="message-body"><p>{message.text}</p>{message.detail && <small>{message.detail}</small>}</div>
          {message.role === 'user' && <span className="user-avatar">Tú</span>}
        </article>)}
        {isWorking && <div className="working-status" role="status"><span className="working-pulse" /> Analizando factura...</div>}
        {report && <AuditReport report={report} onReset={reset} />}
        {result && <ProcessTrace result={result} />}
      </div>
      <form className="composer" onSubmit={runAgent}>
        <input ref={fileInput} type="file" aria-label="Adjuntar factura JSON o PDF" accept="application/json,application/pdf,.json,.pdf" onChange={(event) => event.target.files?.[0] && attachFile(event.target.files[0])} />
        {pdfFile || invoice ? <div className="attachment-chip"><Icon name="file" size={18} /><div><strong>{pdfFile ? pdfFile.name : invoice?.numero}</strong><small>{pdfFile ? `${fileSize(pdfFile.size)} · PDF` : `${invoice?.items.length} conceptos · JSON`}</small></div><button type="button" onClick={() => { setInvoice(null); setPdfFile(null); setError(null); setResult(null) }} aria-label="Quitar factura adjunta">×</button></div> : <p className="empty-attachment">Adjunta una factura JSON o PDF para comenzar.</p>}
        <div className="composer-row"><button type="button" className="attach-button" onClick={() => fileInput.current?.click()} aria-label="Seleccionar factura JSON o PDF"><Icon name="upload" size={19} /></button><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Pregunta sobre este caso..." rows={1} aria-label="Pregunta sobre este caso" /><button className="send-button" disabled={isWorking || !prompt.trim() || (!pdfFile && !invoice)} type="submit" aria-label="Enviar"><Icon name="arrow" size={18} /></button></div>
      </form>
      {error && <p className="chat-error" role="alert"><Icon name="alert" size={16} />{error}</p>}
    </section>

    <aside className="right-inspector" aria-label="Inspector del caso">
      <div className="inspector-status"><span className="status-dot" /> Entorno local seguro</div>
      <section className="inspector-section"><h2><Icon name="file" size={18} /> Caso activo</h2><dl><div><dt>Siniestro</dt><dd>{caseClaim}</dd></div><div><dt>Factura</dt><dd>{caseInvoice}</dd></div><div><dt>Taller</dt><dd>{caseWorkshop}</dd></div><div><dt>Estado</dt><dd className={`case-state ${report?.estado === 'CON_INCONSISTENCIAS' ? 'case-warning' : report?.estado === 'CORRECTA' ? 'case-clear' : ''}`}>{caseState}</dd></div></dl></section>
      <section className="inspector-section"><h2><Icon name="shield" size={18} /> Fuentes</h2><ul className="source-list">{['Factura', 'Siniestro', 'Tarifario'].map((source) => <li key={source}><span>{source}</span><small className={sources.includes(source) ? 'source-used' : ''}>{sources.includes(source) ? 'Disponible' : 'Sin consultar'}</small></li>)}</ul></section>
      <section className="inspector-section inspector-trace"><h2><Icon name="clock" size={18} /> Trazabilidad</h2><p>{result ? 'Abre “Ver proceso” en la conversación para revisar los pasos y detalles técnicos devueltos por el agente.' : 'Los pasos y fuentes consultadas aparecerán al ejecutar la auditoría.'}</p></section>
    </aside>
  </main>
}
