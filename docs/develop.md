# Detailed instructions

These instructions are meant for developers that want to modify bartender. If
you're willing to contribute your changes, please refer to our [contributing
guidelines](https://github.com/i-VRESSE/bartender/blob/main/CONTRIBUTING.md) and
[code of
conduct](https://github.com/i-VRESSE/bartender/blob/main/CODE_OF_CONDUCT.md)

## Project structure

This project was generated using the
[fastapi_template](https://github.com/s3rius/FastAPI-template). Its main
structure is outlined below.

```bash
$ tree .
├── tests                       # Tests for project.
│   └── conftest.py             # Fixtures for all tests.
├── docs                        # Documentatin for project.
|   ├── index.rst               # Main documentation page.
│   └── conf.py                 # Sphinx config file.
└── src
    └── bartender
        ├── db                  # module contains db configurations
        │   ├── dao             # Data Access Objects. Contains different classes to interact with database.
        │   └── models          # Package contains different models for ORMs.
        ├── __main__.py         # Startup script. Starts uvicorn.
        ├── services            # Package for different external services such as rabbit or redis etc.
        ├── settings.py         # Main configuration settings for project.
        ├── static              # Static content.
        └── web                 # Package contains web server. Handlers, startup config.
            ├── api             # Package with all handlers.
            │   └── router.py   # Main router.
            ├── application.py  # FastAPI application configuration.
            └── lifetime.py     # Contains actions to perform on startup and shutdown.
```

## Installing from source

We recommend setting up a dedicated python virtual environment and install
bartender inside it. We use [poetry](https://python-poetry.org/) for package
management.

```bash
python3 -m venv venv
source venv/bin/activate
poetry install
```

## Migrations

Bartender uses [alembic](https://alembic.sqlalchemy.org) to create database
tables and perform migrations.

If you want to migrate your database, you should run following commands:

```bash
# To run all migrations until the migration with revision_id.
alembic upgrade "<revision_id>"

# To perform all pending migrations.
alembic upgrade "head"
```

### Reverting migrations

If you want to revert migrations, you should run:

```bash
# revert all migrations up to: revision_id.
alembic downgrade <revision_id>

# Revert everything.
 alembic downgrade base
```

### Migration generation

To generate migrations you should run:

```bash
# For automatic change detection.
alembic revision --autogenerate

# For empty file generation.
alembic revision
```

## Style guide

We follow the
[wemake-python-styleguide](https://wemake-python-styleguide.readthedocs.io/en/latest/)
which integrates various linters. Auto-formatters like black and isort are also
configured. An easy way to run everything is through [pre-commit](https://pre-commit.com/).
It's configured using `.pre-commit-config.yaml` file.

You can run pre-commit as a standalone command:

```
pre-commit run --all-files
```

or configure it such that it always runs automatically when you commit something:

```bash
pre-commit install
```

## Running tests

For running tests on your local machine

1. You need a database. Here's a way to start one with docker:

    ```text
    docker run -p "5432:5432" -e "POSTGRES_PASSWORD=bartender" -e "POSTGRES_USER=bartender" -e "POSTGRES_DB=bartender" postgres:13.6-bullseye
    ```

2. Run the pytest.

    ```bash
    pytest -vv .
    ```

To get a PostgreSQL terminal do

```bash
docker exec -ti <id or name of docker container> psql -U bartender
```

## Documentation

Documentation is generated with [Sphinx](https://www.sphinx-doc.org/en/master/),
and can be written in
[RestructuredText](https://docutils.sourceforge.io/rst.html) or [MyST
markdown](https://myst-parser.readthedocs.io/en/latest/)

First install dependencies with

```shell
poetry install --with docs
```

Build with

```shell
cd docs
make clean && make html
```

Creates documentation site at `docs/_build/html`.