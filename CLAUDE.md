# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MIGs is a Python CLI tool for managing Google Cloud Managed Instance Groups (MIGs), providing a developer-friendly interface for spinning up and managing VMs with automatic SSH config management for VS Code integration.

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

# Run tests (currently no tests configured)
make test

# Clean build artifacts
make clean
```

### Release Process
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

- **cli.py**: Main entry point and command definitions using Click framework. All user-facing commands are defined here with decorators like `@cli.command()`.

- **gcloud.py**: Wrapper around gcloud CLI commands. Key functions:
  - `list_migs()`: Lists all MIGs in the project
  - `resize_mig()`: Creates new VM instances
  - `delete_instance()`: Removes VM instances
  - `get_instance_ip()`: Retrieves external IP addresses
  - Authentication handling with automatic prompt for login

- **storage.py**: Local VM tracking using JSON storage at `~/.migs/vms.json`. Manages:
  - Personal VM inventory with custom names
  - Sync state between local storage and GCP
  - Auto-deletion scheduling

- **ssh_config.py**: SSH configuration management for VS Code Remote Explorer:
  - Automatically adds/removes SSH config entries
  - Uses format: `Host migs-<vm-name>`
  - Manages ProxyCommand for GCP connectivity

### Key Design Patterns

1. **Error Handling**: All gcloud operations include authentication error handling with automatic prompts for re-authentication.

2. **Async Operations**: The `up` command supports `--async` flag for non-blocking VM creation.

3. **Rich Output**: Uses Rich library for formatted tables and progress indicators.

4. **State Management**: Local JSON storage tracks personal VMs with periodic sync against GCP state.

5. **Environment Variables**: Both `ssh` and `run` commands automatically detect and upload `.env` files from the current directory, sourcing them with `set -a; source /tmp/.env; set +a`.

## Important Implementation Details

- All VM operations are performed through subprocess calls to `gcloud` CLI
- SSH config entries are automatically managed to enable VS Code Remote SSH
- The tool assumes SSH keys are already configured in GCP project metadata
- Auto-deletion uses VM metadata labels (`ttl` and `created-at`) for scheduling
- File transfers (`upload`/`download`) use gcloud compute scp under the hood
- The `run` command now accepts script arguments: `migs run vm-name script.sh arg1 arg2`
- `.env` files are uploaded to `/tmp/.env` and sourced automatically for both `ssh` and `run` commands
- The `_upload_env_file()` helper method handles .env file uploads to avoid code duplication