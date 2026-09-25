import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const agentResponse = {
  status: 'completed',
  message: 'Revisión lista para una persona.',
  steps: [
    { type: 'invoice_validated', tool: null, status: 'completed', message: 'Factura validada' },
    { type: 'tool_call', tool: 'audit_invoice', status: 'completed', message: 'Auditoría ejecutada' },
    { type: 'response_generated', tool: null, status: 'completed', message: 'Respuesta generada' },
  ],
  tool_results: [],
  claim: null,
  audit: { factura: 'FAC-2026-001', estado: 'CON_INCONSISTENCIAS', cantidad_inconsistencias: 1, inconsistencias: [{ tipo: 'PRECIO_SUPERA_TARIFA', codigo: 'REP-001', mensaje: 'Precio superior a tarifa.' }] },
  error: null,
}

function stubAgent(payload: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => payload })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('ClaimGuard UI', () => {
  it('muestra el formulario de auditoría inicial', () => {
    render(<App />)
    expect(screen.getByText('Hola, soy ClaimGuard.')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Enviar/i })).toBeTruthy()
  })

  it('envía la factura al agente y muestra únicamente los pasos reales devueltos', async () => {
    const fetchMock = stubAgent(agentResponse)
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: /Enviar/i }))

    await screen.findByText('Revisión lista para una persona.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/agent', expect.objectContaining({ method: 'POST' }))
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.prompt).toBe('Audita la factura adjunta para el siniestro SIN-001')
    expect(body.invoice.numero).toBe('FAC-2026-001')
    expect(screen.getByText('Auditoría ejecutada')).toBeTruthy()
    expect(screen.getByText('Factura validada')).toBeTruthy()
    expect(screen.getByText('Precio superior a tarifa.')).toBeTruthy()
    expect(screen.queryByText('Verificando el siniestro')).toBeNull()
  })

  it('muestra una falla controlada y los pasos parciales sin éxito inventado', async () => {
    const fetchMock = stubAgent({ status: 'failed', message: 'No se pudo completar la revisión.', steps: [{ type: 'tool_call', tool: 'get_claim', status: 'failed', message: 'Consulta fallida' }], tool_results: [], claim: null, audit: null, error: { code: 'MODEL_TIMEOUT', message: 'El modelo agotó el tiempo de espera.' } })
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: /Enviar/i }))

    await waitFor(() => expect(screen.getByText('Consulta fallida')).toBeTruthy())
    expect(screen.getByText('El modelo agotó el tiempo de espera.')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Siniestro confirmado')).toBeNull()
  })
})
