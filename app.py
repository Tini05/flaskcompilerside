from flask import Flask, request, jsonify, Response
import subprocess
import sys
import time
import threading
import queue
import traceback
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://simplepythoncompiler.vercel.app"])

process = None
output_queue = queue.Queue()
input_event = threading.Event()

def read_output(proc):
    """Reads process output and adds it to the queue."""
    while True:
        output = proc.stdout.readline()
        if not output:
            break
        output = output.strip()
        print(f"📤 Streaming output1: {output}")  # Debugging
        output_queue.put(output)
    
    # Read and enqueue errors
    errors = proc.stderr.read().strip()
    if errors:
        print(f"❌ Error output: {errors}")
        output_queue.put(errors)

@app.route("/run", methods=["POST"])
def run_code():
    global process

    data = request.json
    code = data.get("code", "")
    print(f"📥 Received code:\n{code}")

    if process and process.poll() is None:
        print("⚠ Killing existing process")
        process.kill()

    # Clear any leftover output in the queue
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

    def generate():
        while True:
            if not output_queue.empty():
                output = output_queue.get()
                print(f"📤 Streaming output2: {output}")
                yield f"{output}\n"

                # If a prompt is detected, stop and wait for user input
                if output.strip().endswith("?") or output.strip().endswith(":"):
                    input_event.clear()
                    input_event.wait()

            elif process.poll() is not None:
                break
            time.sleep(0.1)

    return Response(generate(), mimetype="text/plain")

@app.route("/send_input", methods=["OPTIONS", "POST"])
def send_input():
    """Handles user input and resumes execution."""
    global process

    if not process or process.poll() is not None:
        print("🚫 No running process found for input.")
        return jsonify({"output": "No running process"}), 200

    data = request.json
    user_input = data.get("input", "").strip()
    print(f"📥 Received user input: {user_input}")

    try:
        process.stdin.write(user_input + "\n")
        process.stdin.flush()

        # Allow process to continue
        input_event.set()
        time.sleep(0.1)

        # Collect next output
        collected_output = []
        while not output_queue.empty():
            collected_output.append(output_queue.get())

        final_output = "\n".join(collected_output)
        print(f"📤 Sending back output: {final_output}")
        return jsonify({"output": final_output})
    except Exception as e:
        print(f"❌ Error sending input: {e}")
        return jsonify({"output": f"Error: {str(e)}"}), 500

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

if __name__ == "__main__":
    app.run(debug=True)
