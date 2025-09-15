# migs - Google Cloud MIG CLI Tool

A command-line tool that wraps the gcloud CLI to provide an easier experience for managing Google Cloud Managed Instance Groups.

## Features

- List MIGs in your project
- Spin up/down VMs with exact custom names (auto-detects gcloud beta)
- Track your personal VMs
- Automatic SSH config management for VS Code Remote Explorer
- Easy file/directory uploads
- Multi-node cluster support with coordinated naming

## Installation

```bash
pip install migs
```

Or to build from source:
```bash
git clone https://github.com/keatonelvins/migs.git
cd migs
pip install -e .
```

## Prerequisites

- Python 3.8+
- gcloud CLI installed and authenticated (`gcloud auth login`)
- SSH keys configured for Google Compute Engine
- (Optional) gcloud beta component for exact VM naming (`gcloud components install beta`)

## Usage

### List all MIGs
```bash
migs list
```

### Spin up a VM
```bash
# With custom name (auto-detects gcloud beta availability)
migs up my-mig -n my-dev-vm           # Creates VM named "my-dev-vm" if beta available
migs up my-mig -n my-dev-vm -d 2h     # Auto-delete after 2 hours
migs up my-mig -n node -c 3           # Creates "node1", "node2", "node3"

# Without custom name (auto-generated)
migs up my-mig                        # Creates "my-mig-username-timestamp"

# Force stable API (bypass auto-detection)
migs up my-mig -n my-dev-vm --stable  # Use stable API (VM gets random name, mapped locally)
```

### List your VMs
```bash
migs vms
```

### Sync VM state
```bash
migs sync  # Sync local VM list with GCP state
migs sync --discover  # Also discover and claim untracked VMs
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
migs run my-dev-vm ./script.sh arg1 arg2  # Pass arguments to script
```

### Environment Variables (.env files)
Both `ssh` and `run` commands automatically detect and use `.env` files from your current directory:

```bash
# If .env exists in current directory, it will be uploaded and sourced
migs ssh my-dev-vm  # Variables from .env available in shell
migs run my-dev-vm ./app.sh  # Script runs with .env variables
```

The `.env` file is uploaded to `/tmp/.env` on the VM and sourced using `set -a; source /tmp/.env; set +a` to export all variables.

If `$GITHUB_TOKEN` exists in your `.env`, will also configure the gh cli.

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

### Multi-Node Cluster
```bash
# Create 4-node cluster with coordinated names
migs up my-mig --name cluster -c 4    # Creates cluster1, cluster2, cluster3, cluster4

# SSH to specific nodes
migs ssh cluster1
migs ssh cluster2

# Run script on all nodes
migs run cluster train.py --all

# Shut down entire cluster
migs down cluster --all
```

### Distributed Training (PyTorch)
The `--torchrun` flag automatically sets up environment variables for distributed training:

```bash
# Run distributed training script on all nodes
migs run cluster train.py --all --torchrun

# This automatically sets on each node:
- HEAD_NODE_IP: Internal IP of cluster1 (head node)
- HEAD_NODE_PORT: 5000
- NNODES: Total number of nodes
- NODE_RANK: 0 for head, 1+ for workers
- NPROC_PER_NODE: Auto-detected GPU count

# Your script can then use torchrun:
torchrun --nproc_per_node=$NPROC_PER_NODE \
         --nnodes=$NNODES \
         --node_rank=$NODE_RANK \
         --master_addr=$HEAD_NODE_IP \
         --master_port=$HEAD_NODE_PORT \
         your_training_script.py
```

## SSH Config

The tool automatically updates your `~/.ssh/config` file with entries for your VMs, making them accessible in VS Code Remote Explorer.

# Release Instructions
### Setup and Installation
```bash
# Install development dependencies and tool in editable mode
make dev-install
# Or directly with pip
pip install -e .

# Install packaging tools (needed for building/releasing)
make install-tools
```

### Building and Testing
```bash
# Build distribution packages
make build

# Clean build artifacts
make clean
```

### Release Process
First increment the `pyproject.toml` and `src/migs/__init__.py`
```bash
# Test upload to PyPI
make test-upload

# Full release (clean, build, upload)
make release
```

Add git version tag:
```bash
git tag v0.1.x
git push origin v0.1.x
```