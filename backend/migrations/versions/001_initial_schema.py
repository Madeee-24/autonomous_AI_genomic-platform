"""Initial database schema migration for Genomic Analysis Platform

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. datasets
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_file_path', sa.String(length=512), nullable=False),
        sa.Column('file_checksum', sa.String(length=64), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('assembly', sa.String(length=20), nullable=False),
        sa.Column('validation_status', sa.String(length=30), nullable=False),
        sa.Column('validation_summary_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_datasets_file_checksum'), 'datasets', ['file_checksum'], unique=False)
    op.create_index(op.f('ix_datasets_user_id'), 'datasets', ['user_id'], unique=False)

    # 3. analysis_jobs
    op.create_table(
        'analysis_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('dataset_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('current_stage', sa.String(length=50), nullable=False),
        sa.Column('configuration_json', sa.JSON(), nullable=True),
        sa.Column('tool_versions_json', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analysis_jobs_dataset_id'), 'analysis_jobs', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_analysis_jobs_status'), 'analysis_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_analysis_jobs_user_id'), 'analysis_jobs', ['user_id'], unique=False)

    # 4. workflow_events
    op.create_table(
        'workflow_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('analysis_id', sa.String(length=36), nullable=False),
        sa.Column('stage', sa.String(length=50), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['analysis_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflow_events_analysis_id'), 'workflow_events', ['analysis_id'], unique=False)

    # 5. variants
    op.create_table(
        'variants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('analysis_id', sa.String(length=36), nullable=False),
        sa.Column('chromosome', sa.String(length=10), nullable=False),
        sa.Column('position', sa.BigInteger(), nullable=False),
        sa.Column('reference_allele', sa.String(length=255), nullable=False),
        sa.Column('alternate_allele', sa.String(length=255), nullable=False),
        sa.Column('variant_identifier', sa.String(length=64), nullable=True),
        sa.Column('variant_type', sa.String(length=20), nullable=False),
        sa.Column('quality', sa.Float(), nullable=True),
        sa.Column('filter_status', sa.String(length=50), nullable=False),
        sa.Column('genotype_json', sa.JSON(), nullable=True),
        sa.Column('info_json', sa.JSON(), nullable=True),
        sa.Column('allele_index', sa.BigInteger(), nullable=False),
        sa.Column('is_multiallelic', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['analysis_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_variants_analysis_id'), 'variants', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_variants_chromosome'), 'variants', ['chromosome'], unique=False)
    op.create_index(op.f('ix_variants_position'), 'variants', ['position'], unique=False)
    op.create_index(op.f('ix_variants_variant_identifier'), 'variants', ['variant_identifier'], unique=False)

    # 6. annotations
    op.create_table(
        'annotations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('variant_id', sa.String(length=36), nullable=False),
        sa.Column('gene_id', sa.String(length=64), nullable=True),
        sa.Column('gene_symbol', sa.String(length=64), nullable=True),
        sa.Column('transcript_id', sa.String(length=64), nullable=True),
        sa.Column('consequence', sa.String(length=128), nullable=False),
        sa.Column('impact', sa.String(length=20), nullable=False),
        sa.Column('annotation_source', sa.String(length=64), nullable=False),
        sa.Column('annotation_version', sa.String(length=32), nullable=True),
        sa.Column('raw_result_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_annotations_consequence'), 'annotations', ['consequence'], unique=False)
    op.create_index(op.f('ix_annotations_gene_id'), 'annotations', ['gene_id'], unique=False)
    op.create_index(op.f('ix_annotations_gene_symbol'), 'annotations', ['gene_symbol'], unique=False)
    op.create_index(op.f('ix_annotations_variant_id'), 'annotations', ['variant_id'], unique=False)

    # 7. evidence_records
    op.create_table(
        'evidence_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('variant_id', sa.String(length=36), nullable=False),
        sa.Column('source_name', sa.String(length=64), nullable=False),
        sa.Column('source_accession', sa.String(length=64), nullable=True),
        sa.Column('interpretation', sa.String(length=128), nullable=False),
        sa.Column('review_status', sa.String(length=128), nullable=True),
        sa.Column('evidence_summary', sa.Text(), nullable=True),
        sa.Column('source_url', sa.String(length=512), nullable=True),
        sa.Column('has_conflicts', sa.Boolean(), nullable=False),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_version', sa.String(length=32), nullable=True),
        sa.Column('raw_record_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evidence_records_source_accession'), 'evidence_records', ['source_accession'], unique=False)
    op.create_index(op.f('ix_evidence_records_variant_id'), 'evidence_records', ['variant_id'], unique=False)

    # 8. prioritization_results
    op.create_table(
        'prioritization_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('variant_id', sa.String(length=36), nullable=False),
        sa.Column('rule_version', sa.String(length=32), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('priority_category', sa.String(length=32), nullable=False),
        sa.Column('reasons_json', sa.JSON(), nullable=True),
        sa.Column('limitations_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('variant_id')
    )
    op.create_index(op.f('ix_prioritization_results_variant_id'), 'prioritization_results', ['variant_id'], unique=True)

    # 9. ai_explanations
    op.create_table(
        'ai_explanations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('variant_id', sa.String(length=36), nullable=False),
        sa.Column('model_provider', sa.String(length=64), nullable=False),
        sa.Column('model_name', sa.String(length=64), nullable=False),
        sa.Column('prompt_version', sa.String(length=32), nullable=False),
        sa.Column('input_evidence_ids', sa.JSON(), nullable=True),
        sa.Column('explanation_text', sa.Text(), nullable=False),
        sa.Column('structured_output_json', sa.JSON(), nullable=True),
        sa.Column('validation_status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('variant_id')
    )
    op.create_index(op.f('ix_ai_explanations_variant_id'), 'ai_explanations', ['variant_id'], unique=True)

    # 10. reports
    op.create_table(
        'reports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('analysis_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('report_path', sa.String(length=512), nullable=False),
        sa.Column('report_status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['analysis_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_analysis_id'), 'reports', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_reports_user_id'), 'reports', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('reports')
    op.drop_table('ai_explanations')
    op.drop_table('prioritization_results')
    op.drop_table('evidence_records')
    op.drop_table('annotations')
    op.drop_table('variants')
    op.drop_table('workflow_events')
    op.drop_table('analysis_jobs')
    op.drop_table('datasets')
    op.drop_table('users')
