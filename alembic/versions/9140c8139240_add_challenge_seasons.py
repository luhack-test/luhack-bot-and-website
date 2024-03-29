"""Add challenge seasons

Revision ID: 9140c8139240
Revises: 0ca0fb4f5666
Create Date: 2021-10-07 11:25:00.244586

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = '9140c8139240'
down_revision = '0ca0fb4f5666'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('completedchallenges', sa.Column('season', sa.Integer(), server_default='1', nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('completedchallenges', 'season')
    # ### end Alembic commands ###
