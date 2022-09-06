import sqlalchemy as sa
from sqlalchemy_searchable import inspect_search_vectors, search_manager
from sqlalchemy_utils import TSVectorType

from luhack_bot.db.models import db
from luhack_bot.secrets import db_url


async def init_db():
    await db.set_bind(db_url)

def inspect_search_vectors(entity):
    return [
        column
        for column
        in sa.inspect(entity).columns.values()
        if isinstance(column.type, TSVectorType)
    ]

def text_search(query, search_query, vector=None, regconfig=None, sort=False):
    """
    Search given query with full text search.
    :param search_query: the search query
    :param vector: search vector to use
    :param regconfig: postgresql regconfig to be used
    :param sort: order results by relevance (quality of hit)
    """
    if not search_query.strip():
        return query

    if vector is None:
        entity = query.locate_all_froms()
        search_vectors = inspect_search_vectors(entity)
        vector = search_vectors[0]

    if regconfig is None:
        regconfig = search_manager.options['regconfig']

    query = query.where(
        vector.op('@@')(sa.func.parse_websearch(regconfig, search_query))
    )
    if sort:
        query = query.order_by(
            sa.desc(
                sa.func.ts_rank_cd(
                    vector,
                    sa.func.parse_websearch(search_query)
                )
            )
        )

    return query.params(term=search_query)
