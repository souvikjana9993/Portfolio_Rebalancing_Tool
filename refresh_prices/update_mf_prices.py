from mftool import Mftool
import json

# List of known stocks to exclude from MF updates
stocks = {"CARTRADE", "FSC", "OLAELECTRIC"}

# Initialize Mftool
mf = Mftool()

# Load scheme mapping from JSON file
try:
    with open('data/mapping_data/schema_links_mf.json', 'r') as f:
        scheme_mapping = json.load(f)
except FileNotFoundError:
    print("Error: schema_mapping.json file not found!")
    scheme_mapping = {}
except json.JSONDecodeError:
    print("Error: Invalid JSON format in schema_mapping.json!")
    scheme_mapping = {}

# Load portfolio from the previous output file
try:
    with open('data/portfolio_data/updated_portfolio.json', 'r') as f:
        portfolio = json.load(f)
except FileNotFoundError:
    print("Error: updated_portfolio.json file not found!")
    portfolio = {"holdings": []}
except json.JSONDecodeError:
    print("Error: Invalid JSON format in updated_portfolio.json!")
    portfolio = {"holdings": []}

def update_mf_values(portfolio_data):
    combined_holdings = {}
    temp_holdings = []
    all_nav_available = True
    
    # First pass: Combine quantities and values for the same SchemeID
    for holding in portfolio_data["holdings"]:
        security = holding["Security"]
        scheme_id = scheme_mapping.get(security, "N/A")
        
        if scheme_id in combined_holdings:
            combined_holdings[scheme_id]["Qty"] += holding["Qty"]
            combined_holdings[scheme_id]["Value"] += holding["Value"]
        else:
            combined_holdings[scheme_id] = holding.copy()
            combined_holdings[scheme_id]["SchemeID"] = scheme_id
    
    # Second pass: Process all holdings and check if we have all NAV data
    for scheme_id, holding in combined_holdings.items():
        security = holding["Security"]
        
        # Handle stocks
        if security in stocks:
            updated_holding = holding.copy()
            updated_holding["NAV"] = 0.0
            temp_holdings.append(updated_holding)
            continue
            
        # Handle mutual funds
        if scheme_id != "N/A":
            try:
                nav_data = mf.get_scheme_quote(scheme_id)
                scheme_name = mf.get_scheme_details(scheme_id).get("scheme_name", "Unknown")
                
                if nav_data and 'nav' in nav_data:
                    latest_nav = float(nav_data['nav'])
                    new_value = latest_nav * holding["Qty"]
                    updated_holding = holding.copy()
                    updated_holding["Value"] = round(new_value, 2)
                    updated_holding["NAV"] = round(latest_nav, 2)
                    updated_holding["SchemeName"] = scheme_name
                    temp_holdings.append(updated_holding)
                    print(f"Updated {security}: Qty = {holding['Qty']:.3f}, NAV = {latest_nav:.2f}, New Value = {new_value:.2f}, SchemeID = {scheme_id}, SchemeName = {scheme_name}")
                else:
                    print(f"No NAV data available for {security}")
                    all_nav_available = False
                    updated_holding = holding.copy()
                    updated_holding["NAV"] = 0.0
                    updated_holding["SchemeName"] = "Unknown"
                    temp_holdings.append(updated_holding)
            except Exception as e:
                print(f"Error updating {security}: {str(e)}")
                all_nav_available = False
                updated_holding = holding.copy()
                updated_holding["NAV"] = 0.0
                updated_holding["SchemeName"] = "Unknown"
                temp_holdings.append(updated_holding)
        else:
            # Handle N/A cases - these are allowed to proceed
            print(f"No scheme mapping found for {security}")
            updated_holding = holding.copy()
            updated_holding["NAV"] = 0.0
            updated_holding["SchemeName"] = "Unknown"
            temp_holdings.append(updated_holding)
    
    # Only return updated data if all NAVs were successfully retrieved (except N/A cases)
    if all_nav_available:
        return {"holdings": temp_holdings}
    else:
        print("Warning: Not all NAV data was retrieved successfully. Keeping original portfolio.")
        return portfolio_data

# Update the portfolio
updated_portfolio = update_mf_values(portfolio)

# Print the updated portfolio
print("\nUpdated Portfolio:")
print(json.dumps(updated_portfolio, indent=4))

# Save updated portfolio to file only if it contains new data
if updated_portfolio != portfolio:
    try:
        with open('data/portfolio_data/updated_portfolio.json', 'w') as f:
            json.dump(updated_portfolio, f, indent=4)
        print("Portfolio successfully updated and saved.")
    except Exception as e:
        print(f"Error saving updated portfolio: {str(e)}")
else:
    print("Portfolio not updated due to incomplete NAV data.")