# 🏥 Sovereign Pharmacist: Autonomous Pharmacy Ecosystem

This project implements a **State-Aware Multi-Agent System** for a pharmacy, featuring predictive refill intelligence and LangGraph orchestration.

## 🚀 Quick Start

### 1. Prerequisites
- [uv](https://github.com/astral-sh/uv) (Recommended for Python environment management)
- Python 3.12+

### 2. Setup
```bash
# Install dependencies
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```
*(Dependencies: `pandas`, `openpyxl`, `fastapi`, `uvicorn`, `langgraph`, `streamlit`, `requests`)*

### 3. Data Preparation
Converts raw Excel files to the "Source of Truth" CSVs and calculates refill dates.
```bash
uv run python data_prep.py
```

### 4. Run the Backend (FastAPI)
Starts the LangGraph-powered orchestration layer.
```bash
uv run python main.py
```

### 5. Run the Admin Dashboard (Streamlit)
Visualizes proactive refill alerts and system status.
```bash
uv run streamlit run streamlit_app.py
```

## 🏗 System Architecture

The "Sovereign Pharmacist" framework uses a multi-agent orchestration pattern:
- **NLU Agent:** Extracts entities from patient requests.
- **Validator Agent:** Cross-references inventory and prescription rules.
- **Predictive Agent:** Analyzes order history to ensure adherence.
- **Action Agent:** Executes backend tasks (inventory updates, webhooks).

## 📊 Predictive Intelligence
The refill engine uses the formula:
$$Days\,Until\,Empty = \frac{Unit\,Count \times Quantity}{Daily\,Dosage}$$

Patients are flagged as:
- **OVERDUE:** Refill date has passed.
- **Alert in X days:** Refill date is approaching.

## 📁 Project Structure
- `data_prep.py`: Processes Excel data from `db/` into CSVs.
- `main.py`: FastAPI server with LangGraph state machine.
- `streamlit_app.py`: Admin dashboard for proactive refill monitoring.
- `db/`: Raw Excel data (Consumer Order History, Product Export).
- `mock_inventory.csv`: Generated source of truth for stock levels and Rx flags.
- `proactive_refills.csv`: Generated list of patients requiring outreach.
