import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
import os
import operator
from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "pharmacy.db")

# --- Structured Output Schema ---
class ExtractedOrder(BaseModel):
    patient_id: Optional[str] = Field(description="The unique identifier for the patient, e.g., PAT001")
    product_name: str = Field(description="The name of the medicine requested")
    quantity: int = Field(default=1, description="The number of units requested")

from contextlib import asynccontextmanager

# --- Global Graph Variable ---
app_graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_graph
    # PERSISTENCE LAYER: Uses SQLite to store checkpointers
    # Note: Using the context manager to ensure the connection is handled correctly
    with SqliteSaver.from_conn_string(DB_PATH) as memory:
        app_graph = workflow.compile(checkpointer=memory)
        yield

app = FastAPI(title="Sovereign Pharmacist API (Persistent & HIL)", lifespan=lifespan)

@app.post("/agent/order")
async def process_order(order: OrderRequest):
    thread_id = order.thread_id or f"order_{os.urandom(4).hex()}"
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "input_text": order.message,
        "patient_id": order.patient_id,
        "product_name": None,
        "quantity": 1,
        "status": "pending",
        "reason": "",
        "agent_thought": []
    }
    
    result = app_graph.invoke(initial_state, config=config)
    
    return {
        "thread_id": thread_id,
        "status": result["status"],
        "reason": result.get("reason", ""),
        "agent_thought": result["agent_thought"]
    }

@app.post("/admin/approve_hold")
async def approve_hold(req: ApprovalRequest):
    """Sovereign Human-in-the-Loop: Pharmacist manually approves a 'HOLD' state."""
    config = {"configurable": {"thread_id": req.thread_id}}
    
    # 1. Fetch current state
    state = app_graph.get_state(config)
    if not state.values or state.values.get("status") != "hold":
        raise HTTPException(status_code=400, detail="No active HOLD order found for this thread.")
    
    # 2. Force status to 'approved' and continue
    app_graph.update_state(config, {"status": "approved", "agent_thought": [f"Pharmacist: {req.admin_notes}"]}, as_node="validator")
    
    # 3. Resume execution from the next node (Action)
    result = app_graph.invoke(None, config=config)
    
    return {
        "status": result["status"],
        "agent_thought": result["agent_thought"]
    }

@app.get("/admin/proactive_refills")
async def get_proactive_refills():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id as 'Patient ID', product_name as 'Product Name', predicted_date as 'Predicted Refill Date', action as 'Action' FROM refill_predictions")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
