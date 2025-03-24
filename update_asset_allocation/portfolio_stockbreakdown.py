import json
from collections import defaultdict
import os
import csv
from fuzzywuzzy import fuzz

# Function to clean stock names
def clean_stock_name(stock_name):
    stock_name = stock_name.replace(' Ltd.', ' Limited').replace(' Ltd', ' Limited').replace(' Limited.', ' Limited')
    stock_name = stock_name.replace(' Co.', ' Company').replace(' Co', ' Company').replace(' Company.', ' Company')
    stock_name = stock_name.replace(' Inc.', ' Inc').replace(' Inc', ' Incorporated').replace(' Incorporated.', ' Incorporated')
    stock_name = stock_name.replace('&', 'and')
    stock_name = stock_name.strip()  # remove leading/trailing whitespaces
    return stock_name

# Load stock symbols from CSV and clean names during mapping
stock_symbol_map = {}
company_names_list = []
try:
    with open('data/mapping_data/EQUITY_L.csv', mode='r', encoding='utf-8') as csvfile:
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            cleaned_name = clean_stock_name(row['NAME OF COMPANY'])
            stock_symbol_map[cleaned_name] = row['SYMBOL']
            company_names_list.append(cleaned_name)
except FileNotFoundError:
    print("Warning: EQUITY_L.csv not found. Stock symbols won't be mapped.")

# Function to get stock symbol
def get_stock_symbol(stock_name, stock_symbol_map, company_names_list):
    cleaned_stock_name = clean_stock_name(stock_name)

    # 1. Exact match
    if cleaned_stock_name in stock_symbol_map:
        return stock_symbol_map[cleaned_stock_name]

    # 2. Partial matching
    for company_name in company_names_list:
        if cleaned_stock_name.lower() in company_name.lower():
            return stock_symbol_map[company_name]

    # 3. Fuzzy matching
    best_match_symbol = None
    best_match_score = 0
    for company_name in company_names_list:
        score = fuzz.token_set_ratio(cleaned_stock_name, company_name)
        if score > best_match_score:
            best_match_score = score
            best_match_symbol = stock_symbol_map[company_name]

    if best_match_score > 90:  # Adjustable threshold
        return best_match_symbol

    return None  # Return None if no good match

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
stock_to_symbol = {}
total_portfolio_value = 0

for holding in holdings:
    scheme_id = holding['SchemeID']
    value = holding['Value']
    total_portfolio_value += value

    if scheme_id == 'N/A':
        # Direct stock holding
        stock_name = holding['Security']
        cleaned_name = clean_stock_name(stock_name)
        symbol = get_stock_symbol(stock_name, stock_symbol_map, company_names_list)
        stock_values[cleaned_name] += value
        if cleaned_name not in stock_to_sector:
            stock_to_sector[cleaned_name] = holding.get('Sector', 'N/A')
        if symbol and cleaned_name not in stock_to_symbol:
            stock_to_symbol[cleaned_name] = symbol
    else:
        # Mutual fund holding
        breakdown_file = scheme_id_to_file.get(scheme_id)
        if breakdown_file:
            with open(breakdown_file, 'r') as f:
                breakdown = json.load(f)
            for stock in breakdown:
                stock_name = stock['Stock']
                cleaned_name = clean_stock_name(stock_name)
                symbol = get_stock_symbol(stock_name, stock_symbol_map, company_names_list)
                percentage = stock['Percentage_of_Total_Holdings']
                effective_value = percentage * value
                stock_values[cleaned_name] += effective_value
                if cleaned_name not in stock_to_sector:
                    stock_to_sector[cleaned_name] = stock['Sector']
                if symbol and cleaned_name not in stock_to_symbol:
                    stock_to_symbol[cleaned_name] = symbol
        else:
            print(f"Warning: No breakdown file found for SchemeID {scheme_id}")

# Calculate total stock value after aggregation
total_stock_value = sum(stock_values.values())

# Build output with symbols
portfolio_stockbreakdown = [
    {
        'Stock': stock_name,
        'Symbol': stock_to_symbol.get(stock_name, 'N/A'),  # Add symbol, default to 'N/A' if not found
        'Sector': stock_to_sector.get(stock_name, 'N/A'),
        'Value': round(value, 2),
        'Percentage_of_Total_Holdings': round((value / total_stock_value) * 100, 4)
    }
    for stock_name, value in stock_values.items()
]

# Sort by percentage descending
portfolio_stockbreakdown.sort(key=lambda x: x['Percentage_of_Total_Holdings'], reverse=True)

# Save output
output_file = 'data/portfolio_data/portfolio_stockbreakdown.json'
with open(output_file, 'w') as f:
    json.dump(portfolio_stockbreakdown, f, indent=4)

# Debug output
print(f"Total Portfolio Value: {total_portfolio_value}")
print(f"Total Stock Value: {total_stock_value}")
print(f"Number of Stocks: {len(portfolio_stockbreakdown)}")
print(f"Portfolio breakdown saved to: {output_file}")