import os
import re
import time
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
@click.option("--name", "-n", help="Custom name for your VM(s). With count>1, creates name1, name2, etc.")
@click.option("--count", "-c", default=1, type=int, help="Number of VMs to create (default: 1)")
@click.option("--zone", "-z", help="Zone (will auto-detect if not specified)")
@click.option("--duration", "-d", help="Time before auto-deletion (e.g., 30m, 2h, 1d)")
@click.option("--stable", is_flag=True, help="Use stable API (no exact instance naming)")
def up(mig_name, name, count, zone, duration, stable):
    """Spin up one or more VMs in the specified MIG
    
    By default, auto-detects if gcloud beta is available and uses it for exact
    instance names. Without --name, generates names as: mig-username-timestamp
    With --name and --count>1, creates: name1, name2, name3, etc.
    
    Use --stable to force stable API with local name mapping.
    """
    try:
        if not zone:
            zone = gcloud.get_mig_zone(mig_name)
            if not zone:
                console.print(f"[red]Could not find zone for MIG: {mig_name}[/red]")
                return
        
        # Get initial instances before creating resize request (for multi-node detection)
        initial_instances = gcloud.list_instances(mig_name, zone)
        initial_instance_names = {inst["name"] for inst in initial_instances}
        
        # Determine if we should use stable API
        use_stable = stable
        
        # Generate instance names
        instance_names = None
        if name:
            # User provided a name
            if count > 1:
                instance_names = [f"{name}{i}" for i in range(1, count + 1)]
            else:
                instance_names = [name]
        else:
            # Generate default names: <mig_name>_<username>_<id>
            import os
            username = os.getenv("USER", "user")
            timestamp = int(time.time())
            if count > 1:
                instance_names = [f"{mig_name}-{username}-{timestamp}-{i}" for i in range(1, count + 1)]
            else:
                instance_names = [f"{mig_name}-{username}-{timestamp}"]
        
        console.print(f"[cyan]Creating resize request for MIG: {mig_name} (count: {count})[/cyan]")
        if duration:
            console.print(f"[yellow]VMs will auto-delete after: {duration}[/yellow]")
        
        request_id, used_beta = gcloud.create_resize_request(
            mig_name, zone, count, 
            run_duration=duration, 
            instance_names=instance_names, 
            force_mode="stable" if use_stable else None
        )
        
        if instance_names and used_beta:
            console.print(f"[cyan]Using gcloud beta - Instance names: {', '.join(instance_names)}[/cyan]")
        elif instance_names and not used_beta:
            if not use_stable:
                console.print(f"[yellow]Note: gcloud beta not available, try installing or avoid this messages with --stable[/yellow]")
            console.print(f"[cyan]Using stable API - VMs will be mapped to: {', '.join(instance_names)}[/cyan]")
        
        console.print(f"[green]Resize request created: {request_id}[/green]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[yellow]Waiting for {count} VM(s) creation...", total=None)
            
            vm_info = gcloud.wait_for_vm(mig_name, zone, request_id, expected_count=count, 
                                          progress_callback=lambda: progress.advance(task),
                                          initial_instance_names=initial_instance_names,
                                          target_instance_names=instance_names)
        
        if vm_info:
            # Handle single VM or multiple VMs
            if isinstance(vm_info, list):
                # Multiple VMs created
                group_id = f"{mig_name}-{request_id}" if count > 1 else None
                
                for idx, vm in enumerate(vm_info, 1):
                    # When using beta API with instance names, the VM already has the correct name
                    # When using stable API, we need to map custom names
                    if instance_names and used_beta:
                        # VM name is already what we specified
                        vm_name = vm["name"]
                    elif name and count > 1:
                        # Stable API: map to user's custom name with suffix
                        vm_name = f"{name}{idx}"
                    else:
                        vm_name = name or vm["name"]
                    
                    storage.save_vm(vm["name"], mig_name, zone, custom_name=vm_name, group_id=group_id)
                    ssh_manager.add_vm_to_config(vm, custom_name=vm_name)
                
                console.print(f"[green]✓ {len(vm_info)} VMs are ready![/green]")
                if instance_names and used_beta:
                    console.print(f"[cyan]VMs created: {', '.join([vm['name'] for vm in vm_info])}[/cyan]")
                    for vm in vm_info:
                        console.print(f"[cyan]SSH: migs ssh {vm['name']}[/cyan]")
                elif name:
                    console.print(f"[cyan]VMs: {name}1 - {name}{len(vm_info)}[/cyan]")
                    console.print(f"[cyan]SSH: migs ssh {name}1 (or {name}2, {name}3, etc.)[/cyan]")
                else:
                    for vm in vm_info:
                        console.print(f"[cyan]SSH: migs ssh {vm['name']}[/cyan]")
            else:
                # Single VM created (backward compatibility)
                if instance_names and used_beta:
                    vm_name = vm_info["name"]
                else:
                    vm_name = name or vm_info["name"]
                    
                storage.save_vm(vm_info["name"], mig_name, zone, custom_name=vm_name)
                ssh_manager.add_vm_to_config(vm_info, custom_name=vm_name)
                
                console.print(f"[green]✓ VM '{vm_name}' is ready![/green]")
                console.print(f"[cyan]SSH: migs ssh {vm_name}[/cyan]")
        else:
            console.print("[red]Failed to create VM(s)[/red]")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("vm-name")
@click.option("--all", is_flag=True, help="Shut down all VMs in the group (for multi-node setups)")
def down(vm_name, all):
    """Spin down a VM or all VMs in a group"""
    try:
        # First try to find cluster VMs if --all is specified
        if all:
            cluster_vms = storage.get_cluster_vms(vm_name)
            if cluster_vms:
                vms_to_delete = cluster_vms
                console.print(f"[yellow]Shutting down all {len(cluster_vms)} VMs in cluster '{vm_name}'[/yellow]")
            else:
                # Fall back to single VM lookup
                vm_data = storage.get_vm(vm_name)
                if not vm_data:
                    console.print(f"[red]VM or cluster '{vm_name}' not found[/red]")
                    return
                
                if vm_data.get("group_id"):
                    # Get all VMs in the group
                    group_vms = storage.get_vms_in_group(vm_data["group_id"])
                    if group_vms:
                        vms_to_delete = group_vms
                        console.print(f"[yellow]Shutting down all {len(group_vms)} VMs in the group[/yellow]")
                    else:
                        vms_to_delete = [vm_data]
                else:
                    vms_to_delete = [vm_data]
                    console.print(f"[yellow]Shutting down VM: {vm_name}[/yellow]")
        else:
            # Single VM shutdown
            vm_data = storage.get_vm(vm_name)
            if not vm_data:
                console.print(f"[red]VM '{vm_name}' not found[/red]")
                return
            vms_to_delete = [vm_data]
            console.print(f"[yellow]Shutting down VM: {vm_name}[/yellow]")
        
        # Delete each VM
        success_count = 0
        for vm in vms_to_delete:
            success = gcloud.delete_vm(
                vm["instance_name"],
                vm["zone"],
                vm["mig_name"]
            )
            
            if success:
                success_count += 1
                storage.remove_vm(vm["display_name"])
                ssh_manager.remove_vm_from_config(vm["display_name"])
                console.print(f"[green]✓ VM '{vm['display_name']}' has been shut down[/green]")
            else:
                console.print(f"[red]Failed to shut down VM '{vm['display_name']}'[/red]")
        
        if len(vms_to_delete) > 1:
            console.print(f"[cyan]Successfully shut down {success_count}/{len(vms_to_delete)} VMs[/cyan]")
            
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
    
    # Group VMs by group_id
    grouped_vms = {}
    standalone_vms = []
    
    for vm in vms:
        group_id = vm.get("group_id")
        if group_id:
            if group_id not in grouped_vms:
                grouped_vms[group_id] = []
            grouped_vms[group_id].append(vm)
        else:
            standalone_vms.append(vm)
    
    table = Table(title="Your VMs")
    table.add_column("Name", style="cyan")
    table.add_column("Instance", style="green")
    table.add_column("MIG", style="yellow")
    table.add_column("Zone", style="yellow")
    table.add_column("Group", style="magenta")
    table.add_column("Created", style="blue")
    
    # Add grouped VMs first
    for group_id, group_vms in grouped_vms.items():
        # Sort VMs in group by name
        group_vms.sort(key=lambda x: x["display_name"])
        for idx, vm in enumerate(group_vms):
            group_label = f"Group ({len(group_vms)} nodes)" if idx == 0 else "↑"
            table.add_row(
                vm["display_name"],
                vm["instance_name"],
                vm["mig_name"],
                vm["zone"],
                group_label,
                vm["created_at"]
            )
    
    # Add standalone VMs
    for vm in standalone_vms:
        table.add_row(
            vm["display_name"],
            vm["instance_name"],
            vm["mig_name"],
            vm["zone"],
            "-",
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
        
        # Check for .env file in current directory
        env_file = None
        if os.path.exists(".env"):
            env_file = ".env"
            console.print(f"[cyan]Found .env file, will upload and source it[/cyan]")
        
        gcloud.ssh_to_vm(vm_data["instance_name"], vm_data["zone"], list(ssh_args) or None, env_file)
        
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
@click.option("--all", is_flag=True, help="Upload to all VMs in the group (for multi-node setups)")
def upload(vm_name, local_path, remote_path, all):
    """Upload files or directories to a VM or all VMs in a cluster"""
    try:
        if not os.path.exists(local_path):
            console.print(f"[red]Local path '{local_path}' not found[/red]")
            return
        
        # Determine which VMs to upload to
        vms_to_upload = []
        if all:
            # First try to find cluster VMs
            cluster_vms = storage.get_cluster_vms(vm_name)
            if cluster_vms:
                vms_to_upload = cluster_vms
                console.print(f"[cyan]Uploading to all {len(cluster_vms)} VMs in cluster '{vm_name}'[/cyan]")
            else:
                # Fall back to single VM lookup
                vm_data = storage.get_vm(vm_name)
                if not vm_data:
                    console.print(f"[red]VM or cluster '{vm_name}' not found[/red]")
                    return
                
                if vm_data.get("group_id"):
                    # Get all VMs in the group
                    group_vms = storage.get_vms_in_group(vm_data["group_id"])
                    if group_vms:
                        vms_to_upload = group_vms
                        console.print(f"[cyan]Uploading to all {len(group_vms)} VMs in the group[/cyan]")
                    else:
                        vms_to_upload = [vm_data]
                else:
                    vms_to_upload = [vm_data]
        else:
            # Single VM upload
            vm_data = storage.get_vm(vm_name)
            if not vm_data:
                console.print(f"[red]VM '{vm_name}' not found[/red]")
                return
            vms_to_upload = [vm_data]
        
        # Upload to each VM
        success_count = 0
        for vm in vms_to_upload:
            console.print(f"[cyan]Uploading {local_path} to {vm['display_name']}...[/cyan]")
            
            success = gcloud.scp_to_vm(
                local_path,
                vm["instance_name"],
                vm["zone"],
                remote_path
            )
            
            if success:
                success_count += 1
                console.print(f"[green]✓ Upload complete to {vm['display_name']}[/green]")
            else:
                console.print(f"[red]Upload failed to {vm['display_name']}[/red]")
        
        if len(vms_to_upload) > 1:
            console.print(f"[cyan]Successfully uploaded to {success_count}/{len(vms_to_upload)} VMs[/cyan]")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.option("--discover", "-d", is_flag=True, help="Discover and claim untracked VMs")
def sync(discover):
    """Sync local VM list with actual GCP state"""
    try:
        console.print("[cyan]Syncing VM state with GCP...[/cyan]")
        
        # First, sync existing tracked VMs
        vms = storage.list_vms()
        tracked_instances = {vm["instance_name"] for vm in vms}
        
        if vms:
            table = Table(title="Tracked VMs Sync Status")
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
        else:
            console.print("[yellow]No tracked VMs found[/yellow]")
        
        # Discover untracked VMs if requested
        if discover:
            console.print("\n[cyan]Discovering untracked VMs...[/cyan]")
            migs = gcloud.list_migs()
            untracked_vms = []
            
            for mig in migs:
                if mig["size"] > 0:
                    instances = gcloud.list_instances(mig["name"], mig["zone"])
                    for instance in instances:
                        instance_name = instance.get("name", instance.get("instance", "").split("/")[-1])
                        if instance_name and instance_name not in tracked_instances:
                            instance_details = gcloud.get_instance_details(instance_name, mig["zone"])
                            if instance_details:
                                untracked_vms.append({
                                    "instance_name": instance_name,
                                    "mig_name": mig["name"],
                                    "zone": mig["zone"],
                                    "status": instance_details["status"],
                                    "external_ip": instance_details.get("external_ip", "N/A")
                                })
            
            if untracked_vms:
                table = Table(title="Untracked VMs Found")
                table.add_column("#", style="dim")
                table.add_column("Instance", style="green")
                table.add_column("MIG", style="yellow")
                table.add_column("Zone", style="yellow")
                table.add_column("Status", style="cyan")
                table.add_column("External IP", style="blue")
                
                for idx, vm in enumerate(untracked_vms):
                    table.add_row(
                        str(idx + 1),
                        vm["instance_name"],
                        vm["mig_name"],
                        vm["zone"],
                        vm["status"],
                        vm["external_ip"]
                    )
                
                console.print(table)
                
                # Ask if user wants to claim any VMs
                if click.confirm("\nWould you like to claim any of these VMs?"):
                    vm_numbers = click.prompt("Enter VM numbers to claim (comma-separated, e.g., 1,3)", type=str)
                    
                    for num_str in vm_numbers.split(","):
                        try:
                            idx = int(num_str.strip()) - 1
                            if 0 <= idx < len(untracked_vms):
                                vm = untracked_vms[idx]
                                custom_name = click.prompt(f"Custom name for {vm['instance_name']} (press Enter to skip)", default="", show_default=False)
                                custom_name = custom_name.strip() or None
                                
                                # Get full instance details for SSH config
                                instance_info = gcloud.get_instance_details(vm["instance_name"], vm["zone"])
                                if instance_info:
                                    storage.save_vm(vm["instance_name"], vm["mig_name"], vm["zone"], custom_name=custom_name)
                                    ssh_manager.add_vm_to_config(instance_info, custom_name=custom_name)
                                    display_name = custom_name or vm["instance_name"]
                                    console.print(f"[green]✓ Claimed VM: {display_name}[/green]")
                            else:
                                console.print(f"[red]Invalid VM number: {num_str}[/red]")
                        except ValueError:
                            console.print(f"[red]Invalid input: {num_str}[/red]")
            else:
                console.print("[green]No untracked VMs found[/green]")
        
        console.print("\n[green]✓ Sync complete[/green]")
        
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
@click.argument("script-args", nargs=-1, required=False)
@click.option("--session", default=None, help="Tmux session name (defaults to script name)")
@click.option("--all", is_flag=True, help="Run on all VMs in the group (for multi-node setups)")
@click.option("--torchrun", is_flag=True, help="Set up torchrun environment variables for distributed training")
def run(vm_name, script_path, script_args, session, all, torchrun):
    """Execute a bash script on a VM in a tmux session

    Can pass args, e.g. `migs run my-vm script.sh arg1 arg2 arg3`
    
    For multi-node setups, use --all to run on all nodes in the group.
    Use --torchrun with --all to automatically set up distributed training environment.
    """
    
    try:
        if not os.path.exists(script_path):
            console.print(f"[red]Script file '{script_path}' not found[/red]")
            return
        
        script_name = os.path.basename(script_path)
        
        # Check for .env file in current directory
        env_file = None
        if os.path.exists(".env"):
            env_file = ".env"
            console.print(f"[cyan]Found .env file, will upload and source it[/cyan]")
        
        # Determine which VMs to run on
        vms_to_run = []
        if all:
            # First try to find cluster VMs
            cluster_vms = storage.get_cluster_vms(vm_name)
            if cluster_vms:
                vms_to_run = cluster_vms
                console.print(f"[cyan]Running on all {len(cluster_vms)} VMs in cluster '{vm_name}'[/cyan]")
            else:
                # Fall back to single VM lookup
                vm_data = storage.get_vm(vm_name)
                if not vm_data:
                    console.print(f"[red]VM or cluster '{vm_name}' not found[/red]")
                    return
                
                if vm_data.get("group_id"):
                    # Get all VMs in the group
                    group_vms = storage.get_vms_in_group(vm_data["group_id"])
                    if group_vms:
                        vms_to_run = group_vms
                        console.print(f"[cyan]Running on all {len(group_vms)} VMs in the group[/cyan]")
                    else:
                        vms_to_run = [vm_data]
                else:
                    vms_to_run = [vm_data]
        else:
            # Single VM run
            vm_data = storage.get_vm(vm_name)
            if not vm_data:
                console.print(f"[red]VM '{vm_name}' not found[/red]")
                return
            vms_to_run = [vm_data]
        
        # Sort VMs by display name to ensure consistent ordering (important for torchrun)
        vms_to_run.sort(key=lambda x: x["display_name"])
        
        # Get torchrun environment variables if needed
        torchrun_env = None
        if torchrun and all and len(vms_to_run) > 1:
            console.print(f"[cyan]Setting up torchrun environment for {len(vms_to_run)} nodes...[/cyan]")
            
            # Get head node (first VM) internal details
            head_vm = vms_to_run[0]
            head_details = gcloud.get_instance_internal_details(head_vm["instance_name"], head_vm["zone"])
            
            if not head_details:
                console.print(f"[red]Failed to get internal details for head node '{head_vm['display_name']}'[/red]")
                return
            
            head_node_ip = head_details["internal_ip"]
            nproc_per_node = head_details["gpu_count"]
            nnodes = len(vms_to_run)
            
            console.print(f"[cyan]Head node: {head_vm['display_name']} (IP: {head_node_ip})[/cyan]")
            console.print(f"[cyan]GPUs per node: {nproc_per_node}[/cyan]")
            console.print(f"[cyan]Total nodes: {nnodes}[/cyan]")
            
            # Prepare environment for each node
            torchrun_env = {
                "HEAD_NODE_IP": head_node_ip,
                "HEAD_NODE_PORT": "5000",
                "NNODES": str(nnodes),
                "NPROC_PER_NODE": str(nproc_per_node)
            }
        elif torchrun and not all:
            console.print(f"[yellow]Warning: --torchrun is only effective when used with --all for multi-node setups[/yellow]")
        
        # Run script on each VM
        success_count = 0
        for idx, vm in enumerate(vms_to_run):
            # Use the same session name for all VMs (they're on different machines)
            vm_session = session or re.sub(r'[^a-zA-Z0-9_-]', '_', script_name)
            
            # Prepare node-specific environment variables for torchrun
            node_env = None
            if torchrun_env:
                node_env = torchrun_env.copy()
                node_env["NODE_RANK"] = str(idx)  # 0 for head, 1+ for workers
            
            console.print(f"[cyan]Running {script_name} on {vm['display_name']} in tmux session '{vm_session}'...[/cyan]")
            
            success = gcloud.run_script(
                script_path,
                vm["instance_name"],
                vm["zone"],
                vm_session,
                list(script_args),
                env_file,
                node_env
            )
            
            if success:
                success_count += 1
                console.print(f"[green]✓ Script started on {vm['display_name']} in tmux session '{vm_session}'[/green]")
            else:
                console.print(f"[red]Failed to run script on {vm['display_name']}[/red]")
        
        if success_count > 0:
            if len(vms_to_run) == 1:
                console.print(f"[cyan]To attach: migs ssh {vm_name} -- tmux attach -t {vm_session}[/cyan]")
                console.print(f"[cyan]To check status: migs ssh {vm_name} -- tmux ls[/cyan]")
            else:
                console.print(f"[cyan]Scripts started on {success_count}/{len(vms_to_run)} VMs[/cyan]")
                console.print(f"[cyan]To attach to a specific VM: migs ssh <vm-name> -- tmux attach -t {vm_session}[/cyan]")
            
    except AuthenticationError as e:
        console.print(f"[red]Authentication required[/red]")
        console.print(f"[yellow]Please run: gcloud auth login[/yellow]")
        console.print(f"[yellow]Then try again[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    cli()