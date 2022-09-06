"""instantiate_search_fns

Revision ID: 6a56c28c6bf1
Revises: f78a26022069
Create Date: 2022-09-06 17:23:48.327005

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils
from sqlalchemy_searchable import sql_expressions


# revision identifiers, used by Alembic.
revision = '6a56c28c6bf1'
down_revision = 'f78a26022069'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(sql_expressions.statement)
    pass


def downgrade():
    pass
