# Developer guidelines

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
        ├── filesystems/        # Package for different filesystems.
        ├── schdulers/          # Package for different schedulers.
        ├── shared/             # Package for shared logic between filesystems and schedulers.
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

```bash
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
    docker run -p "5432:5432" -e "POSTGRES_PASSWORD=bartender" -e "POSTGRES_USER=bartender" -e "POSTGRES_DB=bartender" postgres:15.2-bullseye
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

## DIRAC grid

To develop bartender with [DIRAC](http://diracgrid.org/) support you can use
[Dev Containers](https://containers.dev/)
to spinup a [DIRAC server container](
https://github.com/orgs/xenon-middleware/packages/container/package/diracc
) and a [DIRAC client container](
https://github.com/orgs/xenon-middleware/packages/container/package/diracclient
).

### Dev Container

Use the [Visual Studio Code Dev Containers extension](
https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers
) to open the workspace in a container.

In a VS code terminal you can run the DIRAC tests with

```shell
pytest -vv tests_dirac
```

To run DIRAC commands make sure the proxy is initialized with

```shell
dirac-proxy-init
```

### Run tests

To run all tests use

```shell
docker compose -f tests_dirac/docker-compose.yml run test
```

To run single test use

```shell
docker compose -f tests_dirac/docker-compose.yml run test 'pip install -e . && pytest -vv tests_dirac/test_it.py'
```

### DIRAC server debugging

The DIRAC server stores logs in `/opt/dirac/startup/*/log/current`
(where `*` are the DIRAC services) and pilot jobs are started under `/home/diracpilot`.
It can take a while for the job to start due to
the `WorkloadManagement_SiteDirector` service starting a pilot.
To look around inside the DIRAC server use

```shell
docker compose -f tests_dirac/docker-compose.yml exec dirac-tuto bash
```

Sometimes the DIRAC server needs clearing of its state,
do this outside container with

```shell
docker compose -f tests_dirac/docker-compose.yml rm -fs dirac-tuto
docker compose -f tests_dirac/docker-compose.yml up dirac-tuto
```

When the DIRAC server container is running you can login to it with

```shell
docker exec -ti tests_dirac-dirac-tuto-1 bash
. bashrc
dirac-proxy-init -K ~diracuser/.globus/userkey.pem -C ~diracuser/.globus/usercert.pem
# to fetch job status
dirac-wms-job-status 1
dirac-wms-job-logging-info 1
# to download raw logs
dirac-wms-job-get-output 1
# to download output files
dirac-wms-job-get-output-data 1
# to browse storage
dirac-dms-filecatalog-cli
# pilot logs
cat ~diracpilot/localsite/output/*
```

## Creating a new release

To create a new release, you should follow these steps:

1. In `pyproject.toml` and `docs/conf.py` update the version number.
2. Create a new GitHub release

- set tag and title to new version number with `v` prefix.
- with same first line of description as previous release.
- append generated release notes to the description.
