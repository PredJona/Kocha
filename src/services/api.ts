import type { AgentResponse, AuditResponse, Claim, Invoice } from '../types/audit'

const apiUrl = (path: string) => `/api${path}`

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), { headers: { 'Content-Type': 'application/json', ...init?.headers }, ...init })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null
    const detail = typeof body?.detail === 'string' && body.detail.trim() ? body.detail : null
    throw new Error(detail ?? (response.status === 422 ? 'La factura o solicitud no es válida.' : 'No pudimos comunicarnos con el servidor.'))
  }
  return response.json() as Promise<T>
}

export const auditInvoice = (invoice: Invoice) => request<AuditResponse>('/auditar', { method: 'POST', body: JSON.stringify(invoice) })
export const saveInvoice = (invoice: Invoice) => request<{ id: number }>('/facturas', { method: 'POST', body: JSON.stringify(invoice) })
export const getClaim = (id: string) => request<Claim>(`/siniestros/${id}`)
export const runClaimGuardAgent = (body: { prompt: string; invoice: Invoice }) => request<AgentResponse>('/agent', { method: 'POST', body: JSON.stringify(body) })
