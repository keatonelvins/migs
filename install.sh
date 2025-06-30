#!/bin/bash

echo "Installing migs CLI tool..."

# Create virtual environment (optional but recommended)
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
else
    source venv/bin/activate
fi

# Install the package
pip install -e .

echo "migs installed successfully!"
echo ""
echo "Usage examples:"
echo "  migs list         - List all MIGs"
echo "  migs up <mig>     - Spin up a VM"
echo "  migs vms          - List your VMs"
echo "  migs ssh <vm>     - SSH into a VM"
echo "  migs down <vm>    - Shut down a VM"