---
name: tutti-pdf-exports
description: Exportacion PDF operativa en Tutti Fleet Optimizer. Usar cuando se necesite modificar el formato del PDF de horarios, tablas por bus, enlaces de Google Maps, resumenes, estilos ReportLab o el payload esperado por la exportacion desde backend/frontend.
---

# Tutti PDF Exports Skill

## Proposito

Esta skill protege el output final que ve operación. Un cambio aquí puede romper el documento aunque el schedule sea correcto.

Activa esta skill cuando el trabajo afecte:
- `backend/pdf_service.py`
- endpoint `/export_pdf`
- payloads serializados de `schedule`
- enlaces Google Maps o tablas del PDF

## Workflow

1. Leer `references/PDF_EXPORTS.md`.
2. Revisar:
   - `backend/pdf_service.py`
   - `backend/main.py` en `/export_pdf`
   - llamadas frontend a export PDF
3. Confirmar qué campos del schedule usa el PDF:
   - `bus_id`
   - `items`
   - `start_time` / `end_time`
   - `stops`
   - `positioning_minutes` / `deadhead_minutes`
4. Si cambias links o stops, complementar con `tutti-routing-maps`.

## Guardrails

- No supongas que el PDF consume modelos Pydantic; acepta payload serializado.
- No cambies nombres de campos sin revisar frontend y export endpoint.
- No rompas backward compatibility con `positioning_minutes` / `deadhead_minutes`.
- No dependas de coordenadas inexistentes para generar el link de Google Maps.

## Cuando derivar

- Si el problema es schedule incorrecto: usar `tutti-domain-model` o `tutti-optimizer-dev`.
- Si el problema es geometría o OSRM: complementar con `tutti-routing-maps`.

## Referencias

- `references/PDF_EXPORTS.md`

