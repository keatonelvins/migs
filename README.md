# migs - Google Cloud MIG CLI Tool

A command-line tool that wraps the gcloud CLI to provide an easier experience for managing Google Cloud Managed Instance Groups.

## Features

- List MIGs in your project
- Spin up/down VMs with custom names
- Track your personal VMs
- Automatic SSH config management for VS Code Remote Explorer
- Easy file/directory uploads

## Installation

```bash
pip install -e .
```

## Prerequisites

- Python 3.8+
- gcloud CLI installed and authenticated (`gcloud auth login`)
- SSH keys configured for Google Compute Engine

## Usage

### List all MIGs
```bash
migs list
```

### Spin up a VM
```bash
migs up my-mig --name my-dev-vm
```

### List your VMs
```bash
migs vms
```

### SSH into a VM
```bash
migs ssh my-dev-vm
```

### Upload files
```bash
migs upload my-dev-vm ./myfile.txt
migs upload my-dev-vm ./mydir/ /home/user/
```

### Spin down a VM
```bash
migs down my-dev-vm
```

## SSH Config

The tool automatically updates your `~/.ssh/config` file with entries for your VMs, making them accessible in VS Code Remote Explorer.