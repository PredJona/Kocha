import type { AgentResponse, AgentStep } from '../types/audit'
import { Icon } from './Icon'

function stepLabel(step: AgentStep): string {
  if (step.status !== 'completed') return step.message
  if (step.type === 'pdf_text_extracted') return 'Documento procesado'
  if (step.type === 'invoice_extracted') return 'Factura extraída'
  if (step.type === 'invoice_validated') return 'Factura validada'
  if (step.type === 'response_generated') return 'Resultado generado'
  if (step.type === 'tool_call' && step.tool === 'get_claim') return 'Siniestro consultado'
  if (step.type === 'tool_call' && step.tool === 'get_tariff') return 'Tarifario consultado'
  if (step.type === 'tool_call' && step.tool === 'audit_invoice') return 'Conceptos comparados'
  return step.message
}

export function consultedSources(result: AgentResponse | null): string[] {
  if (!result) return []
  const sources = ['Factura']
  if (result.audit || result.claim || result.tool_results.some((item) => item.tool === 'get_claim' && item.status === 'success')) sources.push('Siniestro')
  if ((result.audit && !result.audit.inconsistencias.some((finding) => finding.tipo === 'SINIESTRO_NO_ENCONTRADO')) || result.tool_results.some((item) => item.tool === 'get_tariff' && item.status === 'success')) sources.push('Tarifario')
  return sources
}

export function ProcessTrace({ result }: { result: AgentResponse }) {
  const sources = consultedSources(result)
  return <section className={`process-trace process-${result.status}`} aria-label="Proceso de auditoría">
    <div className="process-summary">
      <Icon name={result.status === 'completed' ? 'check' : 'alert'} size={18} />
      <div><strong>{result.status === 'failed' ? 'Proceso no completado' : result.audit ? 'Auditoría completada' : 'Consulta completada'}</strong><small>{result.steps.length} pasos · {sources.length} {sources.length === 1 ? 'fuente' : 'fuentes'}</small></div>
    </div>
    {result.steps.length > 0 && <details className="process-disclosure"><summary>Ver proceso <Icon name="arrow" size={15} /></summary>
      <ol className="process-steps">{result.steps.map((step, index) => <li key={`${step.type}-${index}`} className={`step-${step.status}`}>
        <Icon name={step.status === 'failed' ? 'alert' : step.status === 'running' ? 'clock' : 'check'} size={15} />
        <span>{stepLabel(step)}{stepLabel(step) !== step.message && <small>{step.message}</small>}</span>
      </li>)}</ol>
      <details className="technical-details"><summary>Detalles técnicos</summary><ul>{result.steps.map((step, index) => <li key={`${step.type}-${index}`}>{step.type}{step.tool ? ` · ${step.tool}` : ''} · {step.status}</li>)}</ul></details>
    </details>}
  </section>
}
