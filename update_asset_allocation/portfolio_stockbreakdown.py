import json
from collections import defaultdict
import os

# File paths
HOLDINGS_FILE_PATH = 'data/portfolio_data/updated_portfolio.json'
BREAKDOWN_DIR = 'data/mf_stock_breakdown_data'

# Load holdings data
with open(HOLDINGS_FILE_PATH, 'r') as f:
    holdings_data = json.load(f)
holdings = holdings_data['holdings']

# Map scheme IDs to breakdown files
breakdown_files = [f for f in os.listdir(BREAKDOWN_DIR) if f.endswith('.json')]
scheme_id_to_file = {f.rsplit('_', 1)[-1].replace('.json', ''): os.path.join(BREAKDOWN_DIR, f) for f in breakdown_files}

# Aggregate stock values and track sectors
stock_values = defaultdict(float)
stock_to_sector = {}
total_portfolio_value = 0

for holding in holdings:
    scheme_id = holding['SchemeID']
    value = holding['Value']
    total_portfolio_value += value

    if scheme_id == 'N/A':
        # Direct stock holding
        stock_name = holding['Security']
        stock_values[stock_name] += value
        if stock_name not in stock_to_sector:
            stock_to_sector[stock_name] = holding.get('Sector', 'N/A')
    else:
        # Mutual fund holding
        breakdown_file = scheme_id_to_file.get(scheme_id)
        if breakdown_file:
            with open(breakdown_file, 'r') as f:
                breakdown = json.load(f)
            for stock in breakdown:
                stock_name = stock['Stock']
                percentage = stock['Percentage_of_Total_Holdings']  # e.g., 0.5 means 50%
                effective_value = percentage * value  # No /100, as it’s already a fraction
                stock_values[stock_name] += effective_value
                if stock_name not in stock_to_sector:
                    stock_to_sector[stock_name] = stock['Sector']
        else:
            print(f"Warning: No breakdown file found for SchemeID {scheme_id}")

# Calculate total stock value after aggregation
total_stock_value = sum(stock_values.values())

# Build output
portfolio_stockbreakdown = [
    {
        'Stock': stock_name,
        'Sector': stock_to_sector.get(stock_name, 'N/A'),
        'Value': round(value, 2),
        'Percentage_of_Total_Holdings': round((value / total_stock_value) * 100, 4)
    }
    for stock_name, value in stock_values.items()
]

# Sort by percentage descending
portfolio_stockbreakdown.sort(key=lambda x: x['Percentage_of_Total_Holdings'], reverse=True)

# Save output
with open('data/portfolio_data/portfolio_stockbreakdown.json', 'w') as f:
    json.dump(portfolio_stockbreakdown, f, indent=4)

# Debug output
print(f"Total Portfolio Value: {total_portfolio_value}")
print(f"Total Stock Value: {total_stock_value}")
print(f"Number of Stocks: {len(portfolio_stockbreakdown)}")