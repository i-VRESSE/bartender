# DIRAC tests

Run tests within a container with DIRAC client installed
against a containerized DIRAC server instance using Docker compose.

Uses [ghcr.io/xenon-middleware/diracclient:8.0.18](
https://github.com/orgs/xenon-middleware/packages/container/package/diracclient
) and [ghcr.io/xenon-middleware/dirac:8.0.18](
https://github.com/orgs/xenon-middleware/packages/container/package/dirac
) Docker images respectivly.

## Run

```shell
docker compose -f tests_dirac/docker-compose.yml run test 'pip install -e . && pytest -vv tests_dirac'
```

## Interactive

To get a interactive python shell, run

```bash
docker compose -f tests_dirac/docker-compose.yml run test 'pip install -e .[dev] && dirac-proxy-init -g dirac_user && ipython'
```

See [test_it.py](test_it.py) for example usage of the DIRAC scheduler and filesystem.

## Visual Studio Code

See [../docs/develop.md#DIRAC-grid](../docs/develop.md#DIRAC-grid) for instructions
on how to use the VS Code Devcontainer extension to develop with DIRAC.
