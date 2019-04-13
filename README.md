# LUHack_Discord_Verification_Bot

# secrets setup

- Create a copy of `.env.example` as `.env` and fill in the secrets

# poetry setup

https://github.com/sdispater/poetry

`poetry install`

# running the bot

`poetry run start_bot`

# running the writeups server

`poetry run uvicorn writeups_site.site:app`

# performing database migrations

## After making changes to the db schema, you should run

``` shell
poetry run alembic revision --autogenerate -m "<description of schema change>"
```

## When the db schema has been changed, you should run

``` shell
poetry run alembic upgrade head
```

## To check if the current db schema revision is the latest

``` shell
poetry run alembic current
```

- It should show a revision hash with `(head)` next to it if the db schema is up
  to data.

# required postgres extensions

- uuid-ossp
