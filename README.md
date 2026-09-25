# ClaimGuard AI

Auditor de facturación de siniestros para revisar conceptos de taller contra un
tarifario y los ítems autorizados del siniestro. Los resultados son hallazgos
para revisión humana; la aplicación no aprueba pagos ni afirma fraude.

## Ejecutar el proyecto

En una terminal, desde la raíz del proyecto:

```bash
# Terminal 1: API FastAPI
python3 -m pip install -r backend/requirements.txt
uvicorn backend.main:app --reload

# Terminal 2: interfaz React
npm install
npm run dev
```

Abre la URL que muestra Vite (normalmente `http://localhost:5173`). El
frontend redirige las llamadas `/api/*` al backend local en el puerto 8000.

## Verificar el frontend

```bash
npm run build
npm test
```

## Agente local (factura JSON o PDF con texto)

Instala Python 3.12, [Ollama](https://docs.ollama.com/quickstart) y Node.js 22. Desde la raíz del repositorio:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm ci
```

Inicia Ollama con `ollama serve` si aún no está ejecutándose. Instala un modelo local compatible con salida JSON estructurada, por ejemplo `ollama pull qwen2.5:3b`. El modelo se elige con variables de entorno; no hace falta cambiar código:

```bash
export OLLAMA_HOST=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen2.5:3b
export OLLAMA_TIMEOUT=120
.venv/bin/uvicorn backend.main:app --reload
```

En otra terminal, ejecuta `npm run dev` para usar la interfaz. También puedes probar el contrato del agente directamente con una factura sintética:

```bash
curl -sS http://127.0.0.1:8000/agent -H 'Content-Type: application/json' -d '{"prompt":"Audita esta factura","invoice":{"numero":"FAC-DEMO-001","siniestro_id":"SIN-001","taller":"Taller de prueba","items":[{"codigo":"REP-001","descripcion":"Parachoques delantero","cantidad":1,"precio_unitario":450}]}}'
```

Para una factura PDF pequeña que contenga texto seleccionable:

```bash
curl -F file=@invoice.pdf -F 'prompt=Audita esta factura' http://127.0.0.1:8000/agent/pdf
```

`/agent/pdf` acepta PDFs de hasta 5 MiB y 20 páginas, extrae como máximo 30 000 caracteres, valida los campos obtenidos y ejecuta la misma auditoría del agente JSON. Requiere texto incrustado: no hace OCR de imágenes o escaneos. Los errores de lectura y extracción devuelven un resultado controlado sin ejecutar la auditoría.

La respuesta incluye la explicación, los resultados obtenidos y una lista de pasos ejecutados por el backend. El agente presenta hallazgos para revisión humana; no aprueba pagos ni declara fraude.

```bash
.venv/bin/python -m pytest -v
npm test
npm run build
```

Las pruebas automatizadas y CI sustituyen únicamente el límite externo de Ollama por respuestas controladas; usan extracción PDF, SQLite y reglas de auditoría reales sin requerir servidor ni modelo local. Los `curl` anteriores son **pruebas opcionales de integración local con Ollama real**, independientes de CI. Si Ollama no responde, comprueba que esté iniciado, que `OLLAMA_MODEL` coincida con `ollama list` y que `OLLAMA_HOST` apunte al servidor correcto. Para cambiar de modelo basta con instalarlo mediante `ollama pull <nombre>` y ajustar `OLLAMA_MODEL`.

## Flujo disponible hoy

1. Selecciona el siniestro sintético `SIN-001`.
2. Usa la factura JSON de ejemplo o adjunta una factura JSON o PDF con texto seleccionable.
3. Ejecuta la auditoría y revisa cargos duplicados, conceptos fuera del
   siniestro y precios superiores a la tarifa.

La interfaz envía JSON a `/api/agent` y PDF como multipart (`file` y `prompt`) a `/api/agent/pdf`. Muestra la trazabilidad y el informe de auditoría devueltos por el backend. Los PDF escaneados sin texto seleccionable no son compatibles. El contrato `/api/v1/audits` aún no está implementado.

## Git para el equipo

Cada tarea debe hacerse en una rama y enviarse como Pull Request:

```bash
git switch -c nombre-de-tu-rama
git add .
git commit -m "Añade interfaz de auditoría"
git push -u origin nombre-de-tu-rama
```

Después, abre el enlace que GitHub imprime y crea el Pull Request hacia
`main`. No subas `.env`, bases SQLite ni `node_modules`.
