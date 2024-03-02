# Configuration

This application can be configured with environment variables and `config.yaml`
file. The environment variables are for FastAPI settings like http port and user
management. The `config.yaml` file is for non-FastAPI configuration like which
[application can be submitted](#applications) and [where they should
submitted](#job-destinations).

## Environment variables

You can create `.env` file in the root directory and place all environment
variables here.

All environment variables should start with "BARTENDER\_" prefix.

For example if you see in your "bartender/settings.py" a variable named like
`random_parameter`, you should provide the "BARTENDER_RANDOM_PARAMETER" variable
to configure the value. This behavior can be changed by overriding `env_prefix`
property in `bartender.settings.Settings.Config`.

An example of .env file:

```bash
BARTENDER_RELOAD="True"
BARTENDER_PORT="8000"
BARTENDER_ENVIRONMENT="dev"
```

You can read more about BaseSettings class here:
<https://pydantic-docs.helpmanual.io/usage/settings/>

## Authentication

The bartender web service uses [JWT tokens](https://jwt.io/) for authentication.

The tokens should use the RS256 algorithm,
which requires a public and private RSA key pair.
A key pair can be generated with

```bash
openssl genpkey -algorithm RSA -out private_key.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -pubout -in private_key.pem -out public_key.pem
```

The private key of the RSA key pair is used to sign a token in
an another web application or with the `bartender generate-token` command.

The public key of the RSA key pair is used to verify that the token comes
from a trusted source.
The public key file location is `public_key.pem`
or value of `BARTENDER_PUBLIC_KEY` environment variable.

The token payload should contain the following claims:

* `sub`: The user id. Used to identifiy who submitted a job.
* `exp`: The expiration time of the token.
* `iss`: The issuer of the token. Used to track from where jobs are submitted.
* `roles`: Optionally. The roles of the user.
  See [Applications](#applications) how roles are used.

## Configuration file

Bartender uses a configuration file for setting up applications and destinations.

The configuration file is `config.yaml` or
value of `BARTENDER_CONFIG_FILENAME` environment variable.
An
[example configuration file](https://github.com/i-VRESSE/bartender/blob/main/config-example.yaml)
is shipped with the repository.

Here, we explain the options in more detail.

## Job root dir

By default, the files of jobs are stored in `/tmp/jobs`. To change the
directory, set the `job_root_dir` parameter in the configuration file to a valid
path.

```yaml
job_root_dir: /tmp/jobs
```

## Applications

Bartender accepts jobs for different applications.

Applications can be configured in the `config.yaml` file under `applications`
key.

For example

```yaml
applications:
  wc:
    command_template: wc README.md
    upload_needs:
      file: README.md
  size:
    command_template: >
      {% set flag = {
        'bytes': '-b',
        'kilobytes': '-k',
        'megabytes': '-m',
        'human': '-h',
      }[format] -%}
      du -s {{ flag|q }} .
    summary: Estimate file space usage.
    description: Determines the size of the unzipped files and prints it to the stdout.
    input_schema:
      additionalProperties: false
      properties:
        format:
          enum:
            - bytes
            - kilobytes
            - megabytes
            - human
          type: string
          description: The format of the output.
          default: bytes
  shutdown:
    # for demonstration purposes only, do not use in production
    command: shutdown -h now
    allowed_roles:
      - admin  # Only users with admin role can submit jobs for this application
```

* The key is the name of the application
* The zip archive file as value of the `upload` field name
  and optional fields defined in `input_schema`
  can be sent in a multipart/form-data request to
  the `PUT /api/application/{name of application}` endpoint.
* The `command_template` value is a [Jinja template](https://palletsprojects.com/p/jinja/)
  and is used to render the validated non file form fields into a command string.
* Optionally, the `upload_needs` is a list of file names that
  must be present inside the uploaded archive.
* Optionally, the non file form fields are validated against the JSON schema
  (version 2020-12) defined under the `input_schema` key.
  Input schema should be of type object and
  all its properties should be of type string.
* Optionally, the `allowed_roles` key holds an array of role names,
  one of which a submitter should have.
  When key is not set or list is empty then any authorized user
  is allowed. See [Authentication](#authentication) how to set roles on users.
* Optionally, the application can be annotated with a `summary` and `description`.
  These will be shown in the OpenAPI specification and
  the interactive API documentation at <http://localhost:8000/api/docs>.

In the command template make sure to use the `|q` filter so the
user supplied values are [shell-escaped](https://docs.python.org/3/library/shlex.html#shlex.quote).
Also to prevent [unintended newlines](https://yaml.org/spec/1.2.2/#65-line-folding)
in the rendered command use `>` in YAML.

## Job destinations

Bartender can run job in different destinations.

A destination is a combination of a scheduler and filesystem. Supported
schedulers

* **memory**, Scheduler which has queue in memory and can specified number of jobs
  (slots) concurrently.
* **slurm**, Scheduler which calls commands of [Slurm batch
  scheduler](https://slurm.schedmd.com/) on either local machine or remote
  machine via SSH.
* **arq**, Scheduler which uses a Redis server as a job queue and
  1 or more workers (`bartender perform` command) to run the jobs.
* **dirac**, Scheduler which submits job to grid using [DIRAC](http://diracgrid.org/).

Supported file systems

* **local**: Uploading or downloading of files does nothing
* **sftp**: Uploading or downloading of files is done using SFTP.
* **dirac**, Uploading or downloading of files using [DIRAC](http://diracgrid.org/).

When the filesystem is on a remote system with non-shared file system or a
different user, then

* the input files will be uploaded before submission to the scheduler and
* the output files will be downloaded after the job has completed.

Destinations can be configured in the `config.yaml` file under `destinations`
key. By default a single slot in-memory scheduler with a local filesystem is
used.

A destination has its own authentication mechanism.
When a job is submitted by any user of the web service,
it will be executed by the username/proxy that is configured in the destination.

### Example of running jobs on the local system

```yaml
destinations:
  local:
    scheduler:
      type: memory
      slots: 1
    filesystem:
      type: local
```

### Example of running jobs on a slurm Docker container

To use this, start a [container](
https://github.com/xenon-middleware/xenon-docker-images/tree/master/slurm-20
) with `docker run --detach --publish 10022:22
xenonmiddleware/slurm:20`

```yaml
destinations:
  slurmcontainer:
    scheduler:
      type: slurm
      partition: mypartition
      ssh_config:
        port: 10022
        hostname: localhost
        username: xenon
        password: javagat
    filesystem:
      type: sftp
      ssh_config:
        port: 10022
        hostname: localhost
        username: xenon
        password: javagat
      entry: /home/xenon
```

### Example of running jobs on an async Redis queue (arq) with single worker

Requires a Redis server on default port to be running
with `docker run --detach --publish 6379:6379 redis:7`.

Requires at least one arq worker to run in another shell
with same config file with `bartender perform --config config.yaml`.

```yaml
destinations:
  redis:
    scheduler:
      type: arq
      redis_dsn: redis://localhost:6379
      max_jobs: 1
      job_timeout: PT12H  # 12 hours
    filesystem:
      type: local
```

### Example of running jobs with multiple destinations and workers

The bartender web service and the Redis server are
running on <https://bartender.uu.nl> machine.

Destinations:

* small, jobs that are small enough to run on same machine as bartender web service.
  * On machine start single worker with `bartender perform --destination small`
  * A maximum of 10 jobs can run at the same time and
    they will share the cpus on the machine.
* medium, jobs that are small enough to be transfered to the grid
  * On each grid machine you should have bartender installed and
    have the same config file.
  * On each grid machine that you want to run jobs on,
    start a single worker with `bartender perform --destination medium`
  * The workers on the grid will need to communicate with the Redis server.
  * On each machine a single job will run at a time and the job can use all cpus.
* large, jobs that are too big to run anywhere else should by run on the hpc cluster.
  * On the clusters shared filesystem you should have bartender installed and
    have the same config file.
  * On each cluster compute node that you want to run jobs on,
    start a single worker with `bartender perform --destination large`
  * The workers on the cluster will need to communicate with the Redis server.
  * On each node a maxium of two jobs will run at a time and
    each job can use halve the cpus on a node.

```yaml
destination_picker: custom.picker
destinations:
  small:
    scheduler:
       type: arq
       redis_dsn: redis://localhost:6379
       max_jobs: 10
       job_timeout: P5M  # 5 minutes
    filesystem:
       type: local
  medium:
    scheduler:
       type: arq
       redis_dsn: rediss://someusername:somestrongpassword@bartender.uu.nl:6379
       queue: medium
       max_jobs: 1
       job_timeout: PT2H  # 2 hours
    filesystem:
       type: dirac
  large:
    scheduler:
       type: arq
       redis_dsn: rediss://someusername:somestrongpassword@bartender.uu.nl:6379
       queue: large
       max_jobs: 2
       job_timeout: PT12H  # 12 hours
    filesystem:
       type: sftp
       hostname: headnode.cluster.uu.nl
```

When Redis server is accessible by anyone on the Internet or cluster then
it should be more protected, like adding authentication, encryption
and firewall rules.

The destination picker could look something like:

```python
# In custom.py

def picker(
    job_dir: Path,
    application_name: str,
    user: User,
    context: "Context",
) -> str:
  # Calculate size of job_dir in bytes
  size = sum(file.stat().st_size for file in job_dir.rglob('*'))
  if size < 100_000:
    return 'small'
  elif size > 10_000_000:
    return 'large'
  return 'medium'
```

### DIRAC support

If you need [DIRAC](http://diracgrid.org/) support create a conda environment
instead of creating a virtual environment.

```bash
mamba create --name bartender dirac-grid python=3.10 poetry=1.5.1
conda activate bartender
poetry install
```

The conda environment contains all DIRAC dependencies and DIRAC itself.

(Cannot use `poetry install --with=dirac` as Poetry gets stuck resolving
dependencies because it ignores the already installed DIRAC dependencies.)

On the compute node it is expected that

1. `dirac-dms-get-file` + `dirac-dms-add-file` commands are available
1. `tar` command is available
1. If `apptainer_image` is set in scheduler configuration
   then `apptainer` command is available.
   If set to path on cvmfs then `/cvmfs` should be mounted.
1. Application command works.

### Example of running jobs on a DIRAC grid running inside a Docker container

<details>
<summary>
Requires a DIRAC grid to be running inside a Docker container
</summary>

This repostory contains a Docker Compose file to run bartender
with database and a DIRAC server.

```bash
docker compose -f deploy/docker-compose.dirac.yml up
```

(To start fresh, remove existing volumes with
`docker compose -f deploy/docker-compose.dirac.yml down --volumes`
)

The config.yaml in current working directory is used.

</details>

```yaml
destinations:
  grid:
    scheduler:
      type: dirac
      storage_element: StorageElementOne
      proxy:
        log_level: DEBUG
    filesystem:
      type: dirac
      lfn_root: /tutoVO/user/c/ciuser/bartenderjobs
      storage_element: StorageElementOne
      proxy:
        log_level: DEBUG
```

## Destination picker

If you have multiple applications and job destinations you need some way to
specify to which destination a job should be submitted. A Python function can be
used to pick a destination. By default jobs are submitted to the first
destination.

To use a custom picker function set `destination_picker`.
The value should be formatted as `<module>:<function>` or
`<path to python file>:<function>`.
The picker function should have type
[bartender.picker.DestinationPicker](
https://github.com/i-VRESSE/bartender/blob/bdbef5176e05c498b37f4ada2bf7c09ad0e7b853/src/bartender/picker.py#L8
). For example to rotate over each
destination use:

```yaml
destination_picker: bartender.picker.pick_round
```

## Job flow

Diagram of a job flowing through web service, schedulers and filesystems.

```mermaid
graph TD
    A[User upload] --> B{Pick destination}
    A2[User status] --> I{Retrieve status\nfrom scheduler}
    I -->|Completed| J[Copy output files\nfrom remote storage\nto web service]
    I -->|Incomplete| I
    J --> Z[Show results]
    B -->|Memory| D[Run in in-memory queue]
    B -->|Redis| E[Add job description\n to queue]
    E --> E2{Wait for work}
    subgraph redisworker
        E3 --> E2
        E2 -->|Job description| E3[Run command]
    end
    B -->|Slurm| F[Copy input files\nfrom web service\nto sftp server]
    F --> H[Sbatch]
    B -->|Dirac| G[Copy input files\nfrom web service\nto grid storage]
    G --> K[Wms job submit]
    K --> R[Install command]
    K --> O[Copy input files\nfrom grid storage\nto compute node]
    subgraph diracjob
        R --> P
        O --> P[Run command]
        P --> Q[Copy output files\nfrom compute node\nto grid storage]
    end
```

## Interactive applications

Interactive applications run quick commands (< 30 seconds)
in the output of a completed job on the web server.

An interactive app should

* be quick to run (< 30 seconds)
* produce very little output (stdout, stderr, files)
* in the job directory only write new files or overwrite its own files.
* not have any arguments that can leak information,
     for example paths to files outside the job directory.

The interactive application can be configured in the `config.yaml`
file under `interactive_applications` key.

For example, a user can run a job that generates scores
(Haddock3 with caprieval module) and then run an interactive application that
re-calculates the scores with different weights.

```yaml
interactive_applications:
    rescore:
        command_template: >
            haddock3-re score
            --w_elec {{w_elec|q}} --w_vdw {{w_vdw|q}} --w_desolv {{w_desolv|q}} --w_bsa {{w_bsa|q}} --w_air {{w_air|q}}
            {{ capri_dir|q }}
        description: Rescore a HADDOCK run with different weights.
        job_application: haddock3
        input_schema:
            additionalProperties: false
            properties:
                capri_dir:
                    type: string
                w_air:
                    type: number
                w_bsa:
                    type: number
                w_desolv:
                    type: number
                w_elec:
                    type: number
                w_vdw:
                    type: number
            required:
                - capri_dir
                - w_elec
                - w_vdw
                - w_desolv
                - w_bsa
                - w_air
            type: object
```

A JSON body can be sent to the
`POST /api/job/{jobid}/interactive/rescore` endpoint.

The JSON body will be validated against the JSON schema
(version 2020-12) defined under the `input_schema` key.

The `command_template` value is a [Jinja template](https://palletsprojects.com/p/jinja/)
and will be used to render the validated JSON body into a command string.

The command is executed in the directory of the completed job
and the return code, standard out and standard error are returned.
To find the output files use the other job endpoints.

In the command template make sure to use the `|q` filter so the
user supplied values are [shell-escaped](https://docs.python.org/3/library/shlex.html#shlex.quote).
Also to prevent [unintended newlines](https://yaml.org/spec/1.2.2/#65-line-folding)
in the rendered command use `>` in YAML.

The `job_application` key can be set to only allow
a interactive application to run in jobs
that were submitted for that given application.
If not set then the interactive application can run in any job.

### Embedded files

Files can be embedded in the JSON body of the request.
The value should be base64 encoded string.
In the input schema for property value use something like

```yaml
type: string
contentEncoding: base64
contentMediaType: image/png
```

In the command template the property key will point to
a temporary file with the base64 decoded content.
