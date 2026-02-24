import pandas as pd
import re
import sqlite3
from datetime import timedelta, datetime

DB_PATH = "pharmacy.db"
CURRENT_DATE = datetime(2024, 3, 27)

def extract_unit_count(package_size):
    if not isinstance(package_size, str):
        return 10
    match_x = re.search(r'(\d+)\s*x', package_size)
    if match_x: return int(match_x.group(1))
    match_num = re.search(r'(\d+)', package_size)
    if match_num: return int(match_num.group(1))
    return 10

def map_dosage(dosage_str):
    mapping = {'Once daily': 1, 'Twice daily': 2, 'Three times daily': 3, 'As needed': 1}
    return mapping.get(dosage_str, 1)

def calculate_probabilistic_refills():
    conn = sqlite3.connect(DB_PATH)
    
    # Load orders and products
    orders_df = pd.read_sql_query("SELECT * FROM orders", conn)
    products_df = pd.read_sql_query("SELECT name, package_size FROM products", conn)
    
    orders_df['purchase_date'] = pd.to_datetime(orders_df['purchase_date'])
    
    # 1. Group by patient and product to find intervals
    predictions = []
    
    for (pid, pname), group in orders_df.groupby(['patient_id', 'product_name']):
        group = group.sort_values('purchase_date')
        last_order = group.iloc[-1]
        
        # Get product details
        p_info = products_df[products_df['name'] == pname].iloc[0]
        unit_count = extract_unit_count(p_info['package_size'])
        theoretical_dosage = map_dosage(last_order['dosage_frequency'])
        theoretical_days = (unit_count * last_order['quantity']) / theoretical_dosage
        
        # Calculate Observed Interval if multiple orders exist
        if len(group) > 1:
            # Average days between purchases
            intervals = group['purchase_date'].diff().dt.days.dropna()
            avg_observed_interval = intervals.mean()
            
            # Use Observed Interval (it accounts for 'As needed' behavior)
            # We use a 70/30 weight towards observed behavior
            final_days_estimate = (0.7 * avg_observed_interval) + (0.3 * theoretical_days)
            logic_used = "Probabilistic (Observed Behavior)"
        else:
            final_days_estimate = theoretical_days
            logic_used = "Theoretical (Fixed Dosage)"
            
        predicted_date = last_order['purchase_date'] + timedelta(days=int(final_days_estimate))
        
        # Determine Action
        days_diff = (predicted_date - CURRENT_DATE).days
        if days_diff < 0: action = 'OVERDUE - Trigger Outreach'
        elif days_diff <= 5: action = f'Alert in {days_diff} days'
        else: action = 'No action needed yet'
        
        if action != 'No action needed yet':
            predictions.append({
                'patient_id': pid,
                'product_name': pname,
                'predicted_date': str(predicted_date.date()),
                'action': action
            })

    # Save to Database
    conn.execute("DELETE FROM refill_predictions")
    for pred in predictions:
        conn.execute("""
        INSERT INTO refill_predictions (patient_id, product_name, predicted_date, action)
        VALUES (?, ?, ?, ?)
        """, (pred['patient_id'], pred['product_name'], pred['predicted_date'], pred['action']))
    
    conn.commit()
    conn.close()
    print(f"Probabilistic Refill Engine complete. Processed {len(predictions)} alerts.")

if __name__ == "__main__":
    calculate_probabilistic_refills()
