# Minero Web

App web para Minero basada en `REGLAS_DISENO_PRINT.md`.

Incluye:
- `frontend/`: React + Vite con vistas `Buscar`, `Resultados clasificados`, `Analisis`, `Ayuda`.
- `backend/`: FastAPI que integra `Query_generator` + `Fetcher_NCBI` + clasificacion (`ollama` o `heuristic`).

## 1. Levantar backend

```bash
cd minero_web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8010 --reload
```

Endpoint de salud:

```bash
curl http://localhost:8010/api/minero/health
```

## 2. Levantar frontend

```bash
cd minero_web/frontend
npm install
npm run dev
```

Por defecto el frontend usa `http://localhost:8010`.

Si necesitas otro backend:

```bash
VITE_MINERO_API_URL=http://localhost:8010 npm run dev
```

## 3. Contrato de salida consumido por frontend

La respuesta de `POST /api/minero/search` incluye:

- `metadata.classification_version`
- `metadata.classification_timestamp`
- `metadata.llm_runtime_available`
- `results[].classification` con:
  - `relevance_label`
  - `relevance_score`
  - `reason_short`
  - `tags`
  - `evidence_level`
  - `model_source`

## 4. Notas

- Si Ollama no esta disponible, backend clasifica con fallback heuristico.
- Se preserva compatibilidad de campos actuales: la clasificacion se agrega sin eliminar metadatos previos.
