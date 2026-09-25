import type { AgentResponse, AuditResponse, Claim, Invoice } from '../types/audit'

const apiUrl = (path: string) => `/api${path}`

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!(init?.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch(apiUrl(path), { ...init, headers })
  } catch {
    throw new Error('No pudimos comunicarnos con el servidor. Comprueba la conexión e inténtalo de nuevo.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null
    const detail = typeof body?.detail === 'string' && body.detail.trim() ? body.detail : null
    throw new Error(detail ?? (response.status === 422 ? 'La factura o solicitud no es válida.' : 'No pudimos comunicarnos con el servidor.'))
  }
  try {
    return await response.json() as T
  } catch {
    throw new Error('La respuesta del servidor no es válida.')
  }
}

export const auditInvoice = (invoice: Invoice) => request<AuditResponse>('/auditar', { method: 'POST', body: JSON.stringify(invoice) })
export const saveInvoice = (invoice: Invoice) => request<{ id: number }>('/facturas', { method: 'POST', body: JSON.stringify(invoice) })
export const getClaim = (id: string) => request<Claim>(`/siniestros/${id}`)
export const runClaimGuardAgent = (body: { prompt: string; invoice: Invoice }) => request<AgentResponse>('/agent', { method: 'POST', body: JSON.stringify(body) })
export const runClaimGuardPdfAgent = (file: File, prompt: string) => {
  const body = new FormData()
  body.append('file', file)
  body.append('prompt', prompt)
  return request<AgentResponse>('/agent/pdf', { method: 'POST', body })
}
