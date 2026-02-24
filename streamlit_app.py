import streamlit as st
import os
from orchestrator import app as graph_app
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Sovereign-RX Agentic Portal", page_icon="💊", layout="wide")

# Custom CSS for a clean, medical feel
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .agent-box {
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        background-color: white;
        margin-bottom: 10px;
    }
    .status-completed { color: green; font-weight: bold; }
    .status-rejected { color: red; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("💊 Sovereign-RX: AI Pharmacist Portal")
st.subheader("Multi-Agent Orchestration via LangGraph")

with st.sidebar:
    st.header("System Configuration")
    api_url = st.text_input("Backend API URL", value="http://localhost:8000")
    st.info("This portal connects to your backend and uses Gemini-2.0-Flash for NLU.")
    
    if st.button("Reset Session"):
        st.session_state.messages = []
        st.rerun()

# Input Section
user_input = st.text_area("Patient Request (Natural Language):", 
                         placeholder="e.g., Hi, I'm PAT001 and I need a refill of Panthenol Spray.")

if st.button("Process Order"):
    if not user_input:
        st.warning("Please enter a request.")
    else:
        # Initialize Graph State
        initial_state = {
            "raw_input": user_input,
            "patient_id": "Unknown",
            "product_id": "Unknown",
            "quantity": 1,
            "is_rx_required": False,
            "stock_level": 0,
            "status": "STARTING",
            "messages": []
        }

        with st.status("Agents are collaborating...", expanded=True) as status:
            st.write("🏃 IntakeAgent parsing request...")
            # Run the Graph
            final_output = graph_app.invoke(initial_state)
            
            st.write("⚖️ SafetyPharmacist verifying records...")
            st.write("📦 FulfillmentClerk checking inventory...")
            status.update(label="Orchestration Complete!", state="complete", expanded=False)

        # Display Results in Columns
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("### 🤖 Agent Decision Log")
            for msg in final_output['messages']:
                st.info(msg)

        with col2:
            st.markdown("### 📊 Transaction Summary")
            st.write(f"**Patient ID:** {final_output['patient_id']}")
            st.write(f"**Product:** {final_output['product_id']}")
            st.write(f"**Quantity:** {final_output['quantity']}")
            
            status_val = final_output['status']
            if "COMPLETED" in status_val:
                st.success(f"Final Status: {status_val}")
            elif "REJECTED" in status_val:
                st.error(f"Final Status: {status_val}")
            else:
                st.warning(f"Final Status: {status_val}")

st.markdown("---")
st.caption("Agentic Apothecary Framework v1.0 | Powered by LangGraph & Gemini")
