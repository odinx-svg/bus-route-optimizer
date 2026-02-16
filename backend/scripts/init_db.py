#!/usr/bin/env python3
"""
Script para inicializar la base de datos de Tutti.

Uso:
    python scripts/init_db.py

Este script:
1. Verifica la conexión a PostgreSQL
2. Crea las tablas si no existen
3. Ejecuta migraciones de Alembic
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import init_engine, create_tables, is_database_available, USE_DATABASE


def main():
    print("=" * 60)
    print("Tutti Database Initialization")
    print("=" * 60)
    
    # Check if database is enabled
    if not USE_DATABASE:
        print("\n⚠️  Database is disabled (USE_DATABASE=false)")
        print("   Set USE_DATABASE=true to enable database features.")
        return 0
    
    print(f"\n📊 Database URL: {os.getenv('DATABASE_URL', 'postgresql://tutti:tutti@localhost:5432/tutti')}")
    
    # Initialize engine
    print("\n🔄 Initializing database connection...")
    engine = init_engine()
    
    if engine is None:
        print("\n❌ Failed to connect to database!")
        print("\nPossible solutions:")
        print("  1. Make sure PostgreSQL is running:")
        print("     docker-compose up -d postgres")
        print("  2. Check DATABASE_URL in .env file")
        print("  3. Verify PostgreSQL credentials")
        return 1
    
    print("✅ Database connection successful!")
    
    # Create tables
    print("\n🔄 Creating tables...")
    try:
        create_tables()
        print("✅ Tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return 1
    
    # Verify tables exist
    print("\n🔄 Verifying database...")
    if is_database_available():
        print("✅ Database is ready!")
        print("\n📋 Available tables:")
        from sqlalchemy import inspect
        inspector = inspect(engine)
        for table_name in inspector.get_table_names():
            print(f"   - {table_name}")
    else:
        print("❌ Database verification failed!")
        return 1
    
    print("\n" + "=" * 60)
    print("Database initialization complete!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
