import os
import re
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from migs.gcloud import GCloudWrapper, AuthenticationError
from migs.storage import VMStorage
from migs.ssh_config import SSHConfigManager

console = Console()
gcloud = GCloudWrapper()
storage = VMStorage()
ssh_manager = SSHConfigManager()


@click.group()
def cli():
    """migs - Manage Google Cloud Managed Instance Groups with ease"""
    pass


@cli.command(name='list')
def list_migs():
    """List all MIGs in the current project"""
    try:
        migs = gcloud.list_migs()
        
        if not migs:
            console.print("[yellow]No MIGs found in the current project[/yellow]")
            return
        
        table = Table(title="Managed Instance Groups")
        table.add_column("Name", style="cyan")
        table.add_column("Zone", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Target Size", style="yellow")
        
        for mig in migs:
            table.add_row(
                mig["name"],
                mig["zone"],
                str(mig["size"]),
                str(mig["targetSize"])
            )
        
        console.print(table)
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")


@cli.command()
@click.argument("mig-name")
@click.option("--name", help="Custom name for your VM")
@click.option("--zone", help="Zone (will auto-detect if not specified)")
@click.option("--async", "async_mode", is_flag=True, help="Don't wait for VM creation to complete")
def up(mig_name, name, zone, async_mode):
    """Spin up a new VM in the specified MIG"""
    try:
        if not zone:
            zone = gcloud.get_mig_zone(mig_name)
            if not zone:
                console.print(f"[red]Could not find zone for MIG: {mig_name}[/red]")
                return
        
        console.print(f"[cyan]Creating resize request for MIG: {mig_name}[/cyan]")
        request_id = gcloud.create_resize_request(mig_name, zone, 1)
        
        console.print(f"[green]Resize request created: {request_id}[/green]")
        
        if async_mode:
            console.print("[yellow]VM creation initiated (async mode)[/yellow]")
            console.print("[cyan]Check status with: migs vms[/cyan]")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[yellow]Waiting for VM creation...", total=None)
            
            vm_info = gcloud.wait_for_vm(mig_name, zone, request_id, progress_callback=lambda: progress.advance(task))
        
        if vm_info:
            storage.save_vm(vm_info["name"], mig_name, zone, custom_name=name)
            ssh_manager.add_vm_to_config(vm_info, custom_name=name)
            
            display_name = name or vm_info["name"]
            console.print(f"[green]✓ VM '{display_name}' is ready![/green]")
            console.print(f"[cyan]SSH: migs ssh {display_name}[/cyan]")
        else:
            console.print("[red]Failed to create VM (timeout)[/red]")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("vm-name")
def down(vm_name):
    """Spin down a VM"""
    try:
        vm_data = storage.get_vm(vm_name)
        if not vm_data:
            console.print(f"[red]VM '{vm_name}' not found in your VMs[/red]")
            return
        
        console.print(f"[yellow]Shutting down VM: {vm_name}[/yellow]")
        
        success = gcloud.delete_vm(
            vm_data["instance_name"],
            vm_data["zone"],
            vm_data["mig_name"]
        )
        
        if success:
            storage.remove_vm(vm_name)
            ssh_manager.remove_vm_from_config(vm_name)
            console.print(f"[green]✓ VM '{vm_name}' has been shut down[/green]")
        else:
            console.print(f"[red]Failed to shut down VM[/red]")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
def vms():
    """List your personal VMs"""
    vms = storage.list_vms()
    
    if not vms:
        console.print("[yellow]No personal VMs found[/yellow]")
        return
    
    table = Table(title="Your VMs")
    table.add_column("Name", style="cyan")
    table.add_column("Instance", style="green")
    table.add_column("MIG", style="yellow")
    table.add_column("Zone", style="yellow")
    table.add_column("Created", style="blue")
    
    for vm in vms:
        table.add_row(
            vm["display_name"],
            vm["instance_name"],
            vm["mig_name"],
            vm["zone"],
            vm["created_at"]
        )
    
    console.print(table)


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("vm-name")
@click.argument("ssh-args", nargs=-1, type=click.UNPROCESSED)
def ssh(vm_name, ssh_args):
    """SSH into a VM (supports passing additional SSH arguments)"""
    try:
        vm_data = storage.get_vm(vm_name)
        if not vm_data:
            console.print(f"[red]VM '{vm_name}' not found[/red]")
            return
        
        gcloud.ssh_to_vm(vm_data["instance_name"], vm_data["zone"], list(ssh_args) or None)
        
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("vm-name")
@click.argument("local-path")
@click.argument("remote-path", required=False)
def upload(vm_name, local_path, remote_path):
    """Upload files or directories to a VM"""
    try:
        vm_data = storage.get_vm(vm_name)
        if not vm_data:
            console.print(f"[red]VM '{vm_name}' not found[/red]")
            return
        
        console.print(f"[cyan]Uploading {local_path} to {vm_name}...[/cyan]")
        
        success = gcloud.scp_to_vm(
            local_path,
            vm_data["instance_name"],
            vm_data["zone"],
            remote_path
        )
        
        if success:
            console.print(f"[green]✓ Upload complete[/green]")
        else:
            console.print(f"[red]Upload failed[/red]")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
def sync():
    """Sync local VM list with actual GCP state"""
    try:
        console.print("[cyan]Syncing VM state with GCP...[/cyan]")
        
        vms = storage.list_vms()
        if not vms:
            console.print("[yellow]No VMs to sync[/yellow]")
            return
        
        table = Table(title="VM Sync Status")
        table.add_column("Name", style="cyan")
        table.add_column("Instance", style="green") 
        table.add_column("Status", style="yellow")
        table.add_column("Action", style="blue")
        
        for vm in vms:
            instance_info = gcloud.get_instance_details(vm["instance_name"], vm["zone"])
            
            if not instance_info:
                storage.remove_vm(vm["display_name"])
                ssh_manager.remove_vm_from_config(vm["display_name"])
                table.add_row(
                    vm["display_name"],
                    vm["instance_name"],
                    "NOT FOUND",
                    "Removed from local storage"
                )
            else:
                ssh_manager.add_vm_to_config(instance_info, custom_name=vm["display_name"])
                table.add_row(
                    vm["display_name"],
                    vm["instance_name"],
                    instance_info["status"],
                    "Updated" if instance_info.get("external_ip") else "No external IP"
                )
        
        console.print(table)
        console.print("[green]✓ Sync complete[/green]")
        
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("vm-name")
@click.argument("remote-path")
@click.argument("local-path", required=False)
def download(vm_name, remote_path, local_path):
    """Download files or directories from a VM"""
    try:
        vm_data = storage.get_vm(vm_name)
        if not vm_data:
            console.print(f"[red]VM '{vm_name}' not found[/red]")
            return
        
        console.print(f"[cyan]Downloading {remote_path} from {vm_name}...[/cyan]")
        
        success = gcloud.scp_from_vm(
            remote_path,
            vm_data["instance_name"],
            vm_data["zone"],
            local_path
        )
        
        if success:
            console.print(f"[green]✓ Download complete[/green]")
        else:
            console.print(f"[red]Download failed[/red]")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("vm-name")
def check(vm_name):
    """Check SSH connectivity to a VM"""
    try:
        vm_data = storage.get_vm(vm_name)
        if not vm_data:
            console.print(f"[red]VM '{vm_name}' not found[/red]")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Checking SSH connectivity to {vm_name}...", total=None)
            
            connected = gcloud.check_ssh_connectivity(
                vm_data["instance_name"],
                vm_data["zone"]
            )
        
        if connected:
            console.print(f"[green]✓ SSH connection to '{vm_name}' is healthy[/green]")
            
            instance_info = gcloud.get_instance_details(vm_data["instance_name"], vm_data["zone"])
            if instance_info and instance_info.get("external_ip"):
                console.print(f"[cyan]External IP: {instance_info['external_ip']}[/cyan]")
                console.print(f"[cyan]Status: {instance_info['status']}[/cyan]")
        else:
            console.print(f"[red]✗ Cannot connect to '{vm_name}' via SSH[/red]")
            console.print("[yellow]Possible causes:[/yellow]")
            console.print("  - VM is not running")
            console.print("  - SSH keys not configured")
            console.print("  - Firewall rules blocking SSH")
            console.print("  - VM is still booting")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("vm-name")
@click.argument("script-path")
@click.option("--session", default=None, help="Tmux session name (defaults to script name)")
def run(vm_name, script_path, session):
    """Execute a bash script on a VM in a tmux session"""
    
    try:
        vm_data = storage.get_vm(vm_name)
        if not vm_data:
            console.print(f"[red]VM '{vm_name}' not found[/red]")
            return
        
        if not os.path.exists(script_path):
            console.print(f"[red]Script file '{script_path}' not found[/red]")
            return
        
        script_name = os.path.basename(script_path)
        session_name = session or re.sub(r'[^a-zA-Z0-9_-]', '_', script_name)
        
        console.print(f"[cyan]Running {script_name} on {vm_name} in tmux session '{session_name}'...[/cyan]")
        
        success = gcloud.run_script(
            script_path,
            vm_data["instance_name"],
            vm_data["zone"],
            session_name
        )
        
        if success:
            console.print(f"[green]✓ Script started in tmux session '{session_name}'[/green]")
            console.print(f"[cyan]To attach: migs ssh {vm_name} -- tmux attach -t {session_name}[/cyan]")
            console.print(f"[cyan]To check status: migs ssh {vm_name} -- tmux ls[/cyan]")
        else:
            console.print(f"[red]Failed to run script[/red]")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    cli()