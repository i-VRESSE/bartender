# Configuration

This application can be configured with environment variables and `config.yaml`
file. The environment variables are for FastAPI settings like http port and user
management. The `config.yaml` file is for non-FastAPI configuration like which
[application can be submitted](#applications) and [where they should
submitted](#job-destinations).

## Environment variables

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

## Configuration file

Bartender uses a configuration file for setting up applications and destinations. An
[example configuration file](https://github.com/i-VRESSE/bartender/blob/main/config-example.yaml)
is shipped with the repository. Here, we explain the options in more detail.

## Applications

Bartender accepts jobs for different applications.

Applications can be configured in the `config.yaml` file under `applications` key.

For example

```yaml
applications:
  app1:
    command: wc $config
    config: README.md
  haddock3:
    command: haddock3 $config
    config: workflow.cfg
```

* The key is the name of the application
* The `config` key is the config file that must be present in the uploaded archive.
* The `command` key is the command executed in the directory of the unpacked archive that the consumer uploaded. The `$config` in command string will be replaced with value of the config key.

## Job destinations

Bartender can run job in different destinations.

A destination is a combination of a scheduler and filesystem.
Supported schedulers
* memory, Scheduler which has queue in memory and can specified number of jobs (slots) concurrently.
* slurm, Scheduler which calls commands of [Slurm batch scheduler](https://slurm.schedmd.com/) on either local machine or remote machine via SSH.

Supported file systems
* local: Uploading or downloading of files does nothing
* sftp: Uploading or downloading of files is done using SFTP.

When the filesystem is on a remote system with non-shared file system or a different user, then
* the input files will be uploaded before submission to the scheduler and
* the output files will be downloaded after the job has completed.

Destinations can be configured in the `config.yaml` file under `destinations` key.
By default a single slot in-memory scheduler with a local filesystem is used.

**Example of running jobs on the local system**

```yaml
destinations:
  local:
    scheduler:
      type: memory
      slots: 1
    filesystem:
      type: local
```

**Example of running jobs on a slurm Docker container**

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

## Destination picker

If you have multiple applications and job destinations you need some way to
specify to which destination a job should be submitted. A Python function can be
used to pick a destination. By default jobs are submitted to the first
destination.

To use a custom picker function set `destination_picker`. The value should be
formatted as `<module>:<function>`. The picker function should have type
`bartender.picker.DestinationPicker`. For example to rotate over each
destination use:

```yaml
destination_picker: bartender.picker.pick_round
```

## Job root dir

By default, the files of jobs are stored in `/tmp/jobs`. To change the
directory, set the `job_root_dir` parameter in the configuration file to a valid
path.

```
job_root_dir: /tmp/jobs
```