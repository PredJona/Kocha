# Kocha# Kocha - Auditor de Facturación

Backend desarrollado para el Reto 2 del hackIAthon.

El sistema permite auditar automáticamente facturas enviadas por talleres, comparando los cobros contra un tarifario y contra los datos del siniestro reportado.

## Tecnologías

- Python
- FastAPI
- SQLite
- Pydantic
- Pytest

## Funcionalidades

- Registro de facturas.
- Persistencia con SQLite.
- Detección de facturas duplicadas.
- Consulta de tarifario.
- Validación de precios contra tarifario.
- Consulta de siniestros.
- Validación de ítems contra el siniestro reportado.
- Detección de ítems duplicados.
- Registro del resultado de auditorías.
- Consulta del historial de auditorías.
- API REST documentada con Swagger.
- Pruebas automáticas con Pytest.
- CORS configurado para integración con frontend.

## Estructura

```text
Kocha/
├── backend/
│   ├── tests/
│   │   ├── test_api.py
│   │   └── test_auditoria.py
│   ├── __init__.py
│   ├── auditoria.py
│   ├── database.py
│   ├── main.py
│   └── requirements.txt
├── .gitignore
└── README.md
```

## Crear entorno virtual

```bash
py -m venv .venv
```

En Windows:

```bash
.\.venv\Scripts\Activate.ps1
```

## Instalar dependencias

```bash
python -m pip install -r backend/requirements.txt
```

## Ejecutar backend

Desde la carpeta raíz del proyecto:

```bash
python -m uvicorn backend.main:app --reload
```

## Documentación de la API

Con el servidor ejecutándose:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

```text
GET  /
POST /facturas
GET  /tarifas
GET  /siniestros/{siniestro_id}
POST /auditar
GET  /auditorias
GET  /auditorias/{auditoria_id}
```

## Ejecutar pruebas

```bash
python -m pytest -v
```

## Reglas de auditoría actuales

El sistema detecta:

- Facturas registradas previamente.
- Ítems duplicados dentro de una factura.
- Precios superiores al tarifario acordado.
- Ítems que no existen en el tarifario.
- Ítems que no corresponden al siniestro reportado.
- Siniestros inexistentes.

## Datos de demostración

El proyecto utiliza datos ficticios para demostrar el funcionamiento del MVP.

El tarifario y los siniestros incluidos no representan información real de una aseguradora.