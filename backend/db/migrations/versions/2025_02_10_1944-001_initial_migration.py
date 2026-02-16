"""Initial migration - Create routes, stops, and optimization tables

Revision ID: 001
Revises: 
Create Date: 2025-02-10 19:44:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create routes table
    op.create_table(
        'routes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('school_id', sa.String(), nullable=False),
        sa.Column('school_name', sa.String(), nullable=False),
        sa.Column('arrival_time', sa.Time(), nullable=True),
        sa.Column('departure_time', sa.Time(), nullable=True),
        sa.Column('capacity_needed', sa.Integer(), server_default='0'),
        sa.Column('contract_id', sa.String(), nullable=False),
        sa.Column('days', postgresql.ARRAY(sa.String()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on route type
    op.create_index('ix_routes_type', 'routes', ['type'])
    op.create_index('ix_routes_school_id', 'routes', ['school_id'])
    
    # Create stops table
    op.create_table(
        'stops',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('route_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('time_from_start', sa.Integer(), server_default='0'),
        sa.Column('passengers', sa.Integer(), server_default='0'),
        sa.Column('is_school', sa.Boolean(), server_default='false'),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on route_id for stops
    op.create_index('ix_stops_route_id', 'stops', ['route_id'])
    
    # Create optimization_jobs table
    op.create_table(
        'optimization_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), server_default='pending'),
        sa.Column('algorithm', sa.String(), server_default='v6'),
        sa.Column('input_data', postgresql.JSON(), nullable=True),
        sa.Column('result', postgresql.JSON(), nullable=True),
        sa.Column('stats', postgresql.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on status for jobs
    op.create_index('ix_optimization_jobs_status', 'optimization_jobs', ['status'])
    op.create_index('ix_optimization_jobs_created_at', 'optimization_jobs', ['created_at'])
    
    # Create optimization_results table
    op.create_table(
        'optimization_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('route_id', sa.String(), nullable=True),
        sa.Column('bus_id', sa.String(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('time_shift_minutes', sa.Integer(), server_default='0'),
        sa.Column('deadhead_minutes', sa.Integer(), server_default='0'),
        sa.ForeignKeyConstraint(['job_id'], ['optimization_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for optimization_results
    op.create_index('ix_optimization_results_job_id', 'optimization_results', ['job_id'])
    op.create_index('ix_optimization_results_route_id', 'optimization_results', ['route_id'])
    op.create_index('ix_optimization_results_bus_id', 'optimization_results', ['bus_id'])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index('ix_optimization_results_bus_id')
    op.drop_index('ix_optimization_results_route_id')
    op.drop_index('ix_optimization_results_job_id')
    op.drop_table('optimization_results')
    
    op.drop_index('ix_optimization_jobs_created_at')
    op.drop_index('ix_optimization_jobs_status')
    op.drop_table('optimization_jobs')
    
    op.drop_index('ix_stops_route_id')
    op.drop_table('stops')
    
    op.drop_index('ix_routes_school_id')
    op.drop_index('ix_routes_type')
    op.drop_table('routes')
