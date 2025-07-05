import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class VMStorage:
    """Store and manage personal VM information"""
    
    def __init__(self):
        self.storage_dir = Path.home() / ".migs"
        self.storage_file = self.storage_dir / "vms.json"
        self._ensure_storage()
    
    def _ensure_storage(self):
        """Ensure storage directory and file exist"""
        self.storage_dir.mkdir(exist_ok=True)
        if not self.storage_file.exists():
            self.storage_file.write_text("{}")
    
    def _load_data(self) -> Dict:
        """Load VM data from storage"""
        try:
            return json.loads(self.storage_file.read_text())
        except (json.JSONDecodeError, FileNotFoundError, PermissionError):
            return {}
    
    def _save_data(self, data: Dict):
        """Save VM data to storage"""
        self.storage_file.write_text(json.dumps(data, indent=2))
    
    def save_vm(self, instance_name: str, mig_name: str, zone: str, custom_name: Optional[str] = None, group_id: Optional[str] = None):
        """Save a VM to personal storage"""
        data = self._load_data()
        
        display_name = custom_name or instance_name
        
        data[display_name] = {
            "instance_name": instance_name,
            "mig_name": mig_name,
            "zone": zone,
            "display_name": display_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "group_id": group_id
        }
        
        self._save_data(data)
    
    def get_vm(self, name: str) -> Optional[Dict]:
        """Get VM info by display name or instance name"""
        data = self._load_data()
        
        if name in data:
            return data[name]
        
        for vm_data in data.values():
            if vm_data["instance_name"] == name:
                return vm_data
        
        return None
    
    def remove_vm(self, name: str):
        """Remove a VM from storage"""
        data = self._load_data()
        
        if name in data:
            del data[name]
        else:
            for key, vm_data in list(data.items()):
                if vm_data["instance_name"] == name:
                    del data[key]
                    break
        
        self._save_data(data)
    
    def list_vms(self) -> List[Dict]:
        """List all personal VMs"""
        data = self._load_data()
        return list(data.values())
    
    def get_vms_in_group(self, group_id: str) -> List[Dict]:
        """Get all VMs in a specific group"""
        data = self._load_data()
        return [vm for vm in data.values() if vm.get("group_id") == group_id]
    
    def get_vm_group_id(self, vm_name: str) -> Optional[str]:
        """Get the group ID for a VM if it's part of a group"""
        vm_data = self.get_vm(vm_name)
        return vm_data.get("group_id") if vm_data else None
    
    def get_cluster_vms(self, cluster_name: str) -> List[Dict]:
        """Get all VMs that match a cluster name pattern.
        
        For multi-node clusters created with --name cluster -c 4, this will
        find cluster1, cluster2, cluster3, cluster4 when given 'cluster'.
        """
        data = self._load_data()
        
        # First check if there's an exact match with a group_id
        exact_match = self.get_vm(cluster_name)
        if exact_match and exact_match.get("group_id"):
            # This is a VM in a group, return all VMs in that group
            return self.get_vms_in_group(exact_match["group_id"])
        
        # Otherwise, look for VMs that match the cluster pattern
        # (e.g., "cluster" matches "cluster1", "cluster2", etc.)
        for vm_name, vm_data in data.items():
            # Check if VM name matches cluster pattern (clusterN)
            if vm_name.startswith(cluster_name) and vm_data.get("group_id"):
                # Get all VMs in this group
                group_vms = self.get_vms_in_group(vm_data["group_id"])
                if group_vms:
                    return group_vms
        
        return []