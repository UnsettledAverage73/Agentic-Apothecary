import streamlit as st
import os
import requests
import pandas as pd
from orchestrator import app as graph_app
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv()

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

st.set_page_config(page_title="Sovereign-RX Agentic Portal", page_icon="💊", layout="wide")

def speak_text(text):
    try:
        # Get available voices and use the first one if Rachel is missing
        voices = client.voices.get_all().voices
        voice_id = "21mOBAZ6jtBlW7lUX7eR" # Default to Rachel
        
        # Check if Rachel exists in user's account, otherwise pick the first
        if not any(v.voice_id == voice_id for v in voices):
            voice_id = voices[0].voice_id
            
        audio_stream = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2"
        )
        audio_bytes = b"".join(audio_stream)
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
    except Exception as e:
        st.error(f"Voice Synthesis Error: {e}")

# Custom CSS for a clean, medical feel
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .status-card { padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; background-color: white; margin-bottom: 10px; }
    .cot-step { padding: 10px; border-left: 4px solid #007bff; background: #f0f7ff; margin: 5px 0; border-radius: 0 5px 5px 0; }
    .observation { padding: 10px; border-left: 4px solid #28a745; background: #f0fff4; margin: 5px 0; border-radius: 0 5px 5px 0; }
    </style>
    """, unsafe_allow_html=True)

st.title("💊 Sovereign-RX: AI Pharmacist Portal")

tabs = st.tabs(["🤖 Agent Orchestrator", "📈 Proactive Alerts", "⚙️ System Status"])

with tabs[0]:
    st.subheader("Multi-Agent Chain of Thought")
    
    col_in, col_out = st.columns([1, 1])
    
    with col_in:
        user_input = st.text_area("Patient Request (Natural Language):", 
                                 placeholder="e.g., Hi, I'm PAT001 and I need a refill of Panthenol Spray.",
                                 height=150)
        process_btn = st.button("🚀 Process Order")

    if process_btn:
        if not user_input:
            st.warning("Please enter a request.")
        else:
            initial_state = {
                "raw_input": user_input,
                "patient_id": "Unknown",
                "product_id": "Unknown",
                "quantity": 1,
                "is_rx_required": False,
                "stock_level": 0,
                "status": "STARTING",
                "messages": [],
                "cot_logic": []
            }

            with st.status("Agents are collaborating...", expanded=True) as status:
                st.write("🏃 IntakeNode parsing request...")
                final_output = graph_app.invoke(initial_state)
                st.write("⚖️ SafetyNode verifying records...")
                st.write("📦 ActionNode executing fulfillment...")
                status.update(label="Orchestration Complete!", state="complete", expanded=False)

            with col_out:
                st.markdown("### 🧠 Agent Reasoning")
                for step in final_output['cot_logic']:
                    if "Thinking" in step:
                        st.markdown(f"<div class='cot-step'>🔍 {step}</div>", unsafe_allow_html=True)
                    elif "Observation" in step:
                        st.markdown(f"<div class='observation'>📝 {step}</div>", unsafe_allow_html=True)
                    else:
                        st.write(step)

                st.markdown("### 📊 Summary")
                st.write(f"**Patient:** {final_output['patient_id']} | **Product:** {final_output['product_id']}")
                
                status_val = final_output['status']
                if status_val == "COMPLETED":
                    confirmation_msg = f"Order for {final_output['patient_id']} has been successfully processed. {final_output['product_id']} will be ready shortly."
                    st.success(f"✅ Status: {status_val}")
                    speak_text(confirmation_msg)
                else:
                    error_msg = f"I'm sorry, the order for {final_output['patient_id']} could not be completed because of {status_val}."
                    st.error(f"❌ Status: {status_val}")
                    speak_text(error_msg)

with tabs[1]:
    st.subheader("Predictive Refill Intelligence")
    if st.button("🔄 Refresh Alerts"):
        try:
            response = requests.get("http://127.0.0.1:8000/admin/proactive_refills")
            if response.status_code == 200:
                df = pd.DataFrame(response.json())
                st.dataframe(df, use_container_width=True)
            else:
                st.error("Failed to fetch alerts from backend.")
        except Exception as e:
            st.error(f"Connection error: {e}")

with tabs[2]:
    st.subheader("Environment Configuration")
    st.info(f"**Backend:** Running on localhost:8000")
    st.info(f"**LLM:** Gemini-2.0-Flash")
    st.info(f"**Storage:** AWS DynamoDB (Inventory & PatientState)")

st.markdown("---")
st.caption("Agentic Apothecary Framework v1.0 | Powered by LangGraph, Gemini & AWS")

st.markdown("---")
st.caption("Agentic Apothecary Framework v1.0 | Powered by LangGraph & Gemini")
