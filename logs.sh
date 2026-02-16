#!/bin/bash
# =============================================================================
# Tutti - Logs Script
# Muestra logs de los servicios
# Uso: ./logs.sh [frontend|backend|postgres|redis]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE=${1:-}

if [ -z "$SERVICE" ]; then
    echo "📋 Mostrando logs de todos los servicios (Ctrl+C para salir)..."
    docker-compose logs -f --tail=100
else
    echo "📋 Mostrando logs de '$SERVICE' (Ctrl+C para salir)..."
    docker-compose logs -f --tail=100 "$SERVICE"
fi
