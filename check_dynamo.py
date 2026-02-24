import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('Inventory')

response = table.scan(Limit=20)
print("--- DynamoDB Items ---")
for item in response['Items']:
    print(f"'{item['product_id']}'")
