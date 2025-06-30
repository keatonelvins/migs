import os
from pathlib import Path
from typing import Dict, Optional


class SSHConfigManager:
    """Manage SSH config entries for VS Code Remote Explorer"""
    
    def __init__(self):
        self.ssh_config_path = Path.home() / ".ssh" / "config"
        self.marker_start = "# BEGIN MIGS MANAGED HOSTS"
        self.marker_end = "# END MIGS MANAGED HOSTS"
        self._ensure_ssh_dir()
    
    def _ensure_ssh_dir(self):
        """Ensure .ssh directory exists with proper permissions"""
        ssh_dir = self.ssh_config_path.parent
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        
        if not self.ssh_config_path.exists():
            self.ssh_config_path.touch(mode=0o600)
    
    def _read_config(self) -> str:
        """Read the current SSH config"""
        try:
            return self.ssh_config_path.read_text()
        except:
            return ""
    
    def _write_config(self, content: str):
        """Write the SSH config"""
        self.ssh_config_path.write_text(content)
        os.chmod(self.ssh_config_path, 0o600)
    
    def _get_managed_section(self, config: str) -> tuple[int, int]:
        """Find the managed section in the config"""
        lines = config.split("\n")
        start_idx = -1
        end_idx = -1
        
        for i, line in enumerate(lines):
            if line.strip() == self.marker_start:
                start_idx = i
            elif line.strip() == self.marker_end:
                end_idx = i
                break
        
        return start_idx, end_idx
    
    def add_vm_to_config(self, vm_info: Dict, custom_name: Optional[str] = None):
        """Add a VM entry to SSH config"""
        if not vm_info.get("external_ip") or not vm_info.get("username"):
            return
        
        host_name = custom_name or vm_info["name"]
        
        entry = f"""
Host {host_name}
    User {vm_info["username"]}
    HostName {vm_info["external_ip"]}
    IdentityFile ~/.ssh/google_compute_engine
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
"""
        
        config = self._read_config()
        start_idx, end_idx = self._get_managed_section(config)
        
        if start_idx == -1:
            if config and not config.endswith("\n"):
                config += "\n"
            config += f"\n{self.marker_start}\n{entry}\n{self.marker_end}\n"
        else:
            lines = config.split("\n")
            managed_entries = lines[start_idx+1:end_idx]
            
            new_entries = []
            host_found = False
            
            i = 0
            while i < len(managed_entries):
                line = managed_entries[i]
                if line.strip().startswith("Host ") and host_name in line:
                    host_found = True
                    while i < len(managed_entries) and not managed_entries[i].strip().startswith("Host "):
                        i += 1
                    continue
                new_entries.append(line)
                i += 1
            
            new_entries.append(entry.strip())
            
            new_lines = lines[:start_idx+1] + new_entries + lines[end_idx:]
            config = "\n".join(new_lines)
        
        self._write_config(config)
    
    def remove_vm_from_config(self, vm_name: str):
        """Remove a VM entry from SSH config"""
        config = self._read_config()
        start_idx, end_idx = self._get_managed_section(config)
        
        if start_idx == -1:
            return
        
        lines = config.split("\n")
        managed_entries = lines[start_idx+1:end_idx]
        
        new_entries = []
        skip = False
        
        for line in managed_entries:
            if line.strip().startswith("Host ") and vm_name in line:
                skip = True
            elif line.strip().startswith("Host "):
                skip = False
            
            if not skip:
                new_entries.append(line)
        
        new_lines = lines[:start_idx+1] + new_entries + lines[end_idx:]
        config = "\n".join(new_lines)
        
        self._write_config(config)