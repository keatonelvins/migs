# CLAUDE.md

This file is for YOU Claude! Please update this document if anything is out-of-date.

## Project Overview

MIGs is a Python CLI tool for managing Google Cloud Managed Instance Groups (MIGs), providing a developer-friendly interface for spinning up and managing VMs with automatic SSH config management for VS Code integration. Supports both single-VM and multi-node cluster deployments.

## Development Commands

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

# Production upload to PyPI
make upload

# Full release (clean, build, upload)
make release
```

## Architecture

The codebase follows a modular architecture with clear separation of concerns:

### Core Modules

- **cli.py**: Main entry point and command definitions using Click framework. All user-facing commands are defined here with decorators like `@cli.command()`. Key commands:
  - `up`: Create VMs (supports multi-node with `-n` parameter)
  - `down`: Delete VMs (supports `--all` for group deletion)
  - `run`: Execute scripts (supports `--all` for multi-node execution)
  - `vms`: List VMs with group visualization

- **gcloud.py**: Wrapper around gcloud CLI commands. Key functions:
  - `list_migs()`: Lists all MIGs in the project
  - `create_resize_request()`: Creates new VM instances via resize requests
  - `wait_for_vm()`: Waits for VMs and returns their details (supports multiple VMs)
  - `delete_vm()`: Removes VM instances
  - `get_instance_details()`: Retrieves VM details including external IP
  - Authentication handling with automatic prompt for login

- **storage.py**: Local VM tracking using JSON storage at `~/.migs/vms.json`. Manages:
  - Personal VM inventory with custom names
  - Sync state between local storage and GCP
  - Auto-deletion scheduling
  - Multi-node group tracking with `group_id`
  - Group queries with `get_vms_in_group()`

- **ssh_config.py**: SSH configuration management for VS Code Remote Explorer:
  - Automatically adds/removes SSH config entries
  - Uses format: `Host migs-<vm-name>`
  - Manages ProxyCommand for GCP connectivity

### Key Design Patterns

1. **Error Handling**: All gcloud operations include authentication error handling with automatic prompts for re-authentication.

2. **Long-Running Operations**: VM creation waits up to 15 minutes (single VM) or 30 minutes (multi-node) for completion.

3. **Rich Output**: Uses Rich library for formatted tables and progress indicators.

4. **State Management**: Local JSON storage tracks personal VMs with periodic sync against GCP state.

5. **Environment Variables**: Both `ssh` and `run` commands automatically detect and upload `.env` files from the current directory:
   - Sources with `set -a; source /tmp/.env; set +a`
   - Automatically configures GitHub CLI auth if `GITHUB_TOKEN` is present
   - Enables seamless access to private repositories

6. **Multi-Node Support**: 
   - Single resize request creates multiple VMs efficiently
   - VMs are named with numeric suffixes (name1, name2, etc.)
   - Group operations via `--all` flag on `run` and `down` commands
   - Visual grouping in `vms` command output

## Important Implementation Details

- All VM operations are performed through subprocess calls to `gcloud` CLI
- SSH config entries are automatically managed to enable VS Code Remote SSH
- The tool assumes SSH keys are already configured in GCP project metadata
- Auto-deletion uses VM metadata labels (`ttl` and `created-at`) for scheduling
- File transfers (`upload`/`download`) use gcloud compute scp under the hood
- The `run` command now accepts script arguments: `migs run vm-name script.sh arg1 arg2`
- `.env` files are uploaded to `/tmp/.env` and sourced automatically for both `ssh` and `run` commands
- The `_upload_env_file()` helper method handles .env file uploads to avoid code duplication
- GitHub authentication is automatically configured if `GITHUB_TOKEN` is found in `.env`
- Multi-node clusters:
  - Created with single resize request for efficiency
  - Tracked using `group_id` in storage (format: `{mig_name}-{request_id}`)
  - VM naming: base name + numeric suffix (myvm1, myvm2, etc.)
  - Group operations supported via `--all` flag

## Usage Examples

### Single VM
```bash
migs up my-mig --name myvm
migs ssh myvm
migs down myvm
```

### Multi-Node Cluster
```bash
# Create 4-node cluster
migs up my-mig --name cluster -c 4

# SSH to specific nodes
migs ssh cluster1
migs ssh cluster2

# Run script on all nodes
migs run cluster1 train.py --all

# Shut down entire cluster
migs down cluster1 --all
```

### GitHub Authentication
```bash
# Create .env file with GitHub token
echo "GITHUB_TOKEN=ghp_your_token_here" > .env

# SSH to VM - GitHub CLI will be automatically authenticated
migs ssh myvm

# Run script that needs private repo access
migs run myvm clone_private_repo.sh
```