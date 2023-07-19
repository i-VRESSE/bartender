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

To login to web service you need to generate token with
the private counterpart of the public key.
See [configuration.md#authentication](configuration.md#authentication).
To use `bartender generate-token` command inside container you need make
the private key available in the container.
