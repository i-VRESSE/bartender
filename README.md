# Bartender

[![fair-software.eu](https://img.shields.io/badge/fair--software.eu-%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8B-yellow)](https://fair-software.eu)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.7614737.svg)](https://doi.org/10.5281/zenodo.7614737)
[![Research Software Directory Badge](https://img.shields.io/badge/rsd-bartender-00a3e3.svg)](https://research-software-directory.org/software/bartender)
[![Documentation Status](https://readthedocs.org/projects/i-vresse-bartender/badge/?version=latest)](https://i-vresse-bartender.readthedocs.io/en/latest/?badge=latest)

***

Bartender is a middleware web service to schedule jobs on various
infrastructures.

It can run command line applications for visitors. The application input should
be a configuration file with links to data files in the same directory.
After acquiring a JWT token, you can upload your configuration file and
data files as an archive to the web service for submission.
Once the job has been executed the output files
can be browsed with a web browser.

Bartender can be configured to run applications on a Slurm batch scheduler,
pilot job framework, the grid or in the cloud. Bartender will take care of
moving the input and output files to the right place. To pick where an
application should be run you can choose from a list of existing Python
functions or supply your own.

Bartender can run quick interactive applications on completed jobs.
This is handy if you want to run a quick analysis on the output of a job.

Bartender can be used as the computational backend for a web application, the
web application should guide visitors into the submission and show the results.
See <https://github.com/i-VRESSE/haddock3-webapp> for an example.

Documentation for users and developers is available
at <https://i-vresse-bartender.readthedocs.io> .

## Quickstart

1. Install bartender via github:

    ```bash
    pip install git+https://github.com/i-VRESSE/bartender.git
    ```

1. Obtain a copy of the example configuration file

    ```bash
    curl -o config.yaml https://raw.githubusercontent.com/i-VRESSE/bartender/main/config-example.yaml
    ```

1. In another terminal, start up a database for storing jobs.

    ```bash
    docker run \
        -p "5432:5432" \
        -e "POSTGRES_PASSWORD=bartender" \
        -e "POSTGRES_USER=bartender" \
        -e "POSTGRES_DB=bartender" \
        --mount type=volume,source=bartender-db,target=/var/lib/postgresql/data \
        postgres:15.2-bullseye
    ```

    (Use `docker volume rm bartender-db` to clear the database storage`)

1. Create tables in the database

    ```bash
    alembic upgrade "head"
    ```

1. Generate token to authenticate yourself

    ```bash
    # Generate a rsa key pair
    openssl genpkey -algorithm RSA -out private_key.pem \
        -pkeyopt rsa_keygen_bits:2048
    openssl rsa -pubout -in private_key.pem -out public_key.pem
    bartender generate-token --username myname
    ```

1. Run the application

    ```bash
    bartender serve
    ```

1. Go to the interactive API documentation generated by FastAPI

    <http://localhost:8000/api/docs>

## Consuming web service

The interactive API documentation generated by FastAPI is at
<http://localhost:8000/api/docs>

### Authentication

To consume the bartender web service you need to authenticate yourself
with a [JWT token](https://jwt.io/) in the

* HTTP header `Authorization: Bearer <token>` or
* query parameter `?token=<token>` or
* Cookie `bartenderToken=<token>`of the HTTP request.

For more info see [Configuration docs](https://i-vresse-bartender.readthedocs.io/en/latest/configuration.html#authentication)

### Word count example

Bartender is by default configured with a word count applicaton. Use the
following steps to run a job:

1. Create an archive to submit. The zip file should contain a file called
   `README.md`. A zip file could be created in a clone of this repo with `zip
   README.zip README.md`.
2. Start [bartender web service and postgresql
   server](https://i-vresse-bartender.readthedocs.io/en/latest/index.html#quickstart)
3. Register & login account by
    1. Goto `http://127.0.0.1:8000/api/docs` and
    2. Try out the `POST /auth/register` route.
    3. Use default request body and press execute button. This will create an
       account with email `user@example.com` and password `string`.
    4. Use authorize button on top of page to login with username
       `user@example.com` and password `string`.
4. Submit archive.
    1. Try out the `PUT /api/application/wc/job` route.
    2. Upload the `README.zip` as request body.
    3. Press execute button
    4. The response contains a job identifier (`id` property) that can be used
       to fetch the job state.
5. Fetch job state
    1. Try out the `GET /api/job/{jobid}`
    2. Use job identifier retrieved by submit request as `jobid` parameter
       value.
        * When job state is equal to `ok` the job was completed succesfully.
6. Retrieve result. The word count application (`wc`) outputs to the stdout.
    1. Try out the `GET /api/job/{jobid}/stdout`
    2. Use job identifier retrieved by submit request as `jobid` parameter
       value.
    3. Should see something like `433  1793 14560 README.md`. Where numbers are
        counts for newlines, words, bytes.
