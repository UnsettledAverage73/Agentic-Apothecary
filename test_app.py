import requests
import time
import subprocess

# Start the server in background
# Use uv run to ensure dependencies are available
process = subprocess.Popen(["uv", "run", "python", "main.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3) # Wait for server to start

try:
    # Test Approved Order
    order = {
        "patient_id": "PAT001",
        "product_name": "NORSAN Omega-3 Total",
        "quantity": 1
    }
    response = requests.post("http://localhost:8000/agent/order", json=order)
    print("Test Approved Order Response:", response.json())

    # Test Rx Required Order
    order = {
        "patient_id": "PAT004",
        "product_name": "Mucosolvan",
        "quantity": 1
    }
    response = requests.post("http://localhost:8000/agent/order", json=order)
    print("Test Rx Required Order Response:", response.json())

    # Test Not in Formulary
    order = {
        "patient_id": "PAT001",
        "product_name": "Unknown Medicine",
        "quantity": 1
    }
    response = requests.post("http://localhost:8000/agent/order", json=order)
    print("Test Not in Formulary Response:", response.json())

    # Test Proactive Refills
    response = requests.get("http://localhost:8000/admin/proactive_refills")
    print("Proactive Refills (first 2):", response.json()[:2])

finally:
    process.terminate()
