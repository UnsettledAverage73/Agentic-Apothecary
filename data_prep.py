import pandas as pd
import re
from datetime import timedelta, datetime

# Mock current date for calculations (to match user's example)
CURRENT_DATE = datetime(2024, 3, 27)

def extract_unit_count(package_size):
    if not isinstance(package_size, str):
        return 10
    # Try to find something like 30x0.5 ml -> 30
    match_x = re.search(r'(\d+)\s*x', package_size)
    if match_x:
        return int(match_x.group(1))
    # Try to find something like 120 st -> 120
    match_num = re.search(r'(\d+)', package_size)
    if match_num:
        return int(match_num.group(1))
    return 10

def map_dosage(dosage_str):
    mapping = {
        'Once daily': 1,
        'Twice daily': 2,
        'Three times daily': 3,
        'As needed': 1
    }
    return mapping.get(dosage_str, 1)

# Load data
history_df = pd.read_excel('db/Consumer Order History 1.xlsx', header=4)
products_df = pd.read_excel('db/products-export.xlsx')

# Merge to get package size
merged_df = pd.merge(
    history_df,
    products_df[['product name', 'package size']],
    left_on='Product Name',
    right_on='product name',
    how='left'
)

# Prepare columns
merged_df['Unit Count'] = merged_df['package size'].apply(extract_unit_count)
merged_df['Daily Dosage'] = merged_df['Dosage Frequency'].apply(map_dosage)
merged_df['Days Until Empty'] = (merged_df['Unit Count'] * merged_df['Quantity']) / merged_df['Daily Dosage']
merged_df['Predicted Refill Date'] = merged_df.apply(
    lambda row: row['Purchase Date'] + timedelta(days=int(row['Days Until Empty'])),
    axis=1
)

# 1. mock_inventory.csv
# product name, stock_level, prescription_required
inventory = merged_df[['Product Name', 'Prescription Required']].drop_duplicates()
inventory.columns = ['product name', 'prescription_required']
inventory['stock_level'] = 100
inventory.to_csv('mock_inventory.csv', index=False)

# 2. pharmacy_refill_predictions.csv
# Patient ID, Product Name, Predicted Refill Date, Action
predictions = merged_df[['Patient ID', 'Product Name', 'Predicted Refill Date']].copy()

def get_action(refill_date):
    days_diff = (refill_date - CURRENT_DATE).days
    if days_diff < 0:
        return 'OVERDUE - Trigger Outreach'
    elif days_diff <= 2:
        return f'Alert in {days_diff} days'
    elif days_diff <= 5:
        return f'Alert in {days_diff} days'
    else:
        return 'No action needed yet'

predictions['Action'] = predictions['Predicted Refill Date'].apply(get_action)
predictions.to_csv('pharmacy_refill_predictions.csv', index=False)

# 3. proactive_refills.csv
proactive = predictions[predictions['Action'] != 'No action needed yet']
proactive.to_csv('proactive_refills.csv', index=False)

print("CSVs generated successfully.")
