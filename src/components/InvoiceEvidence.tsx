import { Icon } from './Icon'
import type { Invoice } from '../types/audit'

function money(value: number) {
  return `B/.${Number(value).toFixed(2)}`
}

export function InvoiceEvidence({ invoice }: { invoice: Invoice }) {
  return <section className="invoice-evidence" aria-label="Evidencia de factura">
    <div className="invoice-evidence-heading">
      <span className="invoice-evidence-icon"><Icon name="file" size={18} /></span>
      <div>
        <strong>Factura extraída</strong>
        <small><span>{invoice.numero}</span><span>{invoice.items.length} conceptos extraídos</span></small>
      </div>
    </div>
    <details className="invoice-evidence-details">
      <summary>Ver datos extraídos <Icon name="arrow" size={13} /></summary>
      <dl>
        <div><dt>Reclamo</dt><dd>{invoice.siniestro_id}</dd></div>
        <div><dt>Taller</dt><dd>{invoice.taller}</dd></div>
      </dl>
      <ul>
        {invoice.items.map((item, index) => <li key={`${item.codigo}-${index}`}>
          <div><code>{item.codigo}</code><span>{item.descripcion}</span></div>
          <div className="invoice-evidence-amount"><small>{item.cantidad} ×</small><strong>{money(item.precio_unitario)}</strong></div>
        </li>)}
      </ul>
    </details>
  </section>
}
