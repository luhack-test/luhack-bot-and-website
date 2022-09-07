"""enable fuzzy stuff

Revision ID: 091040f78227
Revises: 13d2afe94e48
Create Date: 2022-09-06 17:56:57.324855

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = '091040f78227'
down_revision = '13d2afe94e48'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute("create extension if not exists fuzzystrmatch")
    conn.execute("create extension if not exists pg_trgm")
    pass


def downgrade():
    conn = op.get_bind()

    conn.execute("drop extension if not exists fuzzystrmatch")
    conn.execute("drop extension if not exists pg_trgm")
    pass
