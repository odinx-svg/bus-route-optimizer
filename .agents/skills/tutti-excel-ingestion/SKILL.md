---
name: tutti-excel-ingestion
description: Parsing y normalizacion de Excels de Tutti Fleet Optimizer. Usar cuando se necesite crear, modificar o debuggear la logica de ingesta desde hojas Excel, la deteccion de columnas, el manejo de datos sucios y la conversion de archivos reales en Route[] validas.
---

# Tutti Excel Ingestion Skill

## Proposito

Esta skill protege la parte mas sucia del sistema: el parser de Excel real.

Activa esta skill cuando el trabajo afecte:
- `backend/parser.py`
- fixtures `.xlsx`
- tests del parser
- errores de importacion de archivos reales

## Workflow

1. Leer `references/DIRTY_DATA_CASES.md`.
2. Revisar `backend/parser.py` completo antes de simplificar helpers.
3. Revisar tests:
   - `backend/tests/test_parser.py`
   - `backend/tests/test_models.py`
4. Si el cambio afecta el shape de `Route`, complementar con `tutti-domain-model`.
5. Verificar con al menos un fixture real o sample workbook.

## Heuristicas del parser actual

- Normalizacion accent-insensitive con `_normalize_text`.
- Soporte defensivo para celdas vacias, `NaN`, strings nulos y formatos mixtos.
- Deteccion de columnas por patrones, no por nombres exactos.
- Tiempos admitidos como `time`, `datetime`, string y numerico.
- Rangos de plazas parseados desde texto irregular.
- Fallbacks explicitos cuando faltan hojas o columnas.

## Guardrails

- No elimines helpers pequenos solo porque parezcan repetidos; suelen cubrir edge cases reales.
- No hardcodees nombres exactos de columnas si hoy se usan patrones.
- No asumas un unico layout de workbook.
- No cambies defaults de dias, horas o capacidad sin revisar tests y optimizer.
- Si una fila invalida se descarta, mantener trazabilidad en reportes o warnings.

## Cuando derivar

- Si el cambio llega al significado de `Route` o `Stop`: usar `tutti-domain-model`.
- Si el problema esta en tiempos OSRM o geometrias: usar `tutti-routing-maps` cuando exista.

## Referencias

- `references/DIRTY_DATA_CASES.md`

