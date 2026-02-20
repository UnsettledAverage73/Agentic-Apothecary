from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import uvicorn
import os
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
# from langfuse.callback import CallbackHandler # Optional: Langfuse integration

# Load Source of Truth
inventory_df = pd.read_csv('mock_inventory.csv')
history_df = pd.read_csv('pharmacy_refill_predictions.csv')

app = FastAPI(title="Sovereign Pharmacist API")

class OrderRequest(BaseModel):
    patient_id: str
    product_name: str
    quantity: int

# --- LangGraph State Machine ---

class AgentState(TypedDict):
    patient_id: str
    product_name: str
    quantity: int
    status: str
    reason: str
    agent_thought: List[str]

def nlu_agent(state: AgentState):
    # Extracts Entities (Medicine, Dosage, Qty) from messy voice/text.
    # In a real system, this would call an LLM (e.g., OpenAI/Anthropic)
    thought = f"NLU: Extraction complete. Patient {state['patient_id']} requested {state['quantity']}x {state['product_name']}."
    return {"agent_thought": [thought]}

def validator_agent(state: AgentState):
    # Cross-references the "Source of Truth" (Inventory & Prescription rules).
    product_name = state['product_name']
    quantity = state['quantity']
    
    # Case-insensitive substring match for robustness
    product_info = inventory_df[inventory_df['product name'].str.contains(product_name, na=False, case=False)]
    
    if product_info.empty:
        thought = f"Validator: {product_name} not found in formulary."
        return {"status": "rejected", "reason": "Medicine not in formulary", "agent_thought": state['agent_thought'] + [thought]}
    
    row = product_info.iloc[0]
    thought = f"Validator: Found {row['product name']}. Checking Rx and Stock."
    
    if row['prescription_required'] == 'Yes':
        thought += " Rx required - status set to HOLD."
        return {"status": "hold", "reason": "Agent: Manual Prescription Verification Required", "agent_thought": state['agent_thought'] + [thought]}
    
    if row['stock_level'] < quantity:
        thought += f" Stock insufficient ({row['stock_level']} available)."
        return {"status": "rejected", "reason": "Out of stock. Procurement triggered.", "agent_thought": state['agent_thought'] + [thought]}
    
    thought += " Safety check passed. Inventory sufficient."
    return {"status": "approved", "agent_thought": state['agent_thought'] + [thought]}

def predictive_agent(state: AgentState):
    # Analyzes Consumer Order History to trigger proactive refills.
    # Here we simulate checking if this order was expected based on the history
    patient_history = history_df[history_df['Patient ID'] == state['patient_id']]
    if not patient_history.empty:
        thought = "Predictive: Order aligns with historical usage patterns."
    else:
        thought = "Predictive: New patient/product combination detected."
    
    return {"agent_thought": state['agent_thought'] + [thought]}

def action_agent(state: AgentState):
    # Updates the DB and triggers external Webhooks (Zapier/n8n).
    if state['status'] == 'approved':
        # Simulate inventory update logic
        thought = "Action: Updating inventory. Triggering fulfillment webhook."
        return {"agent_thought": state['agent_thought'] + [thought]}
    else:
        thought = f"Action: Execution skipped due to {state['status']} status."
        return {"agent_thought": state['agent_thought'] + [thought]}

# Build the Graph
workflow = StateGraph(AgentState)

workflow.add_node("nlu", nlu_agent)
workflow.add_node("validator", validator_agent)
workflow.add_node("predictive", predictive_agent)
workflow.add_node("action", action_agent)

workflow.set_entry_point("nlu")
workflow.add_edge("nlu", "validator")
workflow.add_edge("validator", "predictive")
workflow.add_edge("predictive", "action")
workflow.add_edge("action", END)

app_graph = workflow.compile()

@app.post("/agent/order")
async def process_order(order: OrderRequest):
    initial_state = {
        "patient_id": order.patient_id,
        "product_name": order.product_name,
        "quantity": order.quantity,
        "status": "pending",
        "reason": "",
        "agent_thought": []
    }
    
    # Optional: langfuse_handler = CallbackHandler(host=os.getenv("LANGFUSE_HOST"), public_key=os.getenv("LANGFUSE_PUBLIC_KEY"), secret_key=os.getenv("LANGFUSE_SECRET_KEY"))
    
    result = app_graph.invoke(initial_state)
    
    return {
        "status": result["status"],
        "reason": result.get("reason", ""),
        "agent_thought": result["agent_thought"]
    }

@app.get("/admin/proactive_refills")
async def get_proactive_refills():
    proactive_df = pd.read_csv('proactive_refills.csv')
    return proactive_df.to_dict(orient='records')

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

