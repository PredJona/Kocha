export type InvoiceItem = { codigo: string; descripcion: string; cantidad: number; precio_unitario: number }
export type Invoice = { numero: string; siniestro_id: string; taller: string; items: InvoiceItem[] }
export type Finding = { tipo: string; codigo?: string; descripcion?: string; mensaje: string; precio_facturado?: string; precio_maximo?: string; cantidad_apariciones?: number }
export type AuditResponse = { factura: string; estado: 'CORRECTA' | 'CON_INCONSISTENCIAS'; cantidad_inconsistencias: number; inconsistencias: Finding[] }
export type Claim = { id: string; placa: string; descripcion_dano: string; items_autorizados: string[] }
export type AgentStep = { type: 'pdf_text_extracted' | 'invoice_extracted' | 'invoice_validated' | 'model_call' | 'tool_call' | 'response_generated' | 'error'; tool: string | null; status: 'running' | 'completed' | 'failed'; message: string }
export type AgentError = { code: string; message: string }
export type AgentResponse = { status: 'completed' | 'failed'; message: string; steps: AgentStep[]; tool_results: Array<{ call_id: string; tool: string; status: 'success' | 'error'; output: Record<string, unknown> | null; error: AgentError | null; duration_ms: number }>; invoice: Invoice | null; claim: Claim | null; audit: AuditResponse | null; error: AgentError | null }
