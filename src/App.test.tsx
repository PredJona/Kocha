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

async function submitInvoice() {
  const send = screen.getByRole('button', { name: 'Enviar' }) as HTMLButtonElement
  if (send.disabled) {
    const invoice = { numero: 'FAC-2026-001', siniestro_id: 'SIN-001', taller: 'Taller Aurora', items: [{ codigo: 'REP-001', descripcion: 'Parachoques delantero', cantidad: 1, precio_unitario: 450 }] }
    fireEvent.change(screen.getByLabelText('Adjuntar factura JSON o PDF'), { target: { files: [new File([JSON.stringify(invoice)], 'factura.json', { type: 'application/json' })] } })
    await screen.findByText('Factura FAC-2026-001 adjuntada.')
  }
  fireEvent.click(send)
}

describe('ClaimGuard UI', () => {
  it('muestra el formulario de auditoría inicial', () => {
    render(<App />)
    expect(screen.getByText('Hola, soy Kocha.')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Enviar/i })).toBeTruthy()
  })

  it('envía la factura al agente y muestra únicamente los pasos reales devueltos', async () => {
    const fetchMock = stubAgent(agentResponse)
    render(<App />)

    await submitInvoice()

    await screen.findByText('Revisión lista para una persona.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/agent', expect.objectContaining({ method: 'POST' }))
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('Content-Type')).toBe('application/json')
    expect(body.prompt).toBe('Audita la factura adjunta')
    expect(body.invoice.numero).toBe('FAC-2026-001')
    fireEvent.click(screen.getByText('Ver proceso'))
    expect(screen.getByText('Auditoría ejecutada')).toBeTruthy()
    expect(screen.getByText('Factura validada')).toBeTruthy()
    fireEvent.click(screen.getByText('Ver evidencia'))
    expect(screen.getByText('Precio superior a tarifa.')).toBeTruthy()
    expect(screen.queryByText('Verificando el siniestro')).toBeNull()
  })

  it('muestra una falla controlada y los pasos parciales sin éxito inventado', async () => {
    const fetchMock = stubAgent({ status: 'failed', message: 'No se pudo completar la revisión.', steps: [{ type: 'tool_call', tool: 'get_claim', status: 'failed', message: 'Consulta fallida' }], tool_results: [], claim: null, audit: null, error: { code: 'MODEL_TIMEOUT', message: 'El modelo agotó el tiempo de espera.' } })
    render(<App />)

    await submitInvoice()

    await waitFor(() => expect(screen.getByText('Consulta fallida')).toBeTruthy())
    fireEvent.click(screen.getByText('Ver proceso'))
    expect(screen.getByText('El modelo agotó el tiempo de espera.')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Siniestro confirmado')).toBeNull()
  })

  it('explica una factura inválida devuelta por el backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: [{ loc: ['body', 'invoice'], msg: 'Invalid input' }] }) }))
    render(<App />)

    await submitInvoice()

    await waitFor(() => expect(screen.getAllByText('La factura o solicitud no es válida.').length).toBeGreaterThan(0))
    expect(screen.queryByText('Siniestro confirmado')).toBeNull()
  })

  it('envía un PDF como multipart con file y prompt, y muestra los pasos recibidos en orden', async () => {
    const fetchMock = stubAgent({ ...agentResponse, steps: [
      { type: 'pdf_text_extracted', tool: null, status: 'completed', message: 'Texto del PDF extraído' },
      { type: 'invoice_extracted', tool: null, status: 'completed', message: 'Factura extraída' },
    ] })
    render(<App />)
    const file = new File(['%PDF-1.4'], 'factura-demo.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('Adjuntar factura JSON o PDF'), { target: { files: [file] } })
    expect(screen.getAllByText('factura-demo.pdf').length).toBeGreaterThan(0)
    expect(screen.getByText('1 KB · PDF')).toBeTruthy()
    await submitInvoice()
    await screen.findByText('Revisión lista para una persona.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/agent/pdf')
    expect(init.body).toBeInstanceOf(FormData)
    expect(init.body.get('file')).toBe(file)
    expect(init.body.get('prompt')).toBe('Audita la factura adjunta')
    expect(new Headers(init.headers).has('Content-Type')).toBe(false)
    fireEvent.click(screen.getByText('Ver proceso'))
    const events = document.querySelectorAll('.process-steps li span')
    expect(Array.from(events, (event) => event.textContent)).toEqual(['Documento procesadoTexto del PDF extraído', 'Factura extraída'])
    fireEvent.click(screen.getByText('Ver evidencia'))
    expect(screen.getByText('Precio superior a tarifa.')).toBeTruthy()
    expect(screen.queryByText('Siniestro confirmado')).toBeNull()
  })

  it('reutiliza la factura extraída para una pregunta posterior sobre el PDF', async () => {
    const extractedInvoice = { numero: 'FAC-DEMO-002', siniestro_id: 'SIN-001', taller: 'Taller Aurora', items: [{ codigo: 'REP-001', descripcion: 'Parachoques delantero', cantidad: 1, precio_unitario: 450 }] }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...agentResponse, invoice: extractedInvoice }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ...agentResponse, message: 'Es una factura de reparación de parachoques.', audit: null, invoice: extractedInvoice }) })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Adjuntar factura JSON o PDF'), { target: { files: [new File(['%PDF-1.4'], 'FAC-DEMO-002.pdf', { type: 'application/pdf' })] } })

    await submitInvoice()
    await screen.findByText('Revisión lista para una persona.')
    fireEvent.change(screen.getByLabelText('Pregunta sobre este caso'), { target: { value: '¿Puedes decirme de qué se trata?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))

    await screen.findByText('Es una factura de reparación de parachoques.')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/agent/pdf')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/agent')
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ prompt: '¿Puedes decirme de qué se trata?', invoice: extractedInvoice })
  })

  it('restaura el flujo JSON después de adjuntar un PDF', async () => {
    const fetchMock = stubAgent(agentResponse)
    render(<App />)
    fireEvent.change(screen.getByLabelText('Adjuntar factura JSON o PDF'), { target: { files: [new File(['%PDF'], 'factura.pdf', { type: 'application/pdf' })] } })
    fireEvent.click(screen.getByRole('button', { name: 'Quitar factura adjunta' }))
    await submitInvoice()
    await screen.findByText('Revisión lista para una persona.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/agent')
  })

  it('mantiene el envío JSON cuando se importa una factura JSON', async () => {
    const fetchMock = stubAgent(agentResponse)
    render(<App />)
    const imported = { numero: 'FAC-JSON-002', siniestro_id: 'SIN-001', taller: 'Taller Demo', items: [{ codigo: 'REP-001', descripcion: 'Parachoques', cantidad: 1, precio_unitario: 450 }] }
    fireEvent.change(screen.getByLabelText('Adjuntar factura JSON o PDF'), { target: { files: [new File([JSON.stringify(imported)], 'factura.json', { type: 'application/json' })] } })
    await screen.findByText('Factura FAC-JSON-002 adjuntada.')
    await submitInvoice()
    await screen.findByText('Revisión lista para una persona.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/agent')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).invoice).toEqual(imported)
  })

  it('muestra el estado fallido sin icono de éxito', async () => {
    stubAgent({ ...agentResponse, status: 'failed', audit: null, error: { code: 'PDF_NO_TEXT', message: 'El PDF no contiene texto extraíble.' }, steps: [
      { type: 'error', tool: null, status: 'failed', message: 'No se extrajo texto' },
    ] })
    render(<App />)
    await submitInvoice()
    await screen.findByText('No se extrajo texto')
    fireEvent.click(screen.getByText('Ver proceso'))
    const event = screen.getByText('No se extrajo texto').closest('.step-failed')!
    expect(event.classList.contains('step-failed')).toBe(true)
    expect(event.querySelector('svg path')?.getAttribute('d')).not.toBe('m5 12 4 4L19 6')
    expect(screen.getByText('El PDF no contiene texto extraíble.')).toBeTruthy()
  })

  it('rechaza un adjunto incompatible con un mensaje entendible', () => {
    render(<App />)
    fireEvent.change(screen.getByLabelText('Adjuntar factura JSON o PDF'), { target: { files: [new File(['x'], 'notas.txt', { type: 'text/plain' })] } })
    expect(screen.getByText(/Solo se admiten archivos JSON o PDF/)).toBeTruthy()
  })

  it('distingue visualmente un paso en proceso', async () => {
    stubAgent({ ...agentResponse, steps: [{ type: 'model_call', tool: null, status: 'running', message: 'Consultando al modelo' }] })
    render(<App />)
    await submitInvoice()
    await screen.findByText('Consultando al modelo')
    fireEvent.click(screen.getByText('Ver proceso'))
    const event = screen.getByText('Consultando al modelo').closest('.step-running')!
    expect(event.classList.contains('step-running')).toBe(true)
    expect(event.querySelector('svg path')?.getAttribute('d')).not.toBe('m5 12 4 4L19 6')
  })

  it.each([
    ['PDF_INVALID', 'El PDF no es válido.'],
    ['PDF_NO_TEXT', 'El PDF no contiene texto extraíble.'],
    ['PDF_TOO_LARGE', 'El PDF supera el tamaño permitido.'],
    ['INVOICE_INCOMPLETE', 'La factura está incompleta.'],
    ['INVOICE_UNVERIFIED', 'No se pudo verificar la factura.'],
    ['MODEL_UNAVAILABLE', 'Ollama no está disponible.'],
    ['MODEL_TIMEOUT', 'El modelo agotó el tiempo de espera.'],
    ['MODEL_INVALID_RESPONSE', 'La respuesta del modelo no es válida.'],
  ])('muestra el error controlado %s del backend', async (code, message) => {
    stubAgent({ status: 'failed', message: 'Falló el proceso.', steps: [], tool_results: [], claim: null, audit: null, error: { code, message } })
    render(<App />)
    await submitInvoice()
    await screen.findByText(message)
    expect(screen.queryByText('Factura verificada')).toBeNull()
  })

  it('explica un fallo de red sin mostrar el error interno', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNRESET internal-host.local')))
    render(<App />)
    await submitInvoice()
    await screen.findAllByText(/No pudimos comunicarnos con el servidor/)
    expect(screen.queryByText(/ECONNRESET/)).toBeNull()
  })

  it('muestra el detalle legible de un HTTP 422 al enviar PDF', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: 'El prompt no puede estar vacío.' }) }))
    render(<App />)
    fireEvent.change(screen.getByLabelText('Adjuntar factura JSON o PDF'), { target: { files: [new File(['%PDF'], 'factura.pdf', { type: 'application/pdf' })] } })
    await submitInvoice()
    await screen.findAllByText('El prompt no puede estar vacío.')
  })

  it('oculta un cuerpo de respuesta inesperado del servidor', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => { throw new SyntaxError('Unexpected token < in private response') } }))
    render(<App />)
    await submitInvoice()
    await screen.findAllByText('La respuesta del servidor no es válida.')
    expect(screen.queryByText(/private response/)).toBeNull()
  })

  it('resume el proceso y deja los pasos reales en Ver proceso', async () => {
    stubAgent(agentResponse)
    render(<App />)
    await submitInvoice()
    await screen.findByText('Revisión lista para una persona.')
    expect(screen.getByText(/Auditoría completada/)).toBeTruthy()
    expect(screen.getByText('3 pasos · 3 fuentes')).toBeTruthy()
    expect((document.querySelector('.process-disclosure') as HTMLDetailsElement).open).toBe(false)
    fireEvent.click(screen.getByText('Ver proceso'))
    expect(screen.getByText('Auditoría ejecutada')).toBeTruthy()
    expect((document.querySelector('.process-disclosure') as HTMLDetailsElement).open).toBe(true)
    expect(screen.queryByText('Siniestro consultado')).toBeNull()
  })

  it('muestra importes y diferencia derivados del hallazgo real', async () => {
    stubAgent({ ...agentResponse, audit: { ...agentResponse.audit, inconsistencias: [{ tipo: 'PRECIO_SUPERA_TARIFA', codigo: 'REP-001', mensaje: 'Precio superior a tarifa.', precio_facturado: '450.00', precio_maximo: '300.00' }] } })
    render(<App />)
    await submitInvoice()
    await screen.findByText('Requiere revisión humana')
    expect(screen.getByText('B/.450.00')).toBeTruthy()
    expect(screen.getByText('B/.300.00')).toBeTruthy()
    expect(screen.getByText('+B/.150.00')).toBeTruthy()
    fireEvent.click(screen.getByText('Ver evidencia'))
    expect(screen.getByText('Precio superior a tarifa.')).toBeTruthy()
  })

  it('mantiene visible el caso activo sin declarar fuentes no consultadas', async () => {
    stubAgent({ ...agentResponse, steps: [], audit: null })
    render(<App />)
    expect(screen.getByText('Caso activo')).toBeTruthy()
    await submitInvoice()
    await screen.findByText('Revisión lista para una persona.')
    expect(screen.queryByText('Tarifario consultado')).toBeNull()
  })

  it('inicia sin factura adjunta ni caso de ejemplo', () => {
    render(<App />)
    expect(screen.queryByText('FAC-2026-001')).toBeNull()
    expect(screen.queryByText('Taller Aurora')).toBeNull()
    expect(screen.getByText('Sin factura adjunta')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Enviar' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('Nueva auditoría retira el PDF y deja el caso vacío', () => {
    render(<App />)
    fireEvent.change(screen.getByLabelText('Adjuntar factura JSON o PDF'), { target: { files: [new File(['%PDF'], 'factura.pdf', { type: 'application/pdf' })] } })
    fireEvent.click(screen.getByRole('button', { name: 'Nueva auditoría' }))
    expect(screen.queryByText('factura.pdf')).toBeNull()
    expect(screen.getByText('Sin factura adjunta')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Enviar' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
