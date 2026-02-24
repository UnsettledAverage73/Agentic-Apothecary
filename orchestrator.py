import os
import requests
import json
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Load product names for NLU mapping
import pandas as pd
try:
    df = pd.read_csv("mock_inventory.csv")
    # Only take the first 50 to avoid token limits if the list is huge, though 53 is fine.
    PRODUCT_NAMES = df['product name'].tolist()
    PRODUCT_LIST_STR = "\n".join([f"- {name}" for name in PRODUCT_NAMES])
except Exception as e:
    print(f"Error loading inventory: {e}")
    PRODUCT_LIST_STR = "Error loading product list."

# 1. Define the State
class PharmacyState(TypedDict):
    raw_input: str
    patient_id: str
    product_id: str
    quantity: int
    is_rx_required: bool
    stock_level: int
    status: str
    messages: List[str]

# API Configuration
API_BASE_URL = "http://localhost:8000"

# 2. Node: IntakeAgent (Gemini NLU)
def intake_agent(state: PharmacyState):
    print("--- INTAKE AGENT (Gemini) ---")
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
    You are an expert pharmacist AI.
    User Request: "{state['raw_input']}"
    
    Task:
    1. Identify the Patient ID (e.g., PAT001).
    2. Identify the requested medication and quantity.
    3. MATCH the medication to one of the following VALID PRODUCT NAMES from our inventory:
    
    {PRODUCT_LIST_STR}
    
    Constraints:
    - Return the EXACT product name from the list above as 'product_id'.
    - If the user's request is close (e.g., "Panthenol spray"), map it to the full name (e.g., "Panthenol Spray, 46,3 mg/g Schaum...").
    - If no match is found, use "Unknown".
    - Set default quantity to 1 if not specified.
    
    Return JSON only: {{"patient_id": "...", "product_id": "...", "quantity": int}}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        state['patient_id'] = data.get('patient_id', state['patient_id'])
        state['product_id'] = data.get('product_id', state['product_id'])
        state['quantity'] = data.get('quantity', 1) # Default to 1
        state['messages'].append(f"NLU Parsed: {state['product_id']} for {state['patient_id']}")
    except Exception as e:
        state['messages'].append(f"NLU failed: {str(e)}")
    
    return state

# 3. Node: SafetyPharmacist (Enhanced)
def safety_pharmacist(state: PharmacyState):
    print("--- SAFETY PHARMACIST (Enhanced) ---")
    try:
        # Check Inventory
        inv_res = requests.get(f"{API_BASE_URL}/inventory", params={"product_id": state['product_id']})
        if inv_res.status_code != 200:
            state['status'] = f"REJECTED: Medicine '{state['product_id']}' not found."
            return state
            
        inv_data = inv_res.json()
        state['is_rx_required'] = inv_data.get('prescription_required') == 'Yes'
        state['stock_level'] = int(inv_data.get('stock_level', 0))

        # Check Patient Records
        pred_res = requests.get(f"{API_BASE_URL}/patient/{state['patient_id']}/predictions")
        predictions = pred_res.json()
        
        # Cross-reference
        match = next((p for p in predictions if p['product_name'] == state['product_id']), None)
        
        if state['is_rx_required'] and not match:
            state['status'] = "REJECTED: Rx required but no matching prediction found."
            return state

        if match:
            state['messages'].append(f"Matched Record Action: {match['action']}")
            if "OVERDUE" in match['action']:
                state['messages'].append("Safety Alert: Patient is overdue. Expediting order.")

        state['status'] = "SAFETY_CLEARED"
    except Exception as e:
        state['status'] = f"ERROR: Safety check failed: {str(e)}"
    
    return state

# 4. Node: FulfillmentClerk
def fulfillment_clerk(state: PharmacyState):
    print("--- FULFILLMENT CLERK ---")
    if state['status'] != "SAFETY_CLEARED":
        return state
    
    try:
        payload = {
            "patient_id": state['patient_id'],
            "product_id": state['product_id'],
            "quantity": state['quantity']
        }
        response = requests.post(f"{API_BASE_URL}/order/execute", json=payload)
        if response.status_code == 200:
            res_data = response.json()
            state['status'] = "ORDER_COMPLETED"
            state['messages'].append(f"Success! Remaining stock: {res_data['remaining_stock']}")
        else:
            state['status'] = f"FAILED: {response.json().get('detail')}"
    except Exception as e:
        state['status'] = f"ERROR: Order execution failed: {str(e)}"
    
    return state

# 5. Build the Graph
workflow = StateGraph(PharmacyState)

workflow.add_node("intake", intake_agent)
workflow.add_node("safety_check", safety_pharmacist)
workflow.add_node("fulfillment", fulfillment_clerk)

workflow.set_entry_point("intake")
workflow.add_edge("intake", "safety_check")
workflow.add_edge("safety_check", "fulfillment")
workflow.add_edge("fulfillment", END)

app = workflow.compile()

# Example Test Run
if __name__ == "__main__":
    # Test with natural language
    test_input = "Hi, I am PAT001 and I need refill of Panthenol spray"
    
    initial_state = {
        "raw_input": test_input,
        "patient_id": "Unknown",
        "product_id": "Unknown",
        "quantity": 0,
        "is_rx_required": False,
        "stock_level": 0,
        "status": "STARTING",
        "messages": []
    }
    
    final_output = app.invoke(initial_state)
    print("\n--- FINAL GRAPH STATE ---")
    print(f"Status: {final_output['status']}")
    for msg in final_output['messages']:
        print(f"Log: {msg}")
