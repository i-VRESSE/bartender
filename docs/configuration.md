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

## Configuration file

Bartender uses a configuration file for setting up applications and
destinations. An [example configuration
file](https://github.com/i-VRESSE/bartender/blob/main/config-example.yaml) is
shipped with the repository. Here, we explain the options in more detail.

## Applications

Bartender accepts jobs for different applications.

Applications can be configured in the `config.yaml` file under `applications`
key.

For example

```yaml
applications:
  app1:
    command: wc $config
    config: README.md
  haddock3:
    command: haddock3 $config
    config: workflow.cfg
    allowed_roles:
      - haddock3:easy
```

* The key is the name of the application
* The `config` key is the config file that must be present in the uploaded
  archive.
* The `command` key is the command executed in the directory of the unpacked
  archive that the consumer uploaded. The `$config` in command string will be
  replaced with value of the config key.
* The `allowed_roles` key holds an array of role names, one of which a submitter
  should have. When key is not set or list is empty then any authorized user
  is allowed. See [User management docs](user_management.md#roles) how to
  grant/revoke roles to/from users.

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

Supported file systems

* **local**: Uploading or downloading of files does nothing
* **sftp**: Uploading or downloading of files is done using SFTP.

When the filesystem is on a remote system with non-shared file system or a
different user, then

* the input files will be uploaded before submission to the scheduler and
* the output files will be downloaded after the job has completed.

Destinations can be configured in the `config.yaml` file under `destinations`
key. By default a single slot in-memory scheduler with a local filesystem is
used.

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

To use this, start a container with `docker run --detach --publish 10022:22
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

## Destination picker

If you have multiple applications and job destinations you need some way to
specify to which destination a job should be submitted. A Python function can be
used to pick a destination. By default jobs are submitted to the first
destination.

To use a custom picker function set `destination_picker`. The value should be
formatted as `<module>:<function>`. The picker function should have type
[bartender.picker.DestinationPicker](
https://github.com/i-VRESSE/bartender/blob/bdbef5176e05c498b37f4ada2bf7c09ad0e7b853/src/bartender/picker.py#L8
). For example to rotate over each
destination use:

```yaml
destination_picker: bartender.picker.pick_round
```

## Job root dir

By default, the files of jobs are stored in `/tmp/jobs`. To change the
directory, set the `job_root_dir` parameter in the configuration file to a valid
path.

```yaml
job_root_dir: /tmp/jobs
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
