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
    
    def save_vm(self, instance_name: str, mig_name: str, zone: str, custom_name: Optional[str] = None):
        """Save a VM to personal storage"""
        data = self._load_data()
        
        display_name = custom_name or instance_name
        
        data[display_name] = {
            "instance_name": instance_name,
            "mig_name": mig_name,
            "zone": zone,
            "display_name": display_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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