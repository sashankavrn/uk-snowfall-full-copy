import platform
import socket
from datetime import datetime
import json

data = {
    "machine_name": platform.node() or socket.gethostname(),
    "timezone": str(datetime.now().astimezone().tzinfo)
}

print(json.dumps(data))