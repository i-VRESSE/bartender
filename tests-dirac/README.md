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
!mkdir /tmp/j1
from bartender.schedulers.dirac import DiracScheduler, DiracSchedulerConfig
from bartender.schedulers.abstract import JobDescription

scheduler = DiracScheduler(DiracSchedulerConfig())
description = JobDescription(
    command="echo -n hello",
    job_dir="/tmp/j1",
)
jdl = await scheduler._jdl_script(description)
print(jdl)
!cat /tmp/j1/job.jdl
!cat /tmp/j1/job.sh

jid = await scheduler.submit(description)
print(jid)
state = await scheduler.state(jid)
print(state)
```

Stuck at job failing with uploading output

```
2023-04-25 09:19:42 UTC None/[3]JobWrapper INFO: Output data files stdout.txt, stderr.txt to be uploaded to ['StorageElementOne'] SE
2023-04-25 09:19:42 UTC None/[3]JobWrapper INFO: Found a pattern in the output data file list, files to upload are: stdout.txt
GUIDs not found from POOL XML Catalogue (and were generated) for: stdout.txt
Attempting dm.putAndRegister ('/tutoVO/user/c/ciuser/tutoVO/user/c/ciuser/bartenderjobs/j3/stdout.txt','/home/diracpilot/shared/work/340BFD60/DIRAC_1U7GXBpilot/3/stdout.txt','StorageElementOne',guid='5B466EAB-8FDF-D177-C8C0-6962CF89DE75',catalog='[]', checksum = '3c87e20e')
Error sending accounting record URL for service Accounting/DataStore not found
Error sending accounting record URL for service Accounting/DataStore not found
dm.putAndRegister successfully uploaded and registered stdout.txt to StorageElementOne
2023-04-25 09:19:42 UTC None/[3]JobWrapper INFO: "stdout.txt" successfully uploaded to "StorageElementOne" as "LFN:/tutoVO/user/c/ciuser/tutoVO/user/c/ciuser/bartenderjobs/j3/stdout.txt"
JobWrapper raised exception while processing output files
Traceback (most recent call last):
  File "/home/diracpilot/shared/work/340BFD60/DIRAC_1U7GXBpilot/job/Wrapper/Wrapper_3", line 209, in execute
    result = job.processJobOutputs()
  File "/home/diracpilot/shared/work/340BFD60/DIRAC_1U7GXBpilot/diracos/lib/python3.9/site-packages/DIRAC/WorkloadManagementSystem/JobWrapper/JobWrapper.py", line 873, in processJobOutputs
    if not result_sbUpload["OK"]:
UnboundLocalError: local variable 'result_sbUpload' referenced before assignment
2023-04-25 09:19:43 UTC None/[3]JobWrapper INFO: EXECUTION_RESULT[CPU] in sendJobAccounting 0.00 0.01 0.53 0.04 1.00
```
