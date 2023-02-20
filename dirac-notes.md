# Make DIRAC server to test bartender code against

<details>

<summary>~Vagrant VM with DIRAC server~Use dirac integration test script</summary>

Spinup docker containers which can be used to connect from bartender,
using https://github.com/DIRACGrid/DIRAC/blob/v8.0.13/integration_tests.py

Vagrantfile:

```ruby
Vagrant.configure("2") do |config|
  config.vm.box = "generic/ubuntu2204"
  config.vm.provider "virtualbox" do |vb|
     vb.memory = "8024"
  end
end
```

```shell
vagrant up
vagrant ssh
```

Install

```shell
sudo -i
apt update
apt install -y wget git ca-certificates \
    curl \
    gnupg \
    lsb-release



# Docker
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
usermod -aG docker vagrant

wget https://github.com/conda-forge/miniforge/releases/latest/download/Mambaforge-Linux-x86_64.sh
bash Mambaforge-Linux-x86_64.sh -b -p $HOME/mambaforge
rm Mambaforge-Linux-x86_64.sh
# Activate the environment manually the first time
eval "$("$HOME/mambaforge/bin/conda" shell.bash hook)"
# Make it so that conda doesn't automatically activate the base environment
conda config --set auto_activate_base false
# Automatically make the "conda" shell function available
conda init bash

# as vagrant user
git clone --depth 1 -b v8.0.13 https://github.com/DIRACGrid/DIRAC.git
cd DIRAC
mamba env create --name dirac-development --file environment.yml
conda activate dirac-development

# DIRACOS
# cd ~
# curl -LO https://github.com/DIRACGrid/DIRACOS2/releases/latest/download/DIRACOS-Linux-x86_64.sh
# bash DIRACOS-Linux-x86_64.sh
# source /home/vagrant/diracos/diracosrc
# pip install DIRAC

cd DIRAC
# ./integration_tests.py create --no-run-server-tests --no-run-client-tests

./integration_tests.py ??
```

To complicated, to use VM, switch to run integration_tests.py in bare-metal conda env

</details>

# Dirac integration test setup

Setup conda env by following [README.md#dirac-support](README.md#dirac-support).

Use https://github.com/DIRACGrid/DIRAC/blob/integration/integration_tests.py to setup a DIRAC server.

Get shallow clone of DIRAC to spinup server and client containers

```shell
git clone --depth 1 --single-branch --branch v8.0.14 https://github.com/DIRACGrid/DIRAC.git DIRAC
cd DIRAC
pip install gitpython packaging pyyaml typer
./integration_tests.py prepare-environment
./integration_tests.py install-server
# install-server can take a while >10min
./integration_tests.py install-client
```

<details>
<summary>FAILED: Try to use client config/certs/credentials outside container</summary>


```shell
# get client stuff
mkdir cc && cd cc
docker cp client:/home/dirac/ClientInstallDIR/etc etc
docker cp client:/home/dirac/ClientInstallDIR/bashrc ./
docker cp client:/home/dirac/ServerInstallDIR/user ./
docker cp client:/home/dirac/ClientInstallDIR/diracos/etc/dirac.cfg etc/
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' server
# Generate config with ip of server in cfg as hostname=server is not known outside docker-compose env
dirac-configure -S bartender-dirac \
-C dips://172.18.0.5:9135/Configuration/Server \
-W dips://172.18.0.5:9135 --SkipCAChecks
...
M2Crypto.SSL.Checker.WrongHost: Peer certificate subjectAltName does not match host, expected 172.18.0.5, got DNS:server, DNS:localhost
...

```
Available certs can not be used outside client container

TODO generate cert for docker host machine

</details>

## Run bartender tests inside client container

```
# configure local ce + pilot
docker exec -ti server bash
```

```
cd /home/dirac
source /home/dirac/CONFIG
source "${DIRAC_CI_SETUP_SCRIPT}"
source /home/dirac/ServerInstallDIR/bashrc
dirac-login -C "${SERVERINSTALLDIR}/user/client.pem" -K "${SERVERINSTALLDIR}/user/client.key" dirac_admin
ipython
```

```python
from DIRAC import initialize
initialize()
from DIRAC.ConfigurationSystem.Client.CSAPI import CSAPI
csAPI = CSAPI()
# https://dirac.readthedocs.io/en/latest/AdministratorGuide/Tutorials/installWMS.html
csAPI.setOption("Resources/Sites/DIRAC/DIRAC.Jenkins.ch/CEs/jenkins.cern.ch/CEType", "Local")
# Pilot
# {
#   Version = v8.0.14
#   CheckVersion = False
#   Command
#   {
#     Test = GetPilotVersion
#     Test += CheckWorkerNode
#     Test += InstallDIRAC
#     Test += ConfigureBasics
#     Test += ConfigureCPURequirements
#     Test += ConfigureArchitecture
#     Test += CheckCECapabilities
#     Test += LaunchAgent
#   }
#   GenericPilotGroup = dirac_user
#   GenericPilotUser = ciuser
#   pilotFileServer = dirac-tuto:8443
# }
csAPI.createSection('/Operations/MyDIRAC-Production')
csAPI.createSection('/Operations/MyDIRAC-Production/Pilot')
csAPI.setOption('/Operations/MyDIRAC-Production/Pilot/Version', 'v8.0.14')
csAPI.setOption('/Operations/MyDIRAC-Production/Pilot/CheckVersion', 'False')
csAPI.setOption('/Operations/MyDIRAC-Production/Pilot/GenericPilotGroup', 'dirac')
csAPI.setOption('/Operations/MyDIRAC-Production/Pilot/GenericPilotUser', 'dirac')
csAPI.createSection('/Operations/MyDIRAC-Production/Pilot/Command')
csAPI.setOption(
    "/Operations/MyDIRAC-Production/Pilot/Command/Test",
    "GetPilotVersion,CheckWorkerNode,InstallDIRAC,ConfigureBasics,ConfigureCPURequirements,ConfigureArchitecture,CheckCECapabilities,LaunchAgent",
)
# TODO have WebApp running, so pilotFileServer value has something running on it
# csAPI.setOption('/Operations/MyDIRAC-Production/Pilot/pilotFileServer', 'server:8443')

csAPI.setOption('/WebApp/StaticDirs','pilot')
csAPI.commit()
```

```shell
dirac-admin-allow-site DIRAC.Jenkins.ch "test" -E False
dirac-admin-sysadmin-cli --host server
```

```shell
restart WorkloadManagement *
# Commands at https://dirac.readthedocs.io/en/latest/AdministratorGuide/Tutorials/installWMS.html#installing-the-workloadmanagementsystem
# are mostly installed except few at the bottom of code block
install agent WorkloadManagement SiteDirector
install agent WorkloadManagement JobCleaningAgent
install agent WorkloadManagement PilotStatusAgent
install agent WorkloadManagement StalledJobAgent
install executor WorkloadManagement Optimizers -p Load=JobPath,JobSanity,InputData,JobScheduling
restart WorkloadManagement *
```

## Submit job in client container

```shell
docker exec -ti client bash
cd /home/dirac
source /home/dirac/CONFIG
source "${DIRAC_CI_SETUP_SCRIPT}"
source /home/dirac/ClientInstallDIR/bashrc

dirac-login -C "${SERVERINSTALLDIR}/user/client.pem" -K "${SERVERINSTALLDIR}/user/client.key"

git clone --depth 1 --branch 38-dirac https://github.com/i-VRESSE/bartender.git
cd bartender
pip install -e .
pip install ipython
ipython
```

```python
# From https://dirac.readthedocs.io/en/latest/UserGuide/GettingStarted/UserJobs/DiracAPI/index.html
from DIRAC import initialize
initialize()

from DIRAC.Interfaces.API.Job import Job
from DIRAC.Interfaces.API.Dirac import Dirac

dirac = Dirac()
j = Job()

j.setCPUTime(500)
j.setExecutable('/bin/echo hello')
j.setExecutable('/bin/hostname')
j.setExecutable('/bin/echo hello again')
j.setName('API')

jobID = dirac.submitJob(j)
print('Submission Result: ', jobID)

dirac.getJobStatus(jobID['JobID'])
{'OK': True,
 'Value': {1: {'ApplicationStatus': 'Unknown',
   'MinorStatus': 'Pilot Agent Submission',
   'Status': 'Waiting',
   'Site': 'ANY'}}}

# job pilot agent not running/misconfigured??

dirac.getOutputSandbox(jobID['JobID'])
dirac.killJob(jobID['JobID'])
dirac.deleteJob(jobID['JobID'])

jobID2 = dirac.submitJob(j, mode='local')
# completes, but not useful, as to different from wms
```

TODO job with sandbox input/output + grid storage for input/output files + apptainer
