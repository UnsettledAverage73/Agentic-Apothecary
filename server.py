from fastapi import FastAPI, HTTPException
import boto3
from decimal import Decimal
from pydantic import BaseModel

app = FastAPI(title="Sovereign-RX Backend")
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Tables
inventory_table = dynamodb.Table('Inventory')
patient_state_table = dynamodb.Table('PatientState')

class OrderRequest(BaseModel):
    patient_id: str
    product_id: str
    quantity: int

@app.get("/inventory")
async def get_med_info(product_id: str):
    response = inventory_table.get_item(Key={'product_id': product_id})
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return response['Item']

@app.get("/patient/{patient_id}/predictions")
async def get_refill_status(patient_id: str):
    response = patient_state_table.get_item(Key={'patient_id': patient_id})
    if 'Item' not in response:
        return []
    return response['Item'].get('refill_predictions', [])

@app.post("/order/execute")
async def execute_order(order: OrderRequest):
    # 1. Check Inventory
    response = inventory_table.get_item(Key={'product_id': order.product_id})
    if 'Item' not in response:
        raise HTTPException(status_code=404, detail="Medicine not found")
    
    item = response['Item']
    current_stock = int(item.get('stock_level', 0))
    
    if current_stock < order.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {current_stock}")

    # 2. Decrement Stock
    new_stock = current_stock - order.quantity
    inventory_table.update_item(
        Key={'product_id': order.product_id},
        UpdateExpression="SET stock_level = :val",
        ExpressionAttributeValues={':val': Decimal(str(new_stock))}
    )

    # 3. Log Order to Patient State (Optional but recommended)
    # This part would append the new order to the patient's 'orders' list
    # For now, let's just return success
    return {
        "status": "Success",
        "message": f"Order for {order.quantity} units of {order.product_id} processed.",
        "remaining_stock": new_stock
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
