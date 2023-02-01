# Setup Dirac test env 

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
