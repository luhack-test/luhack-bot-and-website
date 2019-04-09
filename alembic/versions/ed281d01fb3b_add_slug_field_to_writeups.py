"""Add slug field to writeups

Revision ID: ed281d01fb3b
Revises: 6329c2461f69
Create Date: 2019-04-08 21:22:45.835361

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ed281d01fb3b'
down_revision = '6329c2461f69'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('writeups', sa.Column('slug', sa.Text(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('writeups', 'slug')
    # ### end Alembic commands ###
