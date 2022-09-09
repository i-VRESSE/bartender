# bartender

- [bartender](#bartender)
  - [Step-by-step setup of proof-of-concept](#step-by-step-setup-of-proof-of-concept)
  - [Poetry](#poetry)
  - [Docker](#docker)
  - [Project structure](#project-structure)
  - [Configuration](#configuration)
  - [Pre-commit](#pre-commit)
  - [Migrations](#migrations)
    - [Reverting migrations](#reverting-migrations)
    - [Migration generation](#migration-generation)
  - [Running tests](#running-tests)
  - [User management](#user-management)
    - [GitHub login](#github-login)
    - [Orcid sandbox login](#orcid-sandbox-login)
    - [Orcid login](#orcid-login)
    - [Super user](#super-user)
  - [Job](#job)
    - [Calling bartender](#calling-bartender)
  - [Applications](#applications)

***

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

5. Run the application and the database

    ```bash
    bartender serve
    ```

    Important: **In another terminal**

    ```bash
    docker run \
        -p "5432:5432" \
        -e "POSTGRES_PASSWORD=bartender" \
        -e "POSTGRES_USER=bartender" \
        -e "POSTGRES_DB=bartender" \
        postgres:13.6-bullseye
    ```

6. Migrate the database

    ```bash
    alembic upgrade "head"
    ```

7. Go to the interactive API documentation generated by FastAPI

    <http://localhost:8000/api/docs>

8. Create a job with:

    ```bash
    $ curl -X 'PUT' \
      'http://localhost:8000/api/job/' \
      -H 'accept: */*' \
      -H 'Content-Type: application/json' \
      -d '{"name": "my_fist_job"}' \
      -v

    *   Trying 127.0.0.1:8000...
    * Connected to localhost (127.0.0.1) port 8000 (#0)
    > PUT /api/job/ HTTP/1.1
    > Host: localhost:8000
    > User-Agent: curl/7.79.1
    > accept: */*
    > Content-Type: application/json
    > Content-Length: 23
    >
    * Mark bundle as not supporting multiuse
    < HTTP/1.1 303 See Other
    < date: Fri, 26 Aug 2022 11:24:05 GMT
    < server: uvicorn
    < location: http://localhost:8000/api/job/1
    < transfer-encoding: chunked
    <
    * Connection #0 to host localhost left intact
    ```

***

This project was generated using fastapi_template.

## [Poetry](#poetry)

This project uses poetry. It's a modern dependency management
tool.

To run the project use this set of commands:

```bash
poetry install
poetry run bartender serve
```

This will start the server on the configured host.

You can find swagger documentation at `/api/docs`.

You can read more about poetry here: <https://python-poetry.org/>

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

## [Project structure](#project-structure)

```bash
$ tree "bartender"
bartender
├── conftest.py         # Fixtures for all tests.
├── db                  # module contains db configurations
│   ├── dao             # Data Access Objects. Contains different classes to interact with database.
│   └── models          # Package contains different models for ORMs.
├── __main__.py         # Startup script. Starts uvicorn.
├── services            # Package for different external services such as rabbit or redis etc.
├── settings.py         # Main configuration settings for project.
├── static              # Static content.
├── tests               # Tests for project.
└── web                 # Package contains web server. Handlers, startup config.
    ├── api             # Package with all handlers.
    │   └── router.py   # Main router.
    ├── application.py  # FastAPI application configuration.
    └── lifetime.py     # Contains actions to perform on startup and shutdown.
```

## [Configuration](#configuration)

This application can be configured with environment variables.

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

## [Pre-commit](#pre-commit)

To install pre-commit simply run inside the shell:

```bash
pre-commit install
```

pre-commit is very useful to check your code before publishing it.
It's configured using `.pre-commit-config.yaml` file.

By default it runs:

* black (formats your code);
* mypy (validates types);
* isort (sorts imports in all files);
* flake8 (spots possible bugs);
* yesqa (removes useless `# noqa` comments).

You can read more about pre-commit here: <https://pre-commit.com/>

## [Migrations](#migrations)

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

To get PostgreSQL terminal do

```bash
docker exec -ti <id or name of docker container> psql -U bartender
```

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

## [Job](#job)

### [Calling bartender](#calling-bartender)

To interact with the bartender web service the job needs to authenticate itself.
Authentication is done by passing a JWT token in the HTTP header `Authorization: Bearer <token>`.
The job can find a token in the `./meta` file.
This token belongs to the user that submitted it.

For example to submit another job do something like

```shell
TOKEN=$(tail -1 ./meta)
curl -X 'PUT' \
  'http://localhost:8000/api/job/' \
  -H 'accept: */*' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "string"
}'
```

## Applications

Bartender can accept jobs for different applications.

Applications can be configured with the `BARTENDER_APPLICATIONS` environment variable.

For example

```env
BARTENDER_APPLICATIONS='{"app1": {"command": "app1 $config", "config": "workflow.cfg"}, "app2": {"command": "app2 $config", "config": "workflow.cfg"}}'
```
