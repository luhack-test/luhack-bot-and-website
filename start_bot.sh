#!/bin/sh
/opt/poetry/bin/poetry run alembic upgrade head \
    && /opt/poetry/bin/poetry run start_bot
