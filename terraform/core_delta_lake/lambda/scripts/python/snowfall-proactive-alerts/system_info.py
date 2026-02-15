import platform
import socket
import shutil
import os
from datetime import datetime, timezone
import json

def get_disk_usage(path="/"):
    try:
        usage = shutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round((usage.used / usage.total) * 100, 2)
        }
    except Exception as e:
        return {"error": str(e)}

def get_memory_info():
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()

        meminfo = {}
        for line in lines:
            key, value = line.split(":")
            meminfo[key.strip()] = value.strip()

        total = int(meminfo["MemTotal"].split()[0]) / 1024 / 1024
        free = int(meminfo["MemAvailable"].split()[0]) / 1024 / 1024

        return {
            "total_gb": round(total, 2),
            "available_gb": round(free, 2),
            "used_gb": round(total - free, 2),
            "percent_used": round(((total - free) / total) * 100, 2)
        }
    except:
        return {"error": "Memory info not available"}

def get_ip_addresses():
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return {
            "hostname": hostname,
            "local_ip": local_ip
        }
    except:
        return {"error": "Unable to fetch IP info"}

data = {
    "machine_name": platform.node() or socket.gethostname(),
    "timezone": str(datetime.now().astimezone().tzinfo),
    "os": {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version()
    },
    "disk_usage": get_disk_usage("/"),
    "memory": get_memory_info(),
    "network": get_ip_addresses(),

    # Modern, timezone-aware UTC timestamp (no deprecation warning)
    "timestamp": datetime.now(timezone.utc).isoformat()
}

print(json.dumps(data, indent=2))
