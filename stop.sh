#!/bin/bash
# =============================================================================
# Tutti - Stop Script
# Detiene todos los servicios
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 Deteniendo servicios de Tutti..."
docker-compose down

echo ""
echo "✅ Todos los servicios han sido detenidos"
