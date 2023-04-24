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

Stuck at job failing with

```
dirac-wms-job-status 4
JobID=4 ApplicationStatus=Unknown; MinorStatus=Exception During Execution; Status=Failed; Site=MyGrid.Site1.uk;

dirac-wms-job-get-output 4
No Output sandbox found for job 4. Possible causes are: the job does not exist, no sandbox was registered or you do not have permission to access it.
ERROR 4: No Output sandbox found for job 4. Possible causes are: the job does not exist, no sandbox was registered or you do not have permission to access it.

dirac-wms-job-get-jdl 4
{'CPUTime': '86400',
 'DIRACSetup': 'MyDIRAC-Production',
 'Executable': '/tmp/j1/job.sh',
 'InputSandBox': ['/tmp/j1/job.sh'],
 'JobID': '4',
 'JobName': 'j1',
 'JobRequirements': '[    CPUTime = 86400;    OwnerDN = /C=ch/O=DIRAC/OU=DIRAC '
                    'CI/CN=ciuser;    OwnerGroup = dirac_user;    Setup = '
                    'MyDIRAC-Production;    UserPriority = 1;    '
                    'VirtualOrganization = tutoVO;  ]',
 'OutputSandbox': ['stdout.txt', 'stderr.txt'],
 'Owner': 'ciuser',
 'OwnerDN': '/C=ch/O=DIRAC/OU=DIRAC CI/CN=ciuser',
 'OwnerGroup': 'dirac_user',
 'OwnerName': 'ciuser',
 'Priority': '1',
 'StdError': 'stderr.txt',
 'StdOutput': 'stdout.txt',
 'VirtualOrganization': 'tutoVO'}
```

jdl of <https://dirac.readthedocs.io/en/latest/UserGuide/Tutorials/JDLsAndJobManagementBasic/index.html#jobs-with-input-sandbox-and-output-sandbox> is

```
{'CPUTime': '86400',
 'DIRACSetup': 'MyDIRAC-Production',
 'Executable': 'testJob.sh',
 'InputSandbox': ['testJob.sh',
                  'SB:ProductionSandboxSE|/SandBox/c/ciuser.dirac_user/cff/794/cff794d91a819d5eda8396f4f2e5ebf3.tar.bz2'],
 'JobID': '2',
 'JobName': 'InputAndOuputSandbox',
 'JobRequirements': '[    CPUTime = 86400;    OwnerDN = /C=ch/O=DIRAC/OU=DIRAC '
                    'CI/CN=ciuser;    OwnerGroup = dirac_user;    Setup = '
                    'MyDIRAC-Production;    UserPriority = 1;    '
                    'VirtualOrganization = tutoVO;  ]',
 'OutputSandbox': ['StdOut', 'StdErr'],
 'Owner': 'ciuser',
 'OwnerDN': '/C=ch/O=DIRAC/OU=DIRAC CI/CN=ciuser',
 'OwnerGroup': 'dirac_user',
 'OwnerName': 'ciuser',
 'Priority': '1',
 'StdError': 'StdErr',
 'StdOutput': 'StdOut',
 'VirtualOrganization': 'tutoVO'}
```

Which looks different from the one via DiracScheduler
