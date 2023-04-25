# Dirac tests

Run tests within a container with Dicac client installed against a containerized Dirac instance using Docker compose.

Uses [ghcr.io/xenon-middleware/diracclient:8.0.18](https://github.com/orgs/xenon-middleware/packages/container/package/diracclient) and [ghcr.io/xenon-middleware/dirac:8.0.18](https://github.com/orgs/xenon-middleware/packages/container/package/dirac) Docker images respectivly.

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

```python
!mkdir /tmp/j6
!echo bla > /tmp/j6/input.txt
from bartender.schedulers.dirac import DiracScheduler, DiracSchedulerConfig
from bartender.schedulers.abstract import JobDescription

scheduler = DiracScheduler(DiracSchedulerConfig())
description = JobDescription(
    command="/bin/hostname;/bin/date;/bin/ls -la;mkdir output;wc -l input.txt > output/output.txt",
    job_dir="/tmp/j6",
)
jdl = await scheduler._jdl_script(description)
print(jdl)
!cat /tmp/j6/job.jdl
!cat /tmp/j6/job.sh

jid = await scheduler.submit(description)
print(jid)
state = await scheduler.state(jid)
print(state)
```

Stuck at job uploading output as its flattened

```
2023-04-25 10:08:38 UTC None/[1]JobWrapper INFO: Found a pattern in the output data file list, files to upload are: job.sh, output/output.txt, stdout.txt, job.info, input.txt
GUIDs not found from POOL XML Catalogue (and were generated) for: job.sh, output/output.txt, stdout.txt, job.info, input.txt
...
Attempting dm.putAndRegister ('/tutoVO/user/c/ciuser/tutoVO/user/c/ciuser/bartenderjobs/j6/output.txt','/home/diracpilot/shared/work/AAF39273/DIRAC_FtmdcGpilot/1/output/output.txt','StorageElementOne',guid='5B5AAF9B-A8DE-05A9-5F47-C880078E39EA',catalog='[]', checksum = '1a2b041a')
Error sending accounting record URL for service Accounting/DataStore not found
Error sending accounting record URL for service Accounting/DataStore not found
dm.putAndRegister successfully uploaded and registered output/output.txt to StorageElementOne
2023-04-25 10:08:39 UTC None/[1]JobWrapper INFO: "output/output.txt" successfully uploaded to "StorageElementOne" as "LFN:/tutoVO/user/c/ciuser/tutoVO/user/c/ciuser/bartenderjobs/j6/output.txt"
```

Due to basename instead of relative_to at <https://github.com/DIRACGrid/DIRAC/blob/7abf70debfefa8135aeff439a3296f392ab8342b/src/DIRAC/WorkloadManagementSystem/JobWrapper/JobWrapper.py#L1075>
