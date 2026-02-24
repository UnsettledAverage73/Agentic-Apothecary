import boto3
import pandas as pd
import os
import json
from decimal import Decimal

# Set up AWS
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
inventory_table = dynamodb.Table('Inventory')
patient_state_table = dynamodb.Table('PatientState')

def convert_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimal(v) for v in obj]
    return obj

def migrate_inventory():
    print("Migrating Inventory...")
    # Load products
    products_df = pd.read_excel('db/products-export.xlsx')
    
    # Load stock levels (if available)
    try:
        mock_inv = pd.read_csv('mock_inventory.csv')
        stock_map = dict(zip(mock_inv['product name'], mock_inv['stock_level']))
        rx_map = dict(zip(mock_inv['product name'], mock_inv['prescription_required']))
    except:
        stock_map = {}
        rx_map = {}

    for _, row in products_df.iterrows():
        prod_name = row['product name']
        item = {
            'product_id': prod_name,
            'name': prod_name,
            'pzn': str(row['pzn']),
            'price': row['price rec'],
            'package_size': row['package size'],
            'prescription_required': rx_map.get(prod_name, 'No'),
            'stock_level': stock_map.get(prod_name, 100)
        }
        inventory_table.put_item(Item=convert_decimal(item))
    print("Inventory migration complete.")

def migrate_patients():
    print("Migrating Patients...")
    # Load order history
    history_df = pd.read_excel('db/Consumer Order History 1.xlsx', header=4)
    
    # Load predictions
    try:
        pred_df = pd.read_csv('pharmacy_refill_predictions.csv')
        proactive_df = pd.read_csv('proactive_refills.csv')
        all_preds = pd.concat([pred_df, proactive_df]).drop_duplicates()
    except:
        all_preds = pd.DataFrame()

    patients = {}

    # Process history
    for _, row in history_df.iterrows():
        p_id = row['Patient ID']
        if p_id not in patients:
            patients[p_id] = {'patient_id': p_id, 'orders': [], 'refill_predictions': []}
        
        order = {
            'product_name': row['Product Name'],
            'purchase_date': str(row['Purchase Date']),
            'quantity': row['Quantity'],
            'dosage_frequency': row['Dosage Frequency']
        }
        patients[p_id]['orders'].append(order)

    # Process predictions
    for _, row in all_preds.iterrows():
        p_id = row['Patient ID']
        if p_id not in patients:
            patients[p_id] = {'patient_id': p_id, 'orders': [], 'refill_predictions': []}
        
        pred = {
            'product_name': row['Product Name'],
            'predicted_date': row['Predicted Refill Date'],
            'action': row['Action']
        }
        patients[p_id]['refill_predictions'].append(pred)

    # Put in DynamoDB
    for p_id, data in patients.items():
        patient_state_table.put_item(Item=convert_decimal(data))
    
    print("Patient migration complete.")

if __name__ == "__main__":
    migrate_inventory()
    migrate_patients()
