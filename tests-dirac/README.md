# Dirac tests

Run tests within a container with Dicac client installed
against a containerized Dirac instance using Docker compose.

Uses [ghcr.io/xenon-middleware/diracclient:8.0.18](
https://github.com/orgs/xenon-middleware/packages/container/package/diracclient
) and [ghcr.io/xenon-middleware/dirac:8.0.18](
https://github.com/orgs/xenon-middleware/packages/container/package/dirac
) Docker images respectivly.

## Run

```shell
docker compose -f tests-dirac/docker-compose.yml run test 'pip install -e .[dev] && dirac-proxy-init -g dirac_user && pytest -vv tests-dirac'
# TODO move dirac-proxy-init to scheduler/filesytem code
# TODO move command inside docker-compose.yml
```

## Interactive

To get a interactive python shell with dirac installed, run

```bash
docker compose -f tests-dirac/docker-compose.yml run test 'pip install -e .[dev] && dirac-proxy-init -g dirac_user && ipython'
```

See [test_it.py](test_it.py) for example usage of the DIRAC scheduler and filesystem.
