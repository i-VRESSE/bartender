# Contributing guidelines

We welcome any kind of contribution to our software, from simple comment or
question to a full fledged [pull
request](https://help.github.com/articles/about-pull-requests/). In case you
feel like can make a valuable contribution, but you you need help with any of
the steps below: don't let this discourage you; we can help!

## Questions and bug reports

The preferred method for asking and answering questions is through our [GitHub
issue tracker](https://github.com/i-VRESSE/bartender/issues). Before opening a
new issue, please use the search functionality to see of someone already filed
the same issue. You may add add "Question" label to your issue (or others, when
relevant.)

If you think you may have found a bug, you can follow the same instructions
using the "bug" label instead. Try to include all relevant information, such as
the version of bartender and potential configuration files. Ideally, try to
provide a minimal set of instructions to reproduce the problem.

## Code contributions

1. (**important**) announce your plan to the rest of the community _before you
   start working_. This announcement should be in the form of a (new) issue;
1. (**important**) wait until some kind of concensus is reached about your idea
   being a good idea;

Before [opening a pull request](https://help.github.com/articles/creating-a-pull-request/):

1. make sure the existing tests still work and add new tests (if necessary);
1. update or expand the documentation;
1. make sure your code follows the style guidelines;


### Obtaining a copy of the source code

If needed, fork the repository to your own Github profile and create your own
feature branch off of the latest master commit. While working on your feature
branch, make sure to stay up to date with the master branch by pulling in
changes, possibly from the 'upstream' repository (follow the instructions
[here](https://help.github.com/articles/configuring-a-remote-for-a-fork/) and
[here](https://help.github.com/articles/syncing-a-fork/));


Clone the project to obtain a local copy of the source code:

```bash
git clone https://github.com/i-VRESSE/bartender.git
cd bartender
```


### Working with the code

Below are some specific instructions for working with the project.

#### Poetry

This project uses [poetry](https://python-poetry.org/). It's a modern dependency management
tool.

To run the project use this set of commands:

```bash
poetry install
poetry run bartender serve
```

This will start the server on the configured host.

#### Docker

You can start the project with docker using this command:

```bash
docker-compose -f deploy/docker-compose.yml --project-directory . up --build
```

If you want to develop in docker with autoreload add `-f deploy/docker-compose.dev.yml` to your docker command.
Like this:

```bash
docker-compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up
```

This command exposes the web application on port 8000, mounts current directory and enables autoreload.

But you have to rebuild image every time you modify `poetry.lock` or `pyproject.toml` with this command:

```bash
docker-compose -f deploy/docker-compose.yml --project-directory . build
```

#### Pre-commit

[pre-commit](https://pre-commit.com/) is very useful to check your code before publishing it.
It's configured using `.pre-commit-config.yaml` file.

To install pre-commit simply run inside the shell:

```bash
pre-commit install
```

#### Migrations

Bartender uses [alembic](https://alembic.sqlalchemy.org) to create database tables and perform migrations.

If you want to migrate your database, you should run following commands:

```bash
# To run all migrations until the migration with revision_id.
alembic upgrade "<revision_id>"

# To perform all pending migrations.
alembic upgrade "head"
```

##### Reverting migrations

If you want to revert migrations, you should run:

```bash
# revert all migrations up to: revision_id.
alembic downgrade <revision_id>

# Revert everything.
 alembic downgrade base
```

##### Migration generation

To generate migrations you should run:

```bash
# For automatic change detection.
alembic revision --autogenerate

# For empty file generation.
alembic revision
```

#### Running tests

If you want to run it in docker, simply run:

```bash
docker-compose -f deploy/docker-compose.yml --project-directory . run --rm api pytest -vv .
docker-compose -f deploy/docker-compose.yml --project-directory . down
```

For running tests on your local machine.

1. you need to start a database.

    I prefer doing it with docker:

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

#### Documentation

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

Creates documentation site at [docs/_build/html](docs/_build/html/index.html).
