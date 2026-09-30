import websocket
import json
import time
import threading
import signal
import sys
import subprocess
import tempfile
import base64
import os
import jwt


# === CONFIG ===
WS_URL = "wss://vugx1b0qef.execute-api.eu-central-1.amazonaws.com/dev/"
RESTAURANT_NUMBER = "1"
DEVICE_ID = "device-001"
MACHINE_NAME = "UK00054GSC02"

JWT_SECRET = os.environ.get("JWT_SECRET", "Snow4all@2025")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 300  # 5 minutes

# === GLOBAL FLAGS ===
running = True
ws_app = None


def send_heartbeat(ws):
    """Send heartbeat every 30 seconds while running."""
    while running:
        heartbeat_msg = {
            "action": "heartbeat",
            "restaurant_number": RESTAURANT_NUMBER,
            "device_id": DEVICE_ID,
            "timestamp": int(time.time()),
        }
        try:
            ws.send(json.dumps(heartbeat_msg))
            print(f"💓 Sent heartbeat at {time.strftime('%X')}")
        except Exception as e:
            print(f"⚠️ Heartbeat error: {e}")
            break
        time.sleep(120)


def run_received_script(script_name, script_path, ws, command_id=None):
    """Decode, execute, and send back results."""
    try:
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script not found: {script_path}")

        print(f"Executing script: {script_name} → {script_path}")

        process = subprocess.run(
            [sys.executable, script_path],  # Executes Python script
            capture_output=True,
            text=True,
            timeout=60
        )

        save_result_msg = {
            "action": "save_results",
            "restaurant_number": RESTAURANT_NUMBER,
            "device_id": DEVICE_ID,
            "command_id": command_id or "unknown",
            "script_name": script_name,
            "result_output": process.stdout.strip(),
            "stderr": process.stderr.strip(),
            "returncode": process.returncode,
            "timestamp": int(time.time()),
            "execution_status": "success" if process.returncode == 0 else "failed"
        }
        ws.send(json.dumps(save_result_msg))
        print("💾 Sent results for saving to DynamoDB")

    except subprocess.TimeoutExpired:
        print(f"⏱️ Script {script_name} timed out.")
        ws.send(json.dumps({
            "action": "save_results",
            "command_id": command_id or "unknown",
            "device_id": DEVICE_ID,
            "machine": MACHINE_NAME,
            "script_name": script_name,
            "stderr": "Timeout expired",
            "timestamp": int(time.time())
        }))
    except Exception as e:
        print(f"❌ Error running received script: {e}")
        ws.send(json.dumps({
            "action": "save_results",
            "command_id": command_id or "unknown",
            "device_id": DEVICE_ID,
            "machine": MACHINE_NAME,
            "script_name": script_name,
            "stderr": str(e),
            "timestamp": int(time.time())
        }))
    


def on_message(ws, message):
    """Handle incoming messages from WebSocket."""
    print(f"📩 From server: {message}")
    try:
        data = json.loads(message)
        action = data.get("action")

        if action == "trigger_script":
            script_name = data.get("script_name", "health_check")
            script_path = data.get("script_path")
            command_id = data.get("command_id")

            threading.Thread(
                target=run_received_script,
                args=(script_name, script_path, ws, command_id),
                daemon=True
            ).start()
        else:
            # print all other types (register/pong etc)
            print(f"ℹ️ Received message type: {action}")
    except Exception as e:
        print(f"⚠️ Failed to parse message: {e}")


def on_error(ws, error):
    if running:
        print(f"❌ Error: {error}")


def on_close(ws, close_status_code, close_msg):
    print("🔌 Connection closed gracefully.")


def on_open(ws):
    """Register device when connection opens."""
    print("✅ Connected to WebSocket")

    register_msg = {
        "action": "register",
        "restaurant_number": RESTAURANT_NUMBER,
        "device_id": DEVICE_ID,
        "machine": MACHINE_NAME,
    }
    ws.send(json.dumps(register_msg))
    print(f"📤 Sent registration for {MACHINE_NAME}")

    # Start heartbeat thread
    threading.Thread(target=send_heartbeat, args=(ws,), daemon=True).start()


def signal_handler(sig, frame):
    """Handle Ctrl+C / termination."""
    global running, ws_app
    print("\n⚙️ Shutting down gracefully...")

    running = False
    try:
        disconnect_msg = {
            "action": "disconnect",
            "restaurant_number": RESTAURANT_NUMBER,
            "device_id": DEVICE_ID,
        }
        ws_app.send(json.dumps(disconnect_msg))
        print("📤 Sent disconnect message to server")

        ws_app.close()
    except Exception as e:
        print(f"⚠️ Error during close: {e}")
    finally:
        sys.exit(0)

def generate_jwt(machine_name):
    """
    Generate a short-lived JWT for WebSocket authentication
    """
    payload = {
        "machine_name": machine_name,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_TTL_SECONDS,
    }

    JWT_SECRET = "Snow4all@2025"

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


if __name__ == "__main__":
    websocket.enableTrace(False)

    # Attach Ctrl+C handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    MACHINE_NAME = "UK00054GSC02"

    # Generate JWT
    JWT_TOKEN = generate_jwt(MACHINE_NAME)

    url = f"{WS_URL}?restaurantnumber={RESTAURANT_NUMBER}&deviceid={DEVICE_ID}&machine={MACHINE_NAME}"

    headers = [f"Authorization: Bearer {JWT_TOKEN}"]

    ws_app = websocket.WebSocketApp(
        url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    print("🚀 Connecting to WebSocket with generated JWT...")
    ws_app.run_forever(ping_interval=60, ping_timeout=10)