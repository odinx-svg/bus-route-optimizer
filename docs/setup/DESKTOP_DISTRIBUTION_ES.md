# Tutti Descargable (Windows) - Guia Rapida

## Que estamos construyendo

Version instalable para Windows con experiencia profesional:

1. Instalador `.exe` con asistente (siguiente, carpeta destino, licencia).
2. Prompt UAC de Windows (permiso de administrador para instalar en Program Files).
3. Opcion de "Ejecutar TUTTI ahora" al finalizar instalacion.

Arquitectura desktop:

1. Backend FastAPI local en `http://127.0.0.1:8000`
2. Frontend compilado (`frontend/dist`) servido por el backend
3. Ventana nativa de escritorio (WebView) abre la app local

No depende de Vercel/Render para funcionar.

---

## Ejecucion local en repo (modo app nativa)

Desde la raiz:

```bat
start-tutti-desktop-app.bat
```

Este script:

1. Verifica/crea `.venv`
2. Instala dependencias backend/desktop
3. Compila frontend si falta `frontend/dist`
4. Arranca backend local con SQLite
5. Abre ventana nativa de escritorio

---

## Build del ejecutable portable

Desde la raiz:

```bat
scripts\desktop\build-desktop-app-exe.bat
```

Salida:

1. EXE portable: `dist\Tutti Desktop.exe`
2. ZIP portable: `dist\desktop-app\TuttiDesktopApp.zip`

---

## Build del instalador profesional (wizard Windows)

Prerrequisito:

1. Instalar Inno Setup 6 (`ISCC.exe`)
2. Ruta esperada: `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`

Comando:

```bat
scripts\desktop\build-desktop-installer.bat
```

Salida:

1. Instalador: `dist\desktop-app\TuttiSetup.exe`

Caracteristicas del instalador:

1. Pagina de licencia (`scripts/desktop/installer/license_es.txt`)
2. Selector de carpeta de instalacion
3. Acceso directo en menu inicio (y opcional escritorio)
4. Ejecucion de TUTTI al finalizar
5. UAC de Windows (`PrivilegesRequired=admin`)

---

## Publicacion en GitHub Releases (recomendado)

En cada version:

1. Actualiza `APP_VERSION` en `scripts/desktop/desktop_version.py`
2. Genera assets:
   - `scripts\desktop\build-desktop-app-exe.bat`
   - `scripts\desktop\build-desktop-installer.bat`
3. Crea release con tag `vX.Y.Z`
4. Adjunta assets en este orden:
   - `TuttiSetup.exe` (descarga principal desde web)
   - `TuttiDesktopApp.zip` (canal portable)
   - `checksums-sha256.txt` (integridad obligatoria)

### Comando one-click (version + tag + push)

Desde la raiz del repo:

```bat
release-tutti-desktop.bat
```

Opcionalmente puedes fijar version manual:

```bat
release-tutti-desktop.bat 0.1.3
```

Este comando:

1. Actualiza `APP_VERSION` en `scripts/desktop/desktop_version.py`
2. Hace `git add -A` + commit
3. Crea tag `vX.Y.Z`
4. Hace push de rama y tag
5. Dispara GitHub Actions `desktop-release` para publicar assets

---

## Auto-update interno (desktop ya instalado)

La app de escritorio:

1. Consulta la ultima release en GitHub.
2. Compara version actual vs release.
3. Detecta modo de instalacion:
   - `onedir_installed` (Setup): requiere `TuttiSetup.exe`.
   - `portable`: requiere `TuttiDesktopApp.zip`.
4. Si falta el asset requerido para su modo, bloquea update y avisa claramente.
5. Si todo es correcto, aplica actualizacion silenciosa y relanza la app.

Importante:

1. Mantener assets canonicos en cada release:
   - `TuttiSetup.exe`
   - `TuttiDesktopApp.zip`
   - `checksums-sha256.txt`
2. Solo hacer `push` no basta: la deteccion usa la release/tag publicada (ej. `v0.2.32`).
3. No mezclar canales:
   - Setup nunca se actualiza con zip portable.
   - Portable nunca se actualiza con installer.

### Logs de updater (soporte)

Ruta: `%LOCALAPPDATA%\Tutti\logs\desktop-updater.log`

Eventos clave:

- `UPDATE_MODE_RESOLVED`
- `UPDATE_DOWNLOAD_STARTED`
- `UPDATE_CHECKSUM_OK`
- `UPDATE_APPLY_STARTED`
- `UPDATE_APPLY_FAILED`
- `UPDATE_APPLY_SUCCESS`

---

## Requisitos del cliente final

1. Windows 10/11
2. Permiso para instalar apps (`UAC`)
3. Conexion a internet para OSRM si no hay OSRM local

## Soporte legacy

Para equipos que ya muestran errores de runtime al actualizar, usar:

- `docs/setup/DESKTOP_LEGACY_RUNTIME_RECOVERY_ES.md`
