import time, os, sys
import requests

ns = os.getenv("NAMESPACE")
consumption_factor = os.getenv("CONSUMPTION_FACTOR")
pod_name = os.getenv("POD_NAME")

while True:
    time.sleep(5)
    r = requests.post(f"http://gpu-timekeeper.kube-system/budget/{ns}/report", 
    json={  "usage_factor": float(consumption_factor),
            "pod_name": pod_name})
    if r.json()["terminate"]:
        sys.exit(0)
