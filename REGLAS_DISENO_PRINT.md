# Reglas de Diseno de Minero (Pyner_PGRLAB)

## 1. Proposito
Este documento define la especificacion oficial de diseno UX/UI y contrato tecnico para Minero, basado en el flujo real del repositorio:

`lenguaje natural -> query NCBI -> fetcher -> clasificacion LLM -> visualizacion web`

Objetivo principal: que personas cientificas no bioinformaticas puedan usar el sistema de forma confiable y simple.

## 2. Estado real del sistema (fuente de verdad)
Estas reglas se basan en el estado actual del repo:

1. Flujo interactivo principal: `test_fetcher_integrator.sh`.
2. Generacion de query con degradacion sin LLM (sinonimos): `Query_generator/phases/phase3/api/main.py`.
3. Flujo BioProject con jerarquia SRA y sin busqueda PubMed activa por defecto: `Fetcher_NCBI/boolean_fetcher_integrated.py`.
4. Flujo PubMed directo con metadata completa y abstracts: `Fetcher_NCBI/pubmed_boolean_search.py` y `Fetcher_NCBI/ncbi_linkout.py`.
5. Referencia visual inicial: `sra-query-builder.zip` (UI util, datos mock).

## 3. Alcance y fuera de alcance
### 3.1 Alcance en esta etapa
1. Definir UX/UI objetivo de Minero para app web.
2. Definir contrato de datos para frontend en resultados clasificados de `PubMed` y `BioProject`.
3. Definir estrategia de clasificacion LLM con fallback heuristico.
4. Dejar especificacion decision-complete para implementar sin ambiguedades.

### 3.2 Fuera de alcance en esta etapa
1. Implementacion backend/frontend.
2. Migracion directa del ZIP como aplicacion productiva.
3. Cambios obligatorios en scripts existentes.

## 4. Usuarios objetivo y principios UX obligatorios
### 4.1 Usuario objetivo
Persona cientifica que entiende su pregunta biologica, pero no domina sintaxis booleana ni detalles internos de NCBI.

### 4.2 Principios UX (obligatorios)
1. Lenguaje simple y accionable en espanol.
2. Flujo guiado por pasos y decisiones explicitas.
3. Terminologia tecnica con ayuda contextual breve.
4. Priorizar "que significa este resultado" sobre "como se calculo".
5. Reducir pasos manuales y minimizar errores por configuracion.

## 5. Arquitectura de interaccion de la app web
La app debe tener 4 vistas principales:

1. `Buscar`
2. `Resultados clasificados`
3. `Analisis`
4. `Documentacion / Ayuda`

### 5.1 Vista `Buscar`
1. Entrada unica en lenguaje natural con ejemplo pre-cargado.
2. Selector guiado de fuente: `PubMed` o `BioProject`.
3. Previsualizacion legible de query generada.
4. Confirmacion explicita antes de ejecutar.

### 5.2 Vista `Resultados clasificados`
1. Tabla con semaforo de relevancia (`alta`, `media`, `baja`).
2. Filtros simples: relevancia, organismo, condicion, estrategia, evidencia.
3. Panel lateral "Por que este resultado es relevante".
4. Exportacion `CSV` y `JSON` con clasificacion incluida.

### 5.3 Vista `Analisis`
1. Resumen de distribucion por relevancia y etiquetas.
2. Metricas agregadas por fuente (PubMed/BioProject).
3. Indicador claro de modo de clasificacion (`ollama` o `heuristic`).

### 5.4 Vista `Documentacion / Ayuda`
1. Glosario minimo de terminos biologicos y de NCBI.
2. Guia de uso en pasos.
3. Ejemplos reales de consultas.

## 6. Sistema visual y accesibilidad
La visual debe conservar el tono cientifico de `sra-query-builder.zip`, con estas reglas:

1. Accesibilidad minima WCAG AA en contraste de texto y controles.
2. Tema principal claro; modo oscuro opcional.
3. Tipografia y espaciado para lectura prolongada.
4. Jerarquia visual estable: accion primaria > filtros > detalles.
5. Iconografia solo como apoyo, no como unico canal de significado.
6. Estados de foco visibles para teclado.

### 6.1 Paleta semantica recomendada
1. `alta`: verde.
2. `media`: ambar.
3. `baja`: rojo suave.
4. `sin clasificar` (solo durante carga): gris.

## 7. Estados de UX obligatorios
Minero debe soportar estos estados en cada vista:

1. `loading`
2. `empty`
3. `error`
4. `partial-success`
5. `success`

Reglas:

1. Mensajes cortos y no tecnicos.
2. Cada error debe sugerir accion siguiente.
3. En `partial-success` mostrar que parte salio bien y que parte no.

## 8. Clasificacion LLM de resultados
### 8.1 Cobertura
La clasificacion aplica a ambos flujos:

1. `PubMed` (papers)
2. `BioProject` (proyectos + jerarquia SRA)

### 8.2 Salida de clasificacion obligatoria por resultado
Cada resultado debe incluir:

1. `relevance_label`: `"alta" | "media" | "baja"`
2. `relevance_score`: `number` (0-1)
3. `reason_short`: `string` (1-2 frases)
4. `tags`: `string[]`
5. `evidence_level`: `"directa" | "indirecta" | "débil"`
6. `model_source`: `"ollama" | "heuristic"`

### 8.3 Estrategia runtime
1. Default: `Ollama local`.
2. Si Ollama no esta disponible: fallback heuristico obligatorio.
3. Nunca dejar resultados sin objeto `classification`.

### 8.4 Heuristica minima de fallback (obligatoria)
Cuando `model_source = "heuristic"`:

1. Puntuar coincidencia de terminos clave entre query y metadatos.
2. Subir puntaje por coincidencia de organismo y estrategia.
3. Bajar puntaje por metadatos faltantes extensos.
4. Asignar `relevance_label` por umbrales fijos del proyecto.
5. Generar `reason_short` explicando reglas usadas.

## 9. Contrato de datos frontend
### 9.1 Objeto `classification` (reutilizable)
```json
{
  "classification": {
    "relevance_label": "alta",
    "relevance_score": 0.87,
    "reason_short": "Coincide organismo, condicion y estrategia con la consulta.",
    "tags": ["organismo:Arabidopsis thaliana", "condicion:drought", "estrategia:RNA-Seq"],
    "evidence_level": "directa",
    "model_source": "ollama"
  }
}
```

### 9.2 JSON de salida - metadatos globales nuevos
Campos obligatorios en el bloque `metadata`:

1. `classification_version`
2. `classification_timestamp`
3. `llm_runtime_available`

Ejemplo minimo:
```json
{
  "metadata": {
    "query": "....",
    "total_results": 20,
    "classification_version": "1.0.0",
    "classification_timestamp": "2026-02-13T12:00:00Z",
    "llm_runtime_available": true
  }
}
```

### 9.3 JSON de salida - modo PubMed
Cada item de `publications` debe incluir `classification`:
```json
{
  "pmid": "12345678",
  "title": "....",
  "abstract": "....",
  "classification": {
    "relevance_label": "media",
    "relevance_score": 0.62,
    "reason_short": "Coincide condicion, pero evidencia indirecta.",
    "tags": ["condicion:drought", "evidencia:review"],
    "evidence_level": "indirecta",
    "model_source": "heuristic"
  }
}
```

### 9.4 JSON de salida - modo BioProject
Cada item de `results` debe incluir `classification`, sin romper estructura SRA existente:
```json
{
  "bioproject": "PRJNA000000",
  "organism": "Arabidopsis thaliana",
  "sra_hierarchy": {
    "SAMN00000000": {
      "sample_id": "SAMN00000000",
      "experiments": []
    }
  },
  "classification": {
    "relevance_label": "alta",
    "relevance_score": 0.91,
    "reason_short": "Proyecto altamente alineado con consulta y estrategia.",
    "tags": ["organismo:Arabidopsis thaliana", "estrategia:RNA-Seq"],
    "evidence_level": "directa",
    "model_source": "ollama"
  }
}
```

### 9.5 CSV extendido (minimo obligatorio)
Agregar columnas:

1. `relevance_label`
2. `relevance_score`
3. `tags`
4. `evidence_level`

Reglas:

1. `tags` serializado con separador `;`.
2. `model_source` recomendado como columna adicional.
3. Si no hay LLM, completar columnas con heuristica.

## 10. Compatibilidad y versionado
1. No eliminar campos actuales de salida.
2. Extender esquema actual con bloque `classification`.
3. Si algun dato biologico viene `NA`, la clasificacion igual debe existir.
4. Versionar contrato como `classification_version`.

## 11. Flujo guiado para no bioinformaticos (obligatorio)
1. Escribir pregunta biologica en lenguaje natural.
2. Elegir fuente (`PubMed` o `BioProject`) con descripcion de impacto en tiempo.
3. Confirmar query generada en texto legible.
4. Ejecutar busqueda y mostrar progreso.
5. Revisar resultados ordenados por relevancia.
6. Leer explicacion "Por que es relevante".
7. Exportar dataset clasificado.

## 12. Casos de prueba obligatorios
1. Clasificacion con Ollama disponible.
2. Clasificacion sin Ollama (fallback heuristico).
3. Resultado con `NA` y `classification` presente.
4. Flujo `PubMed` con abstracts largos.
5. Flujo `BioProject` con jerarquia SRA y sin publicaciones.
6. Legibilidad UX en espanol (mensajes y ayudas).
7. Consistencia del contrato JSON entre `PubMed` y `BioProject`.

## 13. Checklist de implementacion y validacion UX
### 13.1 Backend / datos
1. Inyectar `classification` en cada resultado.
2. Agregar metadatos globales de clasificacion.
3. Extender CSV con columnas minimas requeridas.
4. Garantizar fallback heuristico cuando Ollama no este disponible.

### 13.2 Frontend / UX
1. Implementar vistas `Buscar`, `Resultados clasificados`, `Analisis`, `Ayuda`.
2. Mostrar semaforo de relevancia y filtros simples.
3. Incluir panel "Por que este resultado es relevante".
4. Mantener mensajes no tecnicos y en espanol.
5. Validar contraste AA y foco de teclado.

### 13.3 Aceptacion final
1. Documento y UI sin referencias a componentes inexistentes de PRINT.
2. Contrato tecnico consumible por frontend sin decisiones abiertas.
3. Clasificacion robusta con y sin LLM.
4. Exportaciones CSV/JSON consistentes.

## 14. Criterios de aceptacion de este documento
1. `REGLAS_DISENO_PRINT.md` queda 100% contextualizado a Minero.
2. La especificacion alinea diseno con flujo real del repo.
3. Incluye contrato tecnico para clasificacion en ambos modos.
4. Define explicitamente fallback sin LLM.
5. Permite implementar web + clasificador sin decisiones pendientes.

## 15. Supuestos y defaults adoptados
1. Idioma principal UX: espanol.
2. Cobertura de clasificacion: `PubMed` y `BioProject`.
3. Runtime por defecto: `Ollama local`.
4. Fallback obligatorio: heuristico deterministico.
5. Base visual inicial: `sra-query-builder.zip`, conectada a datos reales de Pyner.
