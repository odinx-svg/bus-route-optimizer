# Runbook Legacy Desktop: Recuperacion de Runtime (Windows)

## Objetivo
Resolver equipos afectados por errores legacy de runtime en actualizacion, como:

- `failed to create runtime-tmpdir path`
- `Could not create temporary directory`
- `Failed to load Python DLL ... _MEI... python311.dll`

Este runbook normaliza al cliente en un flujo estable (Setup + onedir).

## Alcance
- Instalaciones antiguas de TUTTI desktop con comportamiento inestable al actualizar.
- Soporte de primer nivel y despliegue asistido.

## Procedimiento (5 minutos)
1. Cerrar TUTTI completamente.
2. Abrir Administrador de tareas y finalizar:
   - `Tutti Desktop.exe`
   - procesos de instalador TUTTI/Inno si siguen vivos.
3. Descargar el ultimo `TuttiSetup.exe` desde el release oficial.
4. Ejecutar `TuttiSetup.exe` como administrador.
5. Instalar encima de la version actual (misma carpeta por defecto).
6. Abrir TUTTI y validar:
   - abre sin popup de runtime tmp dir;
   - en `Control` se ve la version esperada;
   - `desktop-updater.log` registra `UPDATE_MODE_RESOLVED` con `install_mode=onedir_installed`.

## Validacion tecnica rapida
1. Verificar estructura instalada:
   - existe `Tutti Desktop.exe`
   - existe carpeta `_internal` junto al exe
2. Verificar logs:
   - `%LOCALAPPDATA%\Tutti\logs\desktop-updater.log`
   - no aparecen errores de `_MEI` ni `runtime-tmpdir`.

## Si persiste el error
1. Desinstalar TUTTI desde Aplicaciones.
2. Borrar carpeta residual (si existe): `C:\Program Files\TUTTI`.
3. Reinstalar con el ultimo `TuttiSetup.exe`.
4. Reintentar apertura.

## Nota operativa
- Contrato de canal:
  - Instalaciones Setup (`_internal` presente) se actualizan solo con `TuttiSetup.exe`.
  - Instalaciones portable se actualizan solo con `TuttiDesktopApp.zip`.
