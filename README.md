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

## Flujo disponible hoy

1. Selecciona el siniestro sintético `SIN-001`.
2. Ingresa o importa una factura JSON estructurada.
3. Ejecuta la auditoría y revisa cargos duplicados, conceptos fuera del
   siniestro y precios superiores a la tarifa.

La interfaz está preparada para sustituir este flujo por la carga de PDF y el
contrato `/api/v1/audits` cuando el backend implemente los endpoints acordados.

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
