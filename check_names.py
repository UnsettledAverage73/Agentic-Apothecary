import pandas as pd

try:
    df = pd.read_excel('db/products-export.xlsx')
    print("--- From Excel ---")
    print(df['product name'].head(10).tolist())
    
    df_csv = pd.read_csv('mock_inventory.csv')
    print("--- From CSV ---")
    print(df_csv['product name'].head(10).tolist())
except Exception as e:
    print(e)
