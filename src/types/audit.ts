export type InvoiceItem = { codigo: string; descripcion: string; cantidad: number; precio_unitario: number }
export type Invoice = { numero: string; siniestro_id: string; taller: string; items: InvoiceItem[] }
export type Finding = { tipo: string; codigo?: string; descripcion?: string; mensaje: string; precio_facturado?: string; precio_maximo?: string; cantidad_apariciones?: number }
export type AuditResponse = { factura: string; estado: 'CORRECTA' | 'CON_INCONSISTENCIAS'; cantidad_inconsistencias: number; inconsistencias: Finding[] }
export type Claim = { id: string; placa: string; descripcion_dano: string; items_autorizados: string[] }
