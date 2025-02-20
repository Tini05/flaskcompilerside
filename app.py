from flask import Flask
from flask_socketio import SocketIO, emit
import subprocess
import sys
import threading
import queue
import traceback

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

process = None
output_queue = queue.Queue()
input_event = threading.Event()

def read_output(proc):
    """Reads process output and emits it via WebSocket."""
    while True:
        output = proc.stdout.readline()
        if not output:
            break
        output = output.strip()
        print(f"📤 Streaming output: {output}")
        socketio.emit("output", {"output": output})
        output_queue.put(output)
    
    errors = proc.stderr.read().strip()
    if errors:
        print(f"❌ Error output: {errors}")
        socketio.emit("output", {"output": errors})
        output_queue.put(errors)

@socketio.on("run_code")
def run_code(data):
    global process
    code = data.get("code", "")
    print(f"📥 Received code:\n{code}")

    if process and process.poll() is None:
        print("⚠ Killing existing process")
        process.kill()
    
    while not output_queue.empty():
        output_queue.get()

    wrapped_code = (
        "import sys\n"
        "import traceback\n"
        "def patched_input(prompt=''):\n"
        "    sys.stdout.write(prompt)\n"
        "    sys.stdout.flush()\n"
        "    return sys.stdin.readline().strip()\n"
        "input = patched_input\n"
        "try:\n"
        + "\n".join(["    " + line for line in code.split("\n")]) +
        "\nexcept Exception as e:\n"
        "    print('❌ Traceback:', traceback.format_exc())"
    )

    process = subprocess.Popen(
        [sys.executable, "-u", "-c", wrapped_code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    threading.Thread(target=read_output, args=(process,), daemon=True).start()

@socketio.on("send_input")
def send_input(data):
    global process
    if not process or process.poll() is not None:
        print("🚫 No running process found for input.")
        emit("output", {"output": "No running process"})
        return
    
    user_input = data.get("input", "").strip()
    print(f"📥 Received user input: {user_input}")
    
    try:
        process.stdin.write(user_input + "\n")
        process.stdin.flush()
        input_event.set()
    except Exception as e:
        print(f"❌ Error sending input: {e}")
        emit("output", {"output": f"Error: {str(e)}"})

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
