import click
from rich.console import Console
from rich.table import Table

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


@cli.command()
def list():
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
def up(mig_name, name, zone):
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
        console.print("[yellow]Waiting for VM to be created...[/yellow]")
        
        vm_info = gcloud.wait_for_vm(mig_name, zone, request_id)
        
        if vm_info:
            storage.save_vm(vm_info["name"], mig_name, zone, custom_name=name)
            ssh_manager.add_vm_to_config(vm_info, custom_name=name)
            
            display_name = name or vm_info["name"]
            console.print(f"[green]✓ VM '{display_name}' is ready![/green]")
            console.print(f"[cyan]SSH: migs ssh {display_name}[/cyan]")
        else:
            console.print("[red]Failed to create VM[/red]")
            
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


@cli.command()
@click.argument("vm-name")
def ssh(vm_name):
    """SSH into a VM"""
    try:
        vm_data = storage.get_vm(vm_name)
        if not vm_data:
            console.print(f"[red]VM '{vm_name}' not found[/red]")
            return
        
        gcloud.ssh_to_vm(vm_data["instance_name"], vm_data["zone"])
        
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


if __name__ == "__main__":
    cli()