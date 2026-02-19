---
name: tutti-build-deploy
description: Build y deployment para Tutti Fleet Optimizer. Usar cuando se necesite construir la aplicacion desktop, generar el ejecutable Windows, actualizar la landing page en Vercel, crear releases de GitHub, o configurar el proceso de CI/CD. Incluye conocimiento de PyInstaller, empaquetado, auto-update y distribucion.
---

# Tutti Build & Deploy Skill

## Overview

Tutti tiene 3 artefactos de distribucion:
1. **Desktop EXE**: App Windows con backend embebido
2. **Landing Page**: Vercel (HTML/CSS/JS)
3. **Dev Mode**: Backend + Frontend por separado

## Desktop Build Process

### Requisitos

- Windows 10/11
- Python 3.11+
- Node.js 18+
- Git

### Build Manual

```batch
# 1. Ejecutar script de build
scripts\desktop\build-desktop-app-exe.bat

# Pasos del script:
# - Instala dependencias Python
# - Sincroniza binario CBC
# - Build frontend (npm run build)
# - PyInstaller onefile
# - Genera ZIP
```

### Salida del Build

```
dist/
├── Tutti Desktop.exe           # Ejecutable final
└── desktop-app/
    ├── release/
    │   └── Tutti Desktop.exe   # Copia para ZIP
    └── TuttiDesktopApp.zip     # ZIP de distribucion
```

### Configuracion PyInstaller

```python
# Tutti Desktop.spec

# Archivos embebidos:
# - backend/          -> backend/
# - frontend/dist/    -> frontend/dist

# Hidden imports requeridos:
# - main, parser, models, db.database, db.models
# - fastapi, starlette, pydantic, uvicorn
# - websockets, wsproto
# - sqlalchemy, pandas, openpyxl
# - reportlab, pulp

# Collect data/binaries:
# - --collect-data pulp
# - --collect-binaries pulp
```

## Desktop Launcher

### Runtime Modes

```python
# Modo Desktop empaquetado (PyInstaller)
if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", None)  # Ruta temp del EXE
    runtime_root = Path(meipass)
else:
    # Modo desarrollo
    runtime_root = Path(__file__).resolve().parents[2]
```

### Variables de Entorno Desktop

```python
# Configuracion critica para desktop
os.environ["SERVE_FRONTEND_DIST"] = "true"
os.environ["FRONTEND_DIST_DIR"] = str(runtime_root / "frontend" / "dist")
os.environ["APP_RUNTIME_MODE"] = "stable"
os.environ["CELERY_ENABLED"] = "false"
os.environ["USE_DATABASE"] = "true"
os.environ["DATABASE_URL"] = f"sqlite:///{data_dir / 'tutti_desktop.db'}"

# OSRM (preconfigurado para desktop)
os.environ["OSRM_BASE_URL"] = "http://187.77.33.218:5000"
```

## Auto-Update System

### Flujo de Actualizacion

```
1. Desktop lanza → _check_and_apply_update_if_available()
2. Consulta GitHub API → /repos/{repo}/releases/latest
3. Compara versiones → _is_newer_version(current, latest)
4. Descarga asset → _download_file(url, destination)
5. Verifica checksum → _verify_checksum(file, hash)
6. Aplica actualizacion:
   - Modo portable: _launch_updater_and_exit() → batch script reemplaza EXE
   - Modo installer: _launch_installer_and_exit() → ejecuta instalador
7. Auto-restart (opcional): TUTTI_DESKTOP_AUTORESTART_AFTER_UPDATE=1
```

### Versiones

```python
# Desktop version (desktop_version.py)
APP_VERSION = "0.2.3"
AUTO_UPDATE_ENABLED = True
GITHUB_REPO = "odinx-svg/bus-route-optimizer"
RELEASE_ASSET_ZIP = "TuttiDesktopApp.zip"
RELEASE_ASSET_EXE = "Tutti Desktop.exe"
```

### GitHub Release Assets

Requeridos para auto-update:
1. `TuttiDesktopApp.zip` (portable)
2. `TuttiSetup.exe` (instalador, opcional)
3. `checksums-sha256.txt` (verificacion)

## Landing Page (Vercel)

### Estructura

```
landing/
├── index.html          # Pagina principal
├── styles.css          # Estilos
├── main.js             # Logica (GitHub API)
└── vercel.json         # Config Vercel
```

### Configuracion Vercel

```json
{
  "cleanUrls": true,
  "trailingSlash": false
}
```

### Deploy

```bash
# Vercel CLI
cd landing
vercel --prod

# O via Git push (si esta conectado a repo)
git push origin main
```

### GitHub API Integration

```javascript
// main.js - Detecta ultima version
async function fetchLatestRelease() {
  const response = await fetch(
    'https://api.github.com/repos/odinx-svg/bus-route-optimizer/releases/latest'
  );
  const release = await response.json();
  
  return {
    version: release.tag_name,
    downloadUrl: release.assets.find(a => a.name === 'TuttiDesktopApp.zip')?.browser_download_url,
    publishedAt: release.published_at
  };
}
```

## Releases GitHub

### Proceso de Release

1. **Actualizar version**:
   ```python
   # scripts/desktop/desktop_version.py
   APP_VERSION = "0.2.4"
   ```

2. **Build**:
   ```batch
   scripts\desktop\build-desktop-app-exe.bat
   ```

3. **Generar checksums**:
   ```batch
   cd dist
   certutil -hashfile "Tutti Desktop.exe" SHA256 > checksums-sha256.txt
   ```

4. **Crear release en GitHub**:
   - Tag: `v0.2.4`
   - Upload assets:
     - `Tutti Desktop.exe`
     - `TuttiDesktopApp.zip`
     - `checksums-sha256.txt`

### Release Notes Template

```markdown
## What's Changed

### Nuevas funcionalidades
- Feature 1
- Feature 2

### Mejoras
- Improvement 1

### Bug fixes
- Fix 1

### Notas tecnicas
- Nota importante para desarrolladores

**Full Changelog**: https://github.com/odinx-svg/bus-route-optimizer/compare/v0.2.3...v0.2.4
```

## Scripts Utiles

### Verificar Build

```batch
@echo off
:: check-build.bat

echo Verificando build...

if not exist "dist\Tutti Desktop.exe" (
    echo ERROR: EXE no encontrado
    exit /b 1
)

if not exist "dist\desktop-app\TuttiDesktopApp.zip" (
    echo ERROR: ZIP no encontrado
    exit /b 1
)

echo Build OK
exit /b 0
```

### Instalador Silencioso

```batch
:: Para distribucion con instalador
TuttiSetup.exe /S /D=C:\Program Files\Tutti
```

## Troubleshooting Build

| Problema | Causa | Solucion |
|----------|-------|----------|
| EXE bloqueado | Archivo en uso | Cerrar instancias, taskkill |
| ImportError | Missing hidden import | Agregar a --hidden-import |
| CBC not found | Solver no embebido | Verificar --collect-binaries pulp |
| Frontend 404 | Dist no embebido | Verificar --add-data frontend/dist |
| DB locked | SQLite concurrente | Cerrar otras instancias |

## Referencias

- `references/build-scripts.md`: Scripts de build avanzados
- `references/release-checklist.md`: Checklist de release
