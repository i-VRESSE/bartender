"""Tiny apps that can be run on a completed job.

Tiny apps are small interactive calculations that can be run within a request-response cycle (<30s).

A tiny app should:

1. be defined as a module within this package.
2. have a module level docstring that describes itself.
3. have a `TinyArguments` Pydantic model that describes the request body.
4. have a `main` function that
    1. takes the TinyArguments object and the job directory as arguments
    2. does the calculation
    3. returns a `TinyAppResult` Pydantic model.
5. only overwrite its own files in the job directory.

Example:

```python
client.post('/api/job/123/tinyapp/rescore', json={
    'module': 1,
    'w_elec': 0.2,
    'w_vdw': 0.2,
    'w_desolv': 0.2,
    'w_bsa': 0.1,
    'w_air': 0.3,
})
# Find the results in the job directory somewhere
files = client.get('/api/job/123/files')
```
"""

from asyncio import create_subprocess_shell
from importlib import import_module
from pathlib import Path
from pkgutil import walk_packages
from types import ModuleType

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from bartender.web.api.job.views import CurrentCompletedJobDir

"""
Notes for self:

Pros:
* Can use job directory without having to copy stuff around
Cons:
* Define a Python module for each tiny app. In addition to bartender original setup with env vars and config.yaml.
* Each tinyapp will have own openapi endpoint. So the generated openapi client will be specific to bartender instance.
* Different then rest of bonvinlab apps.
"""


class TinyAppResult(BaseModel):
    returncode: int
    stderr: str
    stdout: str


async def shell(job_dir: Path, command: str) -> TinyAppResult:
    proc = await create_subprocess_shell(
        command,
        cwd=job_dir,
    )
    returncode = await proc.wait()
    return TinyAppResult(
        returncode=returncode,
        stderr=proc.stderr,
        stdout=proc.stdout,
    )


def initialize_tinyapps_routes(app: FastAPI) -> None:
    # TODO get tinyapps package name from config
    package_name = "bartender.tinyapps"
    package = import_module(package_name)
    for module_info in walk_packages(
        path=package.__path__,
        prefix=package_name + ".",
        onerror=lambda x: None,
    ):
        modname = module_info.name
        # TODO to module add typings for main and TinyArguments
        module: ModuleType = import_module(modname)
        router = APIRouter()
        app_name = modname.replace(package_name + ".", "")

        @router.post("/{jobid}/tinyapp/" + app_name, summary=module.__doc__)
        async def run_tiny_app(
            arguments: module.TinyArguments,
            job_dir: CurrentCompletedJobDir,
        ) -> TinyAppResult:
            # TODO use queue like MemoryScheduler so only a couple of tinyapps can run at once
            # TODO use server side events to keep connection alive and/or to stream output to client???
            return await module.main(arguments, job_dir)

        app.include_router(router, prefix="/api/job", tags=["job"])
