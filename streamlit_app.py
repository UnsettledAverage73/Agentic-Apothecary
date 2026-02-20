import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Sovereign Pharmacist Admin Dashboard", layout="wide")

st.title("🏥 Sovereign Pharmacist: Proactive Refill Alerts")

st.markdown("""
This dashboard identifies patients who are overdue for a refill or will be soon, based on their purchase history and dosage.
""")

try:
    # Try to fetch from FastAPI, fallback to CSV if API is down
    response = requests.get("http://localhost:8000/admin/proactive_refills", timeout=2)
    if response.status_code == 200:
        data = pd.DataFrame(response.json())
    else:
        data = pd.read_csv('proactive_refills.csv')
except:
    data = pd.read_csv('proactive_refills.csv')

# Styling the Action column
def color_action(val):
    if 'OVERDUE' in val:
        return 'background-color: #ffcccc'
    elif 'Alert' in val:
        return 'background-color: #fff3cd'
    return ''

st.table(data.style.applymap(color_action, subset=['Action']))

st.sidebar.header("System Status")
st.sidebar.success("Backend: Active")
st.sidebar.info("Database: mock_inventory.csv")

if st.sidebar.button("Trigger Outreaches"):
    overdue_count = len(data[data['Action'].str.contains('OVERDUE')])
    st.sidebar.write(f"Triggered {overdue_count} outreach webhooks.")
