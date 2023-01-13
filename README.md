# bartender

[![fair-software.eu](https://img.shields.io/badge/fair--software.eu-%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8B%20%20%E2%97%8F%20%20%E2%97%8B-orange)](https://fair-software.eu)

- [bartender](#bartender)
  - [Step-by-step setup of proof-of-concept](#step-by-step-setup-of-proof-of-concept)
  - [Project structure](#project-structure)
  - [Configuration](#configuration)
    - [Applications](#applications)
    - [Job destinations](#job-destinations)
    - [Destination picker](#destination-picker)
  - [User management](#user-management)
    - [GitHub login](#github-login)
    - [Orcid sandbox login](#orcid-sandbox-login)
    - [Orcid login](#orcid-login)
    - [Super user](#super-user)
  - [Consuming web service](#consuming-web-service)
    - [Word count example](#word-count-example)
    - [Haddock3 example](#haddock3-example)
  - [Poetry](#poetry)
  - [Docker](#docker)
  - [Pre-commit](#pre-commit)
  - [Migrations](#migrations)
    - [Reverting migrations](#reverting-migrations)
    - [Migration generation](#migration-generation)
  - [Running tests](#running-tests)
  - [Documentation](#documentation)
    - [Build](#build)

***

Bartender is a middleware web service to schedule jobs on various infrastructures.

This project was generated using [fastapi_template](https://github.com/s3rius/FastAPI-template).

## [Step-by-step setup of proof-of-concept](#step-by-step-setup-of-proof-of-concept)

1. Clone the repository

    ```bash
    git clone https://github.com/i-VRESSE/bartender.git
    cd bartender
    ```

2. Make a python virtual environment

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install poetry

    ```bash
    pip install poetry
    ```

4. Install dependencies

    ```bash
    poetry install
    ```

5. Run the database for storing users and jobs.

    Important: **In another terminal**

    ```bash
    docker run \
        -p "5432:5432" \
        -e "POSTGRES_PASSWORD=bartender" \
        -e "POSTGRES_USER=bartender" \
        -e "POSTGRES_DB=bartender" \
        postgres:13.6-bullseye
    ```

6. Create tables in the database

    ```bash
    alembic upgrade "head"
    ```

7. Run the application

    ```bash
    bartender serve
    ```

8. Go to the interactive API documentation generated by FastAPI

    <http://localhost:8000/api/docs>

    See [Consuming web service](#consuming-web-service) for more info.

## [Project structure](#project-structure)

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
        ├── web                 # Package contains web server. Handlers, startup config.
            ├── api             # Package with all handlers.
            │   └── router.py   # Main router.
            ├── application.py  # FastAPI application configuration.
            └── lifetime.py     # Contains actions to perform on startup and shutdown.
```

## [Configuration](#configuration)

This application can be configured with environment variables and `config.yaml` file.
The environment variables are for FastAPI settings like http port and user management.
The `config.yaml` file is for non-FastAPI configuration like which [application can be submitted](#applications) and [where they should submitted](#job-destinations).
See [config-example.yaml](config-example.yaml) for example of a `config.yaml` file.

You can create `.env` file in the root directory and place all
environment variables here.

All environment variables should start with "BARTENDER\_" prefix.

For example if you see in your "bartender/settings.py" a variable named like
`random_parameter`, you should provide the "BARTENDER_RANDOM_PARAMETER"
variable to configure the value. This behavior can be changed by overriding `env_prefix` property
in `bartender.settings.Settings.Config`.

An example of .env file:

```bash
BARTENDER_RELOAD="True"
BARTENDER_PORT="8000"
BARTENDER_ENVIRONMENT="dev"
```

You can read more about BaseSettings class here: <https://pydantic-docs.helpmanual.io/usage/settings/>

### [Applications](#applications)

Bartender accepts jobs for different applications.

Applications can be configured in the `config.yaml` file under `applications` key.

For example

```yaml
applications:
    app1:
        command: app1 $config
        config:  workflow.cfg
```

* The key is the name of the application
* The `config` key is the config file that must be present in the uploaded archived.
* The `command` key is the command executed in the directory of the unpacked archive that the consumer uploaded. The `$config` in command string will be replaced with value of the config key.

### [Job destinations](#job-destinations)

Bartender can run job in different destinations.

A destination is a combination of a scheduler and filesystem.
Supported schedulers
* memory, Scheduler which has queue in memory and can specified number of jobs (slots) concurrently.
* slurm, Scheduler which calls commands of [Slurm batch scheduler](https://slurm.schedmd.com/) on either local machine or remote machine via SSH.

Supported file systems
* local: Uploading or downloading of files does nothing
* sftp: Uploading or downloading of files is done using SFTP.

When the filesystem is on a remote system with non-shared file system or a different user) then
* the input files will be uploaded before submission to the scheduler and
* the output files will be downloaded after the job has completed.

Destinations can be configured in the `config.yaml` file under `destinations` key.
By default a single slot in-memory scheduler with a local filesystem is used.

### [Destination picker](#destination-picker)

If you have multiple applications and job destinations you need some way to specify to which job submission should go.

A Python function can be used to pick to which destination a job should go.

To use a custom picker function set `destination_picker` in `config.yaml` file.
The value should be formatted as `<module>:<function>`, for example to rotate over each destination use `bartender.picker.pick_round` as value.
The picker function should have type `bartender.picker.DestinationPicker`.

By default jobs are submitted to the first destination.

## [User management](#user-management)

For secure auth add `BARTENDER_SECRET=<some random string>` to `.env` file.

The web service can be configured to authenticated via GitHub and/or Orcid.

After you have setup a social login described in sub chapter below then you can authenticate with

```text
curl -X 'GET' \
  'http://localhost:8000/auth/<name of social login>/authorize' \
  -H 'accept: application/json'
```

This will return an authorization URL, which should be opened in web browser.

Make sure the authorization URL and the callback URL configured in the social platform have the same scheme, domain (like localhost or 127.0.0.1) and port.

After visiting social authentication page you will get a JSON response with an access token.

This access token can be used on protected routes with

```text
curl -X 'GET' \
  'http://localhost:8000/api/users/profile' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <the access token>'
```

### [GitHub login](#github-login)

The web service can be configured to login with your [GitHub](https://gibhub.com) account.

To enable perform following steps:

1. Create a GitHub app
    1. Goto <https://github.com/settings/apps/new>
    2. Set Homepage URL to `http://localhost:8000/`
    3. Set Callback URL to `http://localhost:8000/auth/github/callback`
    4. Check `Request user authorization (OAuth) during installation`
    5. In Webhook section
        1. Uncheck `Active`
    6. In User permissions section
        1. Set `Email addresses` to `Read-only`
    7. Press `Create GitHub App` button
    8. After creation
        1. Generate a new client secret
        2. (Optionally) Restrict app to certain IP addresses
2. Append GitHub app credentials to `.env` file
    1. Add `BARTENDER_GITHUB_CLIENT_ID=<Client id of GitHub app>`
    2. Add `BARTENDER_GITHUB_CLIENT_SECRET=<Client secret of GitHub app>`

### [Orcid sandbox login](#orcid-sandbox-login)

The web service can be configured to login with your [Orcid sandbox](https://sandbox.orcid.org/) account.

To enable perform following steps:

1. Create Orcid account for yourself
   1. Goto [https://sandbox.orcid.org/](https://sandbox.orcid.org/)
       * Use `<something>@mailinator.com` as email, because to register app you need a verified email and Orcid sandbox only sends mails to `mailinator.com`.
   2. Goto [https://www.mailinator.com/v4/public/inboxes.jsp](https://www.mailinator.com/v4/public/inboxes.jsp) and search for `<something>` and verify your email address
   3. Goto [https://sandbox.orcid.org/account](https://sandbox.orcid.org/account), make email public for everyone
2. Create application
   1. Goto [https://sandbox.orcid.org/developer-tools](https://sandbox.orcid.org/developer-tools) to register app.
       * Only one app can be registered per orcid account, so use alternate account when primary account already has an registered app.
       * Your website URL
           * Does not allow localhost URL, so use `https://github.com/i-VRESSE/bartender`
       * Redirect URI
           * For dev deployments set to `http://localhost:8000/auth/orcidsandbox/callback`
3. Append Orcid sandbox app credentials to `.env` file
     1. Add `BARTENDER_ORCIDSANDBOX_CLIENT_ID=<Client id of Orcid sandbox app>`
     2. Add `BARTENDER_ORCIDSANDBOX_CLIENT_SECRET=<Client secret of Orcid sandbox app>`

The `GET /api/users/profile` route will return the Orcid ID in `oauth_accounts[oauth_name=sandbox.orcid.org].account_id`.

### [Orcid login](#orcid-login)

The web service can be configured to login with your [Orcid](https://orcid.org/) account.

Steps are similar to [Orcid sandbox login](#orcid-sandbox-login), but

* Callback URL must use **https** scheme
* Account emails don't have to be have be from `@mailinator.com` domain.
* In steps
  * Replace `https://sandbox.orcid.org/` with `https://orcid.org/`
  * In redirect URL replace `orcidsandbox` with `orcid`.
  * In `.env` replace `_ORCIDSANDBOX_` with `_ORCID_`

### [Super user](#super-user)

When a user has `is_superuser is True` then he/she can manage users and make other users also super users.

However you need a first super user. This can be done by running

```text
bartender super <email address of logged in user>
```

## [Consuming web service](#consuming-web-service)

The interactive API documentation generated by FastAPI is at <http://localhost:8000/api/docs>

To consume the bartender web service you need to authenticate yourself.
Authentication is done by passing a JWT token in the HTTP header `Authorization: Bearer <token>` in the HTTP request.
This token can be aquired by using the register+login routes or using a [socal login](#user-management).

### Word count example

Bartender is by default configured with a word count applicaton.
Use the following steps to run a job:

1. Create an archive to submit. The zip file should contain a file called `README.md`. A zip file could be created in a clone of this repo with `zip README.zip README.md`.
2. Start [bartender web service and postgresql server](#step-by-step-setup-of-proof-of-concept)
3. Register & login account by
    1. Goto `http://127.0.0.1:8000/api/docs` and
    2. Try out the `POST /auth/register` route.
    3. Use default request body and press execute button. This will create an account with email `user@example.com` and password `string`.
    4. Use authorize button on top of page to login with username `user@example.com` and password `string`.
4. Submit archive.
    1. Try out the `POST /api/application/{application}/job` route.
    2. Use `wc` as application parameter
    3. Upload the `README.zip` as request body.
    4. Press execute button
    5. The response contains a job identifier (`id` property) that can be used to fetch the job state.
5. Fetch job state
    1. Try out the `GET /api/job/{jobid}`
    2. Use job identifier retrieved by submit request as `jobid` parameter value.
        * When job state is equal to `ok` the job was completed succesfully.
6. Retrieve result. The word count application (`wc`) outputs to the stdout.
    1. Try out the `GET /api/job/{jobid}/stdout`
    2. Use job identifier retrieved by submit request as `jobid` parameter value.
    3. Should see something like `433  1793 14560 README.md`.
        Where numbers are counts for newlines, words, bytes.

### Haddock3 example

To test with haddock3 use
```shell
export BARTENDER_APPLICATIONS='{"haddock3": {"command": "haddock3 $config", "config": "workflow.cfg"}}'
bartender serve
```
Bartender expects the haddock3 executable to be in its PATH.

Submit a job in another terminal in a directory with a zip file with a `workflow.cfg` file and its data files.

Examples at https://github.com/haddocking/haddock3/blob/main/examples .
```shell
curl -X 'PUT' \
  'http://127.0.0.1:8000/api/applications/haddock3/job' \
  -H 'accept: */*' \
  -H 'Content-Type: multipart/form-data' \
  -F 'upload=@docking-protein-protein.zip;type=application/x-zip-compressed'
```
Where `docking-protein-protein.zip` is the zip file to run haddock3 with.

The response contains a redirect to the job url (`/api/job/<some id>`).

The job url should be fetched until the state property is either `ok` or `error`.

## [Poetry](#poetry)

This project uses [poetry](https://python-poetry.org/). It's a modern dependency management
tool.

To run the project use this set of commands:

```bash
poetry install
poetry run bartender serve
```

This will start the server on the configured host.

## [Docker](#docker)

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

## [Pre-commit](#pre-commit)

[pre-commit](https://pre-commit.com/) is very useful to check your code before publishing it.
It's configured using `.pre-commit-config.yaml` file.

To install pre-commit simply run inside the shell:

```bash
pre-commit install
```

## [Migrations](#migrations)

Bartender uses [alembic](https://alembic.sqlalchemy.org) to create database tables and perform migrations.

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

## [Running tests](#running-tests)

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

## [Documentation](#documentation)

### Build

First install dependencies with

```shell
poetry install --with docs
```

Build with
```shell
cd docs
make html
```

Creates documentation site at [docs/_build/html](docs/_build/html/index.html).
