# Deploy with docker compose

Create config file `config.yaml` as described at [configuration.md](configuration.md).
The `job_root_dir` property should be set to `/tmp/jobs`
which is a Docker compose volume.

Store public RSA key for JWT auth in `public_key.pem` file next to `config.yaml`.

Start with

```bash
docker compose -f deploy/docker-compose.yml up
```

Web service will running on <http://0.0.0.0:8000>.

To login to web service you need to generate token and sign it with
the private counterpart of the public key.g
If you want to generate a token with the
`docker compose -f deploy/docker-compose.yml exec api bartender generate-token` command
you should uncomment the private key volume bind in `deploy/docker-compose.yml`.
See [configuration.md#authentication](configuration.md#authentication).

## Link external directory as job

If you have a directory outside the bartender job root directory
that is the output of one the configured applications in bartender
then you might want to make it available as a job in bartender.

To do this you can create a symlink to the external directory
in the bartender job root directory,
by running the `bartender link` command.
See `bartender link --help` for more information.
