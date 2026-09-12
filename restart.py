"""Helper to restart the dev server."""
import subprocess, time, os, sys, signal

# Kill existing uvicorn on port 8077
try:
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True, text=True, timeout=5,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    for line in result.stdout.splitlines():
        if "8077" in line and "LISTENING" in line:
            pid = line.strip().split()[-1]
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            print(f"Killed PID {pid}")
            break
except Exception as e:
    print(f"Kill failed: {e}")

time.sleep(2)

# Remove old db
db_path = os.path.join(os.path.dirname(__file__), "college_diary.db")
if os.path.exists(db_path):
    os.remove(db_path)
    print("Removed old DB")

# Start uvicorn
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8077"],
    cwd=os.path.dirname(__file__) or ".",
    stdout=open(os.path.join(os.path.dirname(__file__), "server_out.log"), "w"),
    stderr=open(os.path.join(os.path.dirname(__file__), "server_err.log"), "w"),
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
)
print(f"Started server PID={proc.pid}")
time.sleep(5)
print("Ready")
