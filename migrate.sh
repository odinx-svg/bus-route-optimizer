#!/bin/bash
# =============================================================================
# Tutti - Migrate Script
# Ejecuta migraciones de base de datos
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔄 Ejecutando migraciones de base de datos..."

# Verificar que el backend está corriendo
if ! docker-compose ps backend | grep -q "Up"; then
    echo "❌ Error: El backend no está corriendo"
    echo "   Inicia los servicios primero con: ./start.sh"
    exit 1
fi

# Ejecutar migraciones
docker-compose exec backend python -c "
from db.database import create_tables, is_database_available
from db.models import Base
from sqlalchemy import create_engine
import os

database_url = os.getenv('DATABASE_URL', 'postgresql://tutti:tutti@postgres:5432/tutti')
print(f'Conectando a: {database_url.split(\"://\")[0]}://***@{database_url.split(\"@\")[-1]}')

try:
    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)
    print('✅ Tablas creadas exitosamente')
except Exception as e:
    print(f'❌ Error: {e}')
    exit(1)
"

echo ""
echo "✅ Migraciones completadas"
