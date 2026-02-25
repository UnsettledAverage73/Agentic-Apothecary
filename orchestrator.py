import os
import requests
import json
import re
import urllib.parse
from typing import TypedDict, List, Optional, Literal
from langgraph.graph import StateGraph, END
from groq import Groq
from rapidfuzz import process, fuzz
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Load product names for NLU mapping
import pandas as pd
try:
    df = pd.read_csv("mock_inventory.csv")
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
    cot_logic: List[str]  # Chain of Thought logs

# API Configuration
API_BASE_URL = "http://127.0.0.1:8000"

# 2. Optimized Node: IntakeNode (Groq + RapidFuzz Fallback)
def intake_node(state: PharmacyState):
    print("--- GROQ INTAKE NODE ---")
    if 'cot_logic' not in state: state['cot_logic'] = []
    state['cot_logic'].append("Thinking: Extracting patient_id and mapping medication using Groq + RapidFuzz fallback...")
    
    # 1. Regex for Patient ID
    patient_match = re.search(r'(PAT\d+)', state['raw_input'], re.IGNORECASE)
    detected_patient = patient_match.group(1).upper() if patient_match else "Unknown"

    # 2. RapidFuzz Prep
    choices = {name: name.split(',')[0].replace('®', '') for name in PRODUCT_NAMES}
    fuzzy_match = process.extractOne(state['raw_input'], choices, scorer=fuzz.partial_ratio)
    detected_product = fuzzy_match[2] if fuzzy_match and fuzzy_match[1] > 50 else "Unknown"

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert pharmacist AI. Output JSON ONLY."},
                {"role": "user", "content": f"Match request to inventory:\nRequest: {state['raw_input']}\nInventory: {PRODUCT_LIST_STR}\nReturn JSON: {{\"patient_id\": \"{detected_patient}\", \"product_id\": \"EXACT_NAME\", \"quantity\": 1}}"}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(completion.choices[0].message.content)
        state['patient_id'] = data.get('patient_id', detected_patient)
        state['product_id'] = data.get('product_id', detected_product)
        state['quantity'] = data.get('quantity', 1)
        state['cot_logic'].append(f"Observation: Groq Llama-3 matched {state['product_id']} for {state['patient_id']}.")
    except Exception as e:
        state['cot_logic'].append(f"Observation: Groq failed ({str(e)}). Using RapidFuzz Optimization.")
        state['patient_id'] = detected_patient
        state['product_id'] = detected_product
        state['quantity'] = 1
        state['cot_logic'].append(f"Observation: RapidFuzz extracted {state['product_id']} (Confidence: {int(fuzzy_match[1]) if fuzzy_match else 0}%).")
    
    return state

# 3. Node: SafetyNode (Inventory & Rx Check)
def safety_node(state: PharmacyState):
    print("--- SAFETY NODE ---")
    state['cot_logic'].append(f"Thinking: Checking inventory and prescription requirements for {state['product_id']}...")
    try:
        # Use URL encoding for special characters
        encoded_product_id = urllib.parse.quote(state['product_id'])
        inv_res = requests.get(f"{API_BASE_URL}/inventory", params={"product_id": state['product_id']})
        if inv_res.status_code != 200:
            state['status'] = "REJECTED"
            state['cot_logic'].append(f"Observation: Medicine '{state['product_id']}' not in formulary.")
            return state
            
        inv_data = inv_res.json()
        state['is_rx_required'] = inv_data.get('prescription_required') == 'Yes'
        state['stock_level'] = int(inv_data.get('stock_level', 0))

        if state['is_rx_required']:
            state['cot_logic'].append("Observation: This medication requires a prescription.")
            # Trigger "Prescription Missing" check (simplified for now: check predictions)
            pred_res = requests.get(f"{API_BASE_URL}/patient/{state['patient_id']}/predictions")
            predictions = pred_res.json()
            match = next((p for p in predictions if p['product_name'] == state['product_id']), None)
            
            if not match:
                state['status'] = "PRESCRIPTION_MISSING"
                state['cot_logic'].append("Action: Flagging missing prescription.")
                return state
        
        if state['stock_level'] < state['quantity']:
            state['status'] = "OUT_OF_STOCK"
            state['cot_logic'].append(f"Observation: Insufficient stock ({state['stock_level']} available).")
            return state

        state['status'] = "SAFETY_CLEARED"
        state['cot_logic'].append("Observation: Safety checks passed.")
    except Exception as e:
        state['status'] = "ERROR"
        state['cot_logic'].append(f"Error: Safety check failed: {str(e)}")
    
    return state

# 4. Node: ActionNode (Order & SNS)
def action_node(state: PharmacyState):
    print("--- ACTION NODE ---")
    if state['status'] != "SAFETY_CLEARED":
        return state
    
    state['cot_logic'].append("Thinking: Executing order and sending AWS SNS notification...")
    try:
        payload = {
            "patient_id": state['patient_id'],
            "product_id": state['product_id'],
            "quantity": state['quantity']
        }
        response = requests.post(f"{API_BASE_URL}/order/execute", json=payload)
        if response.status_code == 200:
            state['status'] = "COMPLETED"
            state['cot_logic'].append("Observation: Order processed and SNS triggered.")
        else:
            state['status'] = "FAILED"
            state['cot_logic'].append(f"Error: {response.json().get('detail')}")
    except Exception as e:
        state['status'] = "ERROR"
        state['cot_logic'].append(f"Error: Order execution failed: {str(e)}")
    
    return state

# 5. Build the Graph
workflow = StateGraph(PharmacyState)

workflow.add_node("intake", intake_node)
workflow.add_node("safety", safety_node)
workflow.add_node("action", action_node)

workflow.set_entry_point("intake")
workflow.add_edge("intake", "safety")

# Conditional Edges for Branching
def route_safety(state: PharmacyState) -> Literal["action", "end"]:
    if state['status'] == "SAFETY_CLEARED":
        return "action"
    return "end"

workflow.add_conditional_edges("safety", route_safety, {"action": "action", "end": END})
workflow.add_edge("action", END)

app = workflow.compile()

if __name__ == "__main__":
    test_input = "Hi, I am PAT001 and I need refill of Panthenol spray"
    initial_state = {
        "raw_input": test_input,
        "patient_id": "Unknown",
        "product_id": "Unknown",
        "quantity": 0,
        "is_rx_required": False,
        "stock_level": 0,
        "status": "STARTING",
        "messages": [],
        "cot_logic": []
    }
    final_output = app.invoke(initial_state)
    print("\n--- FINAL CHAIN OF THOUGHT ---")
    for step in final_output['cot_logic']:
        print(step)
    print(f"\nFinal Status: {final_output['status']}")

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
