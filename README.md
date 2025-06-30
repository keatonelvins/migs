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
migs up my-mig --name my-dev-vm --async  # Don't wait for creation
```

### List your VMs
```bash
migs vms
```

### Sync VM state
```bash
migs sync  # Sync local VM list with GCP state
```

### Check VM connectivity
```bash
migs check my-dev-vm  # Test SSH connectivity
```

### SSH into a VM
```bash
migs ssh my-dev-vm
migs ssh my-dev-vm -- tmux attach  # Pass additional SSH arguments
```

### Run scripts
```bash
migs run my-dev-vm ./setup.sh  # Runs in tmux session
migs run my-dev-vm ./deploy.sh --session deploy  # Custom session name
```

### Upload files
```bash
migs upload my-dev-vm ./myfile.txt
migs upload my-dev-vm ./mydir/ /home/user/
```

### Download files
```bash
migs download my-dev-vm /remote/file.txt
migs download my-dev-vm /remote/dir/ ./local/
```

### Spin down a VM
```bash
migs down my-dev-vm
```

## SSH Config

The tool automatically updates your `~/.ssh/config` file with entries for your VMs, making them accessible in VS Code Remote Explorer.