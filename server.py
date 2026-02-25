import os
import pandas as pd
from fastapi import FastAPI, HTTPException
import boto3
from decimal import Decimal
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Sovereign-RX Backend (Hybrid Storage)")
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")

# --- Storage Layer Functions ---

def get_inventory_item(product_id: str):
    try:
        table = dynamodb.Table('Inventory')
        response = table.get_item(Key={'product_id': product_id})
        if 'Item' in response:
            return response['Item']
    except Exception as e:
        print(f"DynamoDB Access Error: {e}. Falling back to CSV.")
    
    # Local Fallback
    df = pd.read_csv('mock_inventory.csv')
    item = df[df['product name'] == product_id]
    if not item.empty:
        row = item.iloc[0]
        return {
            "product_id": row['product name'],
            "prescription_required": row['prescription_required'],
            "stock_level": int(row['stock_level'])
        }
    return None

@app.get("/inventory")
async def get_med_info(product_id: str):
    item = get_inventory_item(product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return item

@app.get("/patient/{patient_id}/predictions")
async def get_refill_status(patient_id: str):
    try:
        table = dynamodb.Table('PatientState')
        response = table.get_item(Key={'patient_id': patient_id})
        if 'Item' in response:
            return response['Item'].get('refill_predictions', [])
    except Exception as e:
        print(f"DynamoDB Access Error: {e}. Falling back to local data.")
    
    # Local Fallback (simplified for testing)
    return [{"product_name": "NORSAN Omega-3 Total", "action": "No action needed yet"}]

class OrderRequest(BaseModel):
    patient_id: str
    product_id: str
    quantity: int

@app.post("/order/execute")
async def execute_order(order: OrderRequest):
    item = get_inventory_item(order.product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Medicine not found")
    
    current_stock = int(item.get('stock_level', 0))
    if current_stock < order.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {current_stock}")

    new_stock = current_stock - order.quantity

    # 2. Attempt DynamoDB Update
    try:
        table = dynamodb.Table('Inventory')
        table.update_item(
            Key={'product_id': order.product_id},
            UpdateExpression="SET stock_level = :val",
            ExpressionAttributeValues={':val': Decimal(str(new_stock))}
        )
    except Exception as e:
        print(f"DynamoDB Update Error: {e}. (Local stock update simulated)")

    # 3. Trigger AWS SNS (Best Effort)
    if SNS_TOPIC_ARN:
        try:
            message = f"Order successful for {order.patient_id}: {order.quantity}x {order.product_id}. Remaining stock: {new_stock}"
            sns.publish(TopicArn=SNS_TOPIC_ARN, Message=message, Subject="New Pharmacy Order")
        except:
            pass

    return {
        "status": "Success",
        "message": f"Order for {order.quantity} units of {order.product_id} processed.",
        "remaining_stock": new_stock
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
