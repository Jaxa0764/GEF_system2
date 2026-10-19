"""Add telegram user fields

Revision ID: 0002_telegram_fields
Revises: 0001_initial
Create Date: 2026-10-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0002_telegram_fields'
down_revision: Union[str, Sequence[str], None] = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('telegram_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('phone_number', sa.String(length=32), nullable=True))
        batch_op.alter_column('password_hash',
               existing_type=sa.String(length=255),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_users_telegram_id'), ['telegram_id'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_telegram_id'))
        batch_op.alter_column('password_hash',
               existing_type=sa.String(length=255),
               nullable=False)
        batch_op.drop_column('phone_number')
        batch_op.drop_column('telegram_id')
