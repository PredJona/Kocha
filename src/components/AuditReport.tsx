import type { AuditResponse, Finding } from '../types/audit'
import { Icon } from './Icon'

const labels: Record<string, string> = { ITEM_DUPLICADO: 'Posible duplicado', PRECIO_SUPERA_TARIFA: 'Precio superior al permitido', ITEM_SIN_TARIFA: 'Concepto sin tarifa', ITEM_NO_CORRESPONDE_SINIESTRO: 'Revisar cobertura', SINIESTRO_NO_ENCONTRADO: 'Siniestro no encontrado' }

function money(value: string): string | null {
  const amount = Number(value)
  return Number.isFinite(amount) ? `B/.${amount.toFixed(2)}` : null
}

function FindingCard({ finding }: { finding: Finding }) {
  const billed = finding.precio_facturado ? money(finding.precio_facturado) : null
  const allowed = finding.precio_maximo ? money(finding.precio_maximo) : null
  const difference = billed && allowed ? money(((Math.round(Number(finding.precio_facturado) * 100) - Math.round(Number(finding.precio_maximo) * 100)) / 100).toFixed(2)) : null
  return <article className="finding">
    <div className="finding-heading"><div><span className="finding-kind">{labels[finding.tipo] ?? 'Posible inconsistencia'}</span><h3>{finding.descripcion ?? finding.codigo ?? labels[finding.tipo] ?? 'Hallazgo'}</h3>{finding.descripcion && finding.codigo && <code>{finding.codigo}</code>}</div><span className="review-label">Revisión humana</span></div>
    {billed && allowed && <div className="amount-grid"><div><span>Facturado</span><strong>{billed}</strong></div><div><span>Permitido</span><strong>{allowed}</strong></div><div className="difference"><span>Diferencia</span><strong>{difference && !difference.startsWith('B/.-') ? '+' : ''}{difference}</strong></div></div>}
    <details className="evidence-details"><summary>Ver evidencia <Icon name="arrow" size={15} /></summary><p>{finding.mensaje}</p>{finding.cantidad_apariciones && <small>{finding.cantidad_apariciones} apariciones en la factura.</small>}</details>
  </article>
}

export function AuditReport({ report, onReset }: { report: AuditResponse; onReset: () => void }) {
  const clear = report.estado === 'CORRECTA'
  return <section className="report-panel" aria-live="polite" aria-label="Resultado de auditoría">
    <div className="report-heading"><span className="report-icon"><Icon name="file" size={20} /></span><div><span className="eyebrow">Resultado de auditoría</span><p>Factura {report.factura}</p></div></div>
    <div className={`outcome ${clear ? 'outcome-clear' : 'outcome-warning'}`}><Icon name={clear ? 'check' : 'alert'} size={23} /><div><h2>{clear ? 'Sin observaciones relevantes' : `${report.cantidad_inconsistencias} ${report.cantidad_inconsistencias === 1 ? 'inconsistencia detectada' : 'inconsistencias detectadas'}`}</h2><p>{clear ? 'No se encontraron inconsistencias con las reglas disponibles.' : 'Requiere revisión humana'}</p></div></div>
    {!clear && <div className="findings">{report.inconsistencias.map((finding, index) => <FindingCard key={`${finding.tipo}-${finding.codigo ?? index}-${index}`} finding={finding} />)}</div>}
    <div className="report-footer"><p>Los hallazgos orientan la revisión. Kocha no toma decisiones de pago ni determina fraude.</p><button type="button" onClick={onReset}>Nueva auditoría</button></div>
  </section>
}
