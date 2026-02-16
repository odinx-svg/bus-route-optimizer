#!/bin/bash
# =============================================================================
# Tutti - Reset Script
# Reset completo: detiene servicios, borra volúmenes y reconstruye
# ⚠️  ATENCIÓN: Esto borrará TODOS los datos de la base de datos
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "⚠️  ATENCIÓN: Esto borrará todos los datos de la base de datos"
echo ""
read -p "¿Estás seguro? (escribe 'si' para continuar): " confirm

if [ "$confirm" != "si" ]; then
    echo "❌ Cancelado"
    exit 0
fi

echo ""
echo "🛑 Deteniendo servicios..."
docker-compose down

echo ""
echo "🗑️  Borrando volúmenes..."
docker-compose down -v

echo ""
echo "🧹 Limpiando imágenes huérfanas..."
docker system prune -f

echo ""
echo "🔨 Reconstruyendo imágenes..."
docker-compose build --no-cache

echo ""
echo "🚀 Iniciando servicios..."
docker-compose up -d

echo ""
echo "✅ Reset completo finalizado"
echo ""
echo "📋 URLs disponibles:"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
