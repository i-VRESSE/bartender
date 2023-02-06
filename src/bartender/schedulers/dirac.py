from textwrap import dedent
from DIRAC import initialize
from DIRAC.WorkloadManagementSystem.Client.WMSClient import WMSClient
from DIRAC.WorkloadManagementSystem.Client.JobMonitoringClient import JobMonitoringClient
from bartender.db.models.job_model import State

from bartender.schedulers.abstract import AbstractScheduler, JobDescription

dirac_status_map: dict[str, State] = {
            "Waiting": "queued",
            "Done": "ok",
            # TODO add all possible dirac job states
        }

# TODO make proper async with loop.run_in_executor
# TODO test against Dirac in testcontainer and/or against live?

class DiracScheduler(AbstractScheduler):
    def __init__(self):
        initialize()
        self.wms_client = WMSClient()
        self.monitoring = JobMonitoringClient()

    async def submit(self, description: JobDescription) -> str:
        job_input_files = [f'"{f.absolute()}"' for f in description.job_dir.rglob('*')]
        input_sandbox = ','.join(job_input_files)
        jdl = dedent(f"""\
            Executable = "/bin/sh";
            Arguments = "-c \"{description.command}\"";
            InputSandBox = {{{input_sandbox}}};
            StdOutput = “stdout.txt”;
            StdError = “stderr.txt”;
            OutputSandbox = {{“stdout.txt”,”stderr.txt”}};
        """)
        # TODO ship application to where it is run
        # TODO get output files of job in grid storage
        # TODO when input sandbox is to big then upload to grid storage 
        result = self.wms_client.submitJob(jdl)
        if not result['OK']:
            raise RuntimeError(result['Message'])
        return result['Value']
    
    async def state(self, job_id: str) -> State:
        # Dirac has Status,MinorStatus,ApplicationStatus 
        # TODO Should we also store MinorStatus,ApplicationStatus?
        result = self.monitoring.getJobsStatus(job_id)
        if not result['OK']:
            raise RuntimeError(result['Message'])
        dirac_status = result["Value"][job_id]["Status"]
        return dirac_status_map[dirac_status]

    async def states(self, job_ids: list[str]) -> list[State]:
        result = self.monitoring.getJobsStatus(job_ids)
        if not result['OK']:
            raise RuntimeError(result['Message'])

        # TODO result can be in different order then job_ids        
        return [dirac_status_map[v["Status"]] for v in result["Value"]]

    async def cancel(self, job_id: str) -> None:
        state = await self.state(job_id)
        if state == 'running':
            self.wms_client.killJob(job_id)
        else:
            self.wms_client.deleteJob(job_id)
            # TODO or removeJob()?
