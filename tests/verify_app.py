import subprocess
import time
import os

exe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist", "QuantileCull_V17.exe")
print("Launching app.exe to verify startup...")
p = subprocess.Popen([exe_path])

# Wait to see if it remains running
time.sleep(5)

ret = p.poll()
if ret is None:
    print("Verification SUCCESS: app.exe launched and remained running successfully!")
    p.terminate()
    p.wait()
else:
    print(f"Verification FAILURE: app.exe exited early with code {ret}")
    exit(1)
