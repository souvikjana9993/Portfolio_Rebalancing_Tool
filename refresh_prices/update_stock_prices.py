import yfinance as yf
import json
import os
from datetime import datetime

def update_stock_prices(json_file_path):
    # Load existing data or use default
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as file:
            data = json.load(file)
            12
    # Add .NS to symbols and fetch current prices
    symbols = [f"{stock['Symbol']}.NS" for stock in data]
    try:
        # Get stock data from yfinance
        stock_data = yf.download(symbols, period="1d", interval="1d")
        
        # Update each stock with current price and add qty if not present
        for stock in data:
            symbol = f"{stock['Symbol']}.NS"
            try:
                # Get the most recent closing price
                current_price = stock_data['Close'][symbol].iloc[-1]
                
                # Add price field
                stock['Price'] = round(float(current_price), 2)
                
                # Add quantity field if not present (calculated from Value/Price)
                if 'Qty' not in stock:
                    stock['Qty'] = round(stock['Value'] / stock['Price'], 2)
                                
                # Update timestamp
                stock['Last_Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            except Exception as e:
                print(f"Error processing {symbol}: {str(e)}")
                stock['Price'] = None
                if 'Qty' not in stock:
                    stock['Qty'] = 0
                stock['Last_Updated'] = None  # Set date to None for N/A

        # Calculate total value for percentage calculation
        total_value = sum(stock['Value'] for stock in data if stock['Price'] is not None)
        
        # Update percentages
        for stock in data:
            if stock['Price'] is not None and total_value > 0:
                stock['Percentage_of_Total_Holdings'] = round((stock['Value'] / total_value) * 100, 4)
            else:
                stock['Percentage_of_Total_Holdings'] = 0.0

        # Save updated data to JSON file
        with open(json_file_path, 'w') as file:
            json.dump(data, file, indent=4)
            
        print(f"Stock prices updated successfully. File saved as {json_file_path}")
        return data

    except Exception as e:
        print(f"Error fetching stock data: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    updated_data = update_stock_prices('data/portfolio_data/portfolio_stockbreakdown.json')
    if updated_data:
        print("\nUpdated stock data:")
        for stock in updated_data:
            print(f"{stock['Stock']}:")
            print(f"  Price: {stock.get('Price')}")
            print(f"  Quantity: {stock.get('Qty')}")
            print(f"  Value: {stock['Value']}")
            print(f"  Percentage: {stock['Percentage_of_Total_Holdings']}%")
            print(f"  Last Updated: {stock.get('Last_Updated')}\n")