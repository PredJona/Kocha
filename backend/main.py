import sqlite3

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.auditoria import auditar_factura
from backend.agent.extractors.invoice_extractor import InvoiceExtractor
from backend.agent.extractors.pdf_extractor import MAX_PDF_BYTES
from backend.agent.factory import get_agent_orchestrator, get_invoice_extractor
from backend.agent.orchestrator import AgentOrchestrator
from backend.agent.pdf_pipeline import run_pdf_agent
from backend.agent.schemas import AgentRequest, AgentResponse
from backend.database import (
    crear_tablas,
    guardar_factura,
    listar_tarifas,
    obtener_siniestro,
)
from backend.schemas import Factura, ItemFactura


app = FastAPI(
    title="Kocha - Auditor de Facturación",
    version="1.5.0"
)


crear_tablas()


@app.get("/")
def inicio():
    return {
        "mensaje": (
            "Backend del Reto 2 funcionando"
        ),
        "version": "1.4"
    }


@app.post("/facturas")
def recibir_factura(
    factura: Factura
):
    try:
        factura_id = guardar_factura(
            factura
        )

        return {
            "mensaje": (
                "Factura guardada correctamente"
            ),
            "id": factura_id,
            "numero": factura.numero
        }

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=(
                "La factura ya fue registrada "
                "anteriormente"
            )
        )


@app.get("/tarifas")
def obtener_tarifas():
    return listar_tarifas()


@app.get(
    "/siniestros/{siniestro_id}"
)
def consultar_siniestro(
    siniestro_id: str
):
    siniestro = obtener_siniestro(
        siniestro_id
    )

    if siniestro is None:
        raise HTTPException(
            status_code=404,
            detail="Siniestro no encontrado"
        )

    return siniestro


@app.post("/auditar")
def auditar(
    factura: Factura
):
    inconsistencias = auditar_factura(
        factura
    )

    if inconsistencias:
        estado = "CON_INCONSISTENCIAS"

    else:
        estado = "CORRECTA"

    return {
        "factura": factura.numero,
        "estado": estado,
        "cantidad_inconsistencias": (
            len(inconsistencias)
        ),
        "inconsistencias": inconsistencias
    }


@app.post("/agent", response_model=AgentResponse)
def ejecutar_agente(
    request: AgentRequest,
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
) -> AgentResponse:
    return orchestrator.run(request)


@app.post("/agent/pdf", response_model=AgentResponse)
async def ejecutar_agente_pdf(
    file: UploadFile = File(...),
    prompt: str = Form(..., min_length=1),
    invoice_extractor: InvoiceExtractor = Depends(get_invoice_extractor),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
) -> AgentResponse:
    if not prompt.strip():
        raise HTTPException(status_code=422, detail="El prompt no puede estar vacío.")
    pdf_bytes = await file.read(MAX_PDF_BYTES + 1)
    return await run_in_threadpool(run_pdf_agent, pdf_bytes, prompt, invoice_extractor, orchestrator)
