#!/bin/bash
# =============================================================================
# Tutti - Start Script
# Inicia todos los servicios en modo desarrollo
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  🚌 TUTTI - START                          ║"
echo "║           Iniciando servicios de desarrollo                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Verificar que Docker está instalado
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker no está instalado"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose no está instalado"
    exit 1
fi

echo "🔍 Verificando estado de los servicios..."
echo ""

# Detener servicios existentes si hay conflictos
docker-compose down --remove-orphans 2>/dev/null || true

echo "🔨 Construyendo imágenes (si es necesario)..."
docker-compose build --parallel

echo ""
echo "🚀 Iniciando servicios..."
docker-compose up -d

echo ""
echo "⏳ Esperando a que los servicios estén listos..."
echo ""

# Esperar a que PostgreSQL esté saludable
attempt=0
max_attempts=30
while [ $attempt -lt $max_attempts ]; do
    if docker-compose ps postgres | grep -q "healthy"; then
        echo "✅ PostgreSQL está listo"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Esperando PostgreSQL... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "⚠️  PostgreSQL no respondió a tiempo, pero continuando..."
fi

# Esperar a que el backend esté saludable
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose ps backend | grep -q "healthy" 2>/dev/null; then
        echo "✅ Backend está listo"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Esperando Backend... ($attempt/$max_attempts)"
    sleep 2
done

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              ✅ SERVICIOS INICIADOS                        ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  🌐 Frontend:    http://localhost:5173                     ║"
echo "║  🔌 Backend API: http://localhost:8000                     ║"
echo "║  📚 API Docs:    http://localhost:8000/docs                ║"
echo "║  🔑 Health:      http://localhost:8000/health              ║"
echo "║  🐘 PostgreSQL:  localhost:5432                            ║"
echo "║  ⚡ Redis:       localhost:6379                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Comandos útiles:"
echo "   ./logs.sh [servicio]  - Ver logs"
echo "   ./stop.sh             - Detener todo"
echo "   ./reset.sh            - Reset completo"
echo ""
echo "🎉 ¡Tutti está listo para desarrollar!"
