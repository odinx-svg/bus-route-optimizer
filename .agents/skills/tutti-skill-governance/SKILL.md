---
name: tutti-skill-governance
description: Gobernanza de la libreria de skills de Tutti. Usar cuando se necesite crear, dividir, fusionar, actualizar o auditar skills del proyecto, mantener consistencia entre SKILL.md y metadata UI, y evitar solapamientos o huecos en la cobertura de agentes.
---

# Tutti Skill Governance

## Proposito

Esta skill mantiene coherente la libreria de skills del proyecto. No es para desarrollar producto; es para evolucionar la capa de instrucciones de agentes sin romper su modularidad.

Activa esta skill cuando el trabajo afecte:
- `.agents/skills/`
- `AGENTS.md` en la seccion de skills
- convenciones de naming, scope o derivacion entre skills
- `agents/openai.yaml`

## Workflow

1. Revisar `references/SKILL_MAP.md`.
2. Identificar si el cambio es:
   - `create`
   - `update`
   - `split`
   - `merge`
   - `deprecate`
3. Confirmar que la nueva skill no invade el scope de otra ya existente.
4. Mantener `SKILL.md` compacto y mover detalle a `references/` cuando haga falta.
5. Si se crea o cambia una skill, revisar tambien:
   - `agents/openai.yaml`
   - `AGENTS.md`
   - referencias desde `tutti-architecture`

## Guardrails

- No crear skills por tecnologia si el dominio real es operativo.
- No dejar skills demasiado amplias que absorban parser + optimizer + flota a la vez.
- No duplicar instrucciones iguales en varias skills.
- No inventar estructura idealizada del repo; documentar la estructura real.
- Si una skill futura no existe aun en producto, dejarla como scaffold explicito.

## Criterios de buena modularidad

- una skill debe tener un problema claro
- debe tener triggers reconocibles
- debe tener guardrails concretos
- debe saber a que otras skills derivar
- debe apuntar a archivos reales

## Referencias

- `references/SKILL_MAP.md`
