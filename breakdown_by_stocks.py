import json
import csv
from fuzzywuzzy import fuzz

# Portfolio data (modified to use symbols for direct stocks)
portfolio_data = {
    "MF": {
        "Nippon India Multi Cap Fund(G)-Direct Plan": {"Wt (%)": 11.38},
        "Parag Parikh Flexi Cap Fund(G)-Direct Plan": {"Wt (%)": 11.38},
        "Kotak Emerging Equity Fund(G)-Direct Plan": {"Wt (%)": 6.12},
        "DSP Small Cap Fund(G)-Direct Plan": {"Wt (%)": 6.12},
        "ICICI Pru Corp Bond Fund(G)-Direct Plan": {"Wt (%)": 0},
        "Mirae Asset Tax Saver Fund(G)-Direct Plan": {"Wt (%)": 0},
    },
    "Stock": {
        "RELIANCE": {"Wt (%)": 6},
        "BAJFINANCE": {"Wt (%)": 6},
        "KPITTECH": {"Wt (%)": 5},
        "SOLARINDS": {"Wt (%)": 5},
        "TATAPOWER": {"Wt (%)": 5},
        "KAYNES": {"Wt (%)": 5},
        "ZOMATO": {"Wt (%)": 5},
        "TEJASNET": {"Wt (%)": 4.5},
        "STARHEALTH": {"Wt (%)": 4},
        "POLYCAB": {"Wt (%)": 4},
        "LALPATHLAB": {"Wt (%)": 4},
        "VBL": {"Wt (%)": 4},
        "IDFCFIRSTB": {"Wt (%)": 4},
        "KALYANKJIL": {"Wt (%)": 3.5},
    }
}

# Load MF holding data from JSON files
def load_mf_holdings(filename):
    with open(filename, 'r') as f:
        return json.load(f)

mf_holding_files = {
    "Nippon India Multi Cap Fund(G)-Direct Plan": "data/cleaned_holding_data_nippon.json",
    "Parag Parikh Flexi Cap Fund(G)-Direct Plan": "data/cleaned_holding_data_pp_flexi.json",
    "Kotak Emerging Equity Fund(G)-Direct Plan": "data/cleaned_holding_data_kotak_emerging_eq.json",
    "DSP Small Cap Fund(G)-Direct Plan": "data/cleaned_holding_dsp_smallcap.json",
}

mf_holdings_data = {}
for mf_name, filename in mf_holding_files.items():
    mf_holdings_data[mf_name] = load_mf_holdings(filename)

# Function to clean stock names - added Co. and Co replacements
def clean_stock_name(stock_name):
    stock_name = stock_name.replace(' Ltd.', ' Limited').replace(' Ltd', ' Limited').replace(' Limited.', ' Limited')
    stock_name = stock_name.replace(' Co.', ' Company').replace(' Co', ' Company').replace(' Company.', ' Company')
    stock_name = stock_name.strip()  # remove leading/trailing whitespaces
    return stock_name

# Load stock symbols from CSV and clean names during mapping
stock_symbol_map = {}
company_names_list = [] # To use for fuzzy matching
with open('EQUITY_L.csv', mode='r', encoding='utf-8') as csvfile:
    csv_reader = csv.DictReader(csvfile)
    for row in csv_reader:
        cleaned_name = clean_stock_name(row['NAME OF COMPANY'])
        stock_symbol_map[cleaned_name] = row['SYMBOL']
        company_names_list.append(cleaned_name)

def get_stock_symbol(stock_name, stock_symbol_map, company_names_list):
    cleaned_stock_name = clean_stock_name(stock_name)

    # 1. Exact match
    if cleaned_stock_name in stock_symbol_map:
        return stock_symbol_map[cleaned_stock_name]

    # 2. Partial matching (check if cleaned_stock_name is a substring of any company name in EQUITY_L)
    for company_name in company_names_list:
        if cleaned_stock_name.lower() in company_name.lower(): # Case-insensitive partial match
            return stock_symbol_map[company_name]

    # 3. Fuzzy matching (if no exact or partial match)
    best_match_symbol = None
    best_match_score = 0
    for company_name in company_names_list:
        score = fuzz.token_set_ratio(cleaned_stock_name, company_name) # Using token_set_ratio for better accuracy
        if score > best_match_score:
            best_match_score = score
            best_match_symbol = stock_symbol_map[company_name]

    if best_match_score > 90: # Threshold for fuzzy match - adjust as needed
        return best_match_symbol

    return stock_name # If no good match, return original stock name as symbol (fallback)


stock_breakdown = {}

# Process direct stock holdings - use symbols now
for stock_symbol, data in portfolio_data["Stock"].items():
    stock_breakdown[stock_symbol] = {"Direct Holding Wt (%)": data["Wt (%)"], "MF Holding Wt (%)": 0, "Total Wt (%)": data["Wt (%)"], "actual_name": stock_symbol}

# Process MF holdings
for mf_name, mf_data in portfolio_data["MF"].items():
    mf_portfolio_weight_percent = mf_data["Wt (%)"]
    if mf_portfolio_weight_percent > 0:
        mf_portfolio_weight_decimal = mf_portfolio_weight_percent / 100.0  # MF weight in decimal
        holdings = mf_holdings_data[mf_name]
        for holding in holdings:
            stock_name = holding["Stock"]
            stock_symbol = get_stock_symbol(stock_name, stock_symbol_map, company_names_list) # Use matching logic to get symbol
            percentage_holding_in_mf = holding["Percentage_of_Total_Holdings"]

            # Calculate stock weight contribution from MF - multiply by MF weight
            stock_weight_from_mf = percentage_holding_in_mf * mf_portfolio_weight_decimal * 100 # Convert back to percentage

            if stock_symbol not in stock_breakdown: # Use symbol for lookup
                stock_breakdown[stock_symbol] = {"Direct Holding Wt (%)": 0, "MF Holding Wt (%)": 0, "Total Wt (%)": 0, "actual_name": stock_name} # Store actual name
            stock_breakdown[stock_symbol]["MF Holding Wt (%)"] += stock_weight_from_mf
            stock_breakdown[stock_symbol]["Total Wt (%)"] = stock_breakdown[stock_symbol]["Direct Holding Wt (%)"] + stock_breakdown[stock_symbol]["MF Holding Wt (%)"]

# Prepare data for JSON output - use symbols in final output
output_data = []
for stock_symbol, weights in stock_breakdown.items():
    if weights["Total Wt (%)"] > 0.01: # Show only stocks with meaningful weight
        output_data.append({
            "Stock Symbol": stock_symbol,
            "Direct Holding Weight (%)": round(weights["Direct Holding Wt (%)"], 2),
            "MF Holding Weight (%)": round(weights["MF Holding Wt (%)"], 2),
            "Total Weight (%)": round(weights["Total Wt (%)"], 2),
            "actual_name": weights["actual_name"] # Include actual name in output
        })

# Save JSON output to file
output_filename = "portfolio_breakdown.json"
with open(output_filename, 'w') as outfile:
    json.dump(output_data, outfile, indent=4)

print(f"JSON output saved to: {output_filename}")
print(json.dumps(output_data, indent=4))