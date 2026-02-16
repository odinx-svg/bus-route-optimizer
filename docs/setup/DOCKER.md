# 🐳 Tutti - Docker Setup Guide

Guía completa para ejecutar Tutti con Docker Compose.

---

## 📋 Requisitos

- **Docker** 20.10+ 
- **Docker Compose** 2.0+
- **Git** (para clonar el repositorio)

### Verificar instalación

```bash
docker --version
docker-compose --version
```

---

## 🚀 Quick Start

### 1. Clonar y entrar al proyecto

```bash
cd bus-route-optimizer
```

### 2. Iniciar todos los servicios

**Linux/macOS:**
```bash
./start.sh
```

**Windows:**
```batch
start.bat
```

O manualmente con Docker Compose:
```bash
docker-compose up -d
```

### 3. Acceder a la aplicación

| Servicio | URL |
|----------|-----|
| 🌐 **Frontend** | http://localhost:5173 |
| 🔌 **Backend API** | http://localhost:8000 |
| 📚 **API Docs (Swagger)** | http://localhost:8000/docs |
| 🔑 **Health Check** | http://localhost:8000/health |
| 🐘 **PostgreSQL** | `localhost:5432` |
| ⚡ **Redis** | `localhost:6379` |

---

## 📁 Estructura de Archivos Docker

```
bus-route-optimizer/
├── backend/
│   ├── Dockerfile              # Multi-stage build para FastAPI
│   └── requirements.txt        # Dependencias Python
├── frontend/
│   ├── Dockerfile              # Multi-stage build para React
│   └── package.json            # Dependencias Node.js
├── docker-compose.yml          # Desarrollo
├── docker-compose.prod.yml     # Producción
├── start.sh / start.bat        # Iniciar servicios
├── stop.sh / stop.bat          # Detener servicios
├── logs.sh / logs.bat          # Ver logs
├── reset.sh / reset.bat        # Reset completo
├── migrate.sh / migrate.bat    # Ejecutar migraciones
└── DOCKER.md                   # Esta guía
```

---

## 🔧 Comandos de Gestión

### Iniciar servicios

```bash
# Desarrollo (con hot reload)
docker-compose up -d

# Producción (optimizado)
docker-compose -f docker-compose.prod.yml up -d
```

### Detener servicios

```bash
./stop.sh                 # Linux/macOS
stop.bat                  # Windows

# O manualmente:
docker-compose down
```

### Ver logs

```bash
./logs.sh                 # Todos los servicios
./logs.sh backend         # Solo backend
./logs.sh frontend        # Solo frontend
./logs.sh postgres        # Solo PostgreSQL
```

### Reset completo (⚠️ borra datos)

```bash
./reset.sh                # Linux/macOS
reset.bat                 # Windows
```

Esto:
- Detiene todos los contenedores
- Borra volúmenes (datos de BD)
- Elimina imágenes huérfanas
- Reconstruye todo desde cero

### Ejecutar migraciones

```bash
./migrate.sh              # Linux/macOS
migrate.bat               # Windows
```

### Acceder a contenedores

```bash
# Backend shell
docker-compose exec backend bash

# PostgreSQL
docker-compose exec postgres psql -U tutti -d tutti

# Redis
docker-compose exec redis redis-cli
```

---

## 🏗️ Arquitectura de Servicios

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network                            │
│                    (tutti-network)                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   Frontend   │──────▶│   Backend    │                    │
│  │   (React)    │      │  (FastAPI)   │                    │
│  │   :5173      │      │   :8000      │                    │
│  └──────────────┘      └──────┬───────┘                    │
│                               │                             │
│                               ▼                             │
│                      ┌──────────────┐                      │
│                      │  PostgreSQL  │                      │
│                      │    :5432     │                      │
│                      └──────────────┘                      │
│                               │                             │
│                      ┌──────────────┐                      │
│                      │    Redis     │                      │
│                      │    :6379     │                      │
│                      └──────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Variables de Entorno

### Backend

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexión PostgreSQL | `postgresql://tutti:tutti@postgres:5432/tutti` |
| `USE_DATABASE` | Habilitar/deshabilitar BD | `true` |
| `REDIS_URL` | URL de conexión Redis | `redis://redis:6379/0` |
| `OSRM_URL` | URL del servicio OSRM | `http://187.77.33.218:5000/route/v1/driving` |
| `DEBUG` | Modo debug | `true` (dev) / `false` (prod) |

### Frontend

| Variable | Descripción | Default |
|----------|-------------|---------|
| `VITE_API_URL` | URL del backend | `http://localhost:8000` |
| `VITE_OSRM_URL` | URL de OSRM | `http://localhost:5000/route/v1/driving` |

---

## 🗄️ Base de Datos

### PostgreSQL

- **Host**: `localhost` (o `postgres` desde otros contenedores)
- **Puerto**: `5432`
- **Database**: `tutti`
- **Usuario**: `tutti`
- **Password**: `tutti`

### Acceder con psql

```bash
# Desde host (si tienes psql instalado)
psql -h localhost -p 5432 -U tutti -d tutti

# Desde contenedor
docker-compose exec postgres psql -U tutti -d tutti
```

### Backup de datos

```bash
# Crear backup
docker-compose exec postgres pg_dump -U tutti tutti > backup.sql

# Restaurar backup
cat backup.sql | docker-compose exec -T postgres psql -U tutti -d tutti
```

---

## 🗺️ OSRM (Opcional)

El servicio OSRM está **comentado por defecto** porque requiere archivos de datos grandes.

### Usar OSRM externo

El proyecto ya viene configurado con un servidor OSRM externo:
```
OSRM_URL=http://187.77.33.218:5000/route/v1/driving
```

### Configurar OSRM local

1. Descargar datos OSM para tu región (ej. Galicia):
   ```bash
   wget https://download.geofabrik.de/europe/spain/galicia-latest.osm.pbf
   ```

2. Procesar datos con OSRM:
   ```bash
   docker run -t -v $(pwd):/data osrm/osrm-backend:latest osrm-extract -p /opt/car.lua /data/galicia-latest.osm.pbf
   docker run -t -v $(pwd):/data osrm/osrm-backend:latest osrm-partition /data/galicia-latest.osrm
   docker run -t -v $(pwd):/data osrm/osrm-backend:latest osrm-customize /data/galicia-latest.osrm
   ```

3. Descomentar servicio OSRM en `docker-compose.yml`:
   ```yaml
   osrm:
     image: osrm/osrm-backend:latest
     volumes:
       - ./data:/data
     command: osrm-routed /data/galicia-latest.osrm --algorithm mld
     ports:
       - "5000:5000"
   ```

---

## 🚨 Troubleshooting

### Puerto ya en uso

```bash
# Error: bind: address already in use

# Encontrar proceso usando el puerto
# Linux/macOS:
lsof -i :5173
lsof -i :8000

# Windows:
netstat -ano | findstr :5173
netstat -ano | findstr :8000

# Matar proceso o cambiar puerto en docker-compose.yml
```

### Permisos denegados (Linux/macOS)

```bash
chmod +x start.sh stop.sh logs.sh reset.sh migrate.sh
```

### Contenedores no inician

```bash
# Ver logs detallados
docker-compose logs --tail=100

# Reconstruir imágenes
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Hot reload no funciona

El hot reload está configurado con polling para compatibilidad con Docker:
- **Backend**: `--reload` de uvicorn
- **Frontend**: `CHOKIDAR_USEPOLLING=true`

En Windows/WSL, puede ser necesario aumentar los recursos de Docker.

### Error de conexión a base de datos

```bash
# Verificar que PostgreSQL está saludable
docker-compose ps

# Ver logs de PostgreSQL
docker-compose logs postgres

# Reiniciar servicios
docker-compose restart
```

---

## 📊 Producción

Para desplegar en producción:

### 1. Configurar variables seguras

```bash
# Crear archivo .env.prod
POSTGRES_PASSWORD=tu_password_seguro_aqui
REDIS_PASSWORD=tu_password_redis_aqui
OSRM_URL=https://tu-servidor-osrm.com/route/v1/driving
```

### 2. Usar docker-compose.prod.yml

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Diferencias con desarrollo

| Característica | Desarrollo | Producción |
|----------------|------------|------------|
| Frontend | Vite dev server | Nginx estático |
| Backend | 1 worker + reload | 4 workers Gunicorn |
| PostgreSQL | Expuesto en 5432 | Solo localhost |
| Redis | Sin password | Con password |
| Recursos | Sin límites | Límites definidos |
| Restart | unless-stopped | always |

---

## 🔧 Desarrollo

### Hot Reload

Cualquier cambio en el código se refleja automáticamente:

- **Backend** (`./backend/`): Recarga automática de uvicorn
- **Frontend** (`./frontend/src/`): HMR de Vite

### Instalar nuevas dependencias

**Backend:**
```bash
# Añadir a requirements.txt
docker-compose exec backend pip install nombre_paquete
```

**Frontend:**
```bash
# Añadir a package.json
docker-compose exec frontend npm install nombre_paquete
```

### Ejecutar tests

```bash
# Backend
docker-compose exec backend pytest

# Frontend
docker-compose exec frontend npm test
```

---

## 📈 Monitoreo

### Health Checks

```bash
# Verificar estado de todos los servicios
curl http://localhost:8000/health

# Respuesta esperada:
{
  "status": "healthy",
  "timestamp": 1234567890,
  "response_time_ms": 15.23,
  "service": "tutti-backend",
  "services": {
    "database": {"status": "ok", "message": "Connected"},
    "redis": {"status": "ok", "message": "Connected"}
  }
}
```

### Estadísticas de contenedores

```bash
# Uso de recursos
docker stats

# Espacio en disco
docker system df
```

---

## 🧹 Limpieza

```bash
# Detener y eliminar contenedores
docker-compose down

# Eliminar también volúmenes (borra datos!)
docker-compose down -v

# Eliminar imágenes no utilizadas
docker image prune

# Limpieza completa del sistema
docker system prune -a --volumes
```

---

## 🤝 Contribuir

1. Crear rama feature: `git checkout -b feature/nueva-funcionalidad`
2. Hacer cambios y probar con Docker
3. Commit: `git commit -am 'Añadir nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Crear Pull Request

---

## 📚 Referencias

- [Docker Docs](https://docs.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/docker/)
- [Vite Deployment](https://vitejs.dev/guide/static-deploy.html)

---

## 📝 Changelog

### v1.0.0
- ✅ Configuración Docker completa
- ✅ Multi-stage builds optimizados
- ✅ Hot reload desarrollo
- ✅ PostgreSQL + Redis
- ✅ Scripts de utilidad (bash + Windows)
- ✅ Health checks integrados
- ✅ Documentación completa

---

**¿Problemas?** Abre un issue en el repositorio o contacta al equipo de desarrollo.

🚌 **¡Feliz desarrollo con Tutti!**
