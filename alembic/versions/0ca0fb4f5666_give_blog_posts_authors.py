"""Give blog posts authors

Revision ID: 0ca0fb4f5666
Revises: fffe37a910ff
Create Date: 2021-04-10 06:35:37.751990

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = '0ca0fb4f5666'
down_revision = 'fffe37a910ff'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('blogs', sa.Column('author_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(None, 'blogs', 'users', ['author_id'], ['discord_id'], ondelete='SET NULL')

    op.create_check_constraint('blogs_slug_nonempty', 'blogs', 'slug != \'\'')
    op.create_check_constraint('writeups_slug_nonempty', 'writeups', 'slug != \'\'')
    op.create_check_constraint('challenges_slug_nonempty', 'challenges', 'slug != \'\'')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('blogs_slug_nonempty', 'blogs')
    op.drop_constraint('writeups_slug_nonempty', 'writeups')
    op.drop_constraint('challenges_slug_nonempty', 'challenges')

    op.drop_constraint(None, 'blogs', type_='foreignkey')
    op.drop_column('blogs', 'author_id')
    # ### end Alembic commands ###
