import json
import re,os
from firecrawl import FirecrawlApp
from dotenv import load_dotenv
load_dotenv()


def clean_holding_data(markdown_output):
    """
    Cleans and transforms the markdown output of mutual fund holding data into a list of dictionaries.

    Args:
        markdown_output: The markdown string containing the holding data table.

    Returns:
        A list of dictionaries, where each dictionary represents a row of the cleaned holding data.
    """
    lines = markdown_output.splitlines()
    holding_data_started = False
    holding_data = []
    headers = []

    for line in lines:
        line = line.strip()
        if "## Complete equity Portfolio" in line:
            holding_data_started = True
            continue
        if holding_data_started:
            if "Help me understand this table" in line:
                continue
            if line.startswith("| :--"): # Skip separator line
                continue
            if line.startswith("| Stock Invested in"): # Header line
                headers = [header.strip() for header in line.strip('|').split('|')]
                continue
            if line.startswith("| ["): # Data Row - check if it starts with a stock link to ensure it's a data row and not just empty table
                values = [value.strip() for value in line.strip('|').split('|')]
                if len(headers) == len(values): # Ensure header and value length match
                    row_data = {}
                    for i in range(len(headers)):
                        row_data[headers[i]] = values[i]
                    holding_data.append(row_data)
            elif line.startswith("| No group"): # Skip "No group" line
                continue
            elif line.startswith("| -"): # Handle rows starting with '-'
                values = [value.strip() for value in line.strip('|').split('|')]
                if len(headers) == len(values): # Ensure header and value length match
                    row_data = {}
                    for i in range(len(headers)):
                        row_data[headers[i]] = values[i]
                    holding_data.append(row_data)
            elif line.startswith("| "): # Handle other data rows - generic case
                 values = [value.strip() for value in line.strip('|').split('|')]
                 if len(headers) == len(values): # Ensure header and value length match
                    row_data = {}
                    for i in range(len(headers)):
                        row_data[headers[i]] = values[i]
                    holding_data.append(row_data)
            elif not line: # Stop after empty line after table (if any)
                if holding_data: # Only stop if we have already collected data, to avoid stopping prematurely
                    holding_data_started = False

    cleaned_data = []
    for row in holding_data:
        cleaned_row = {}
        for key, value in row.items():
            if key == "Stock Invested in":
                # Extract stock name from markdown link
                match = re.search(r'\[(.*?)\]', value)
                stock_name = match.group(1) if match else value
                cleaned_row["Stock"] = stock_name
            elif key == "Sector":
                cleaned_row["Sector"] = value
            elif key == "Value(Mn)":
                cleaned_row["Value_Mn"] = float(value) if value != '-' else None # Convert to float
            elif key == "% of Total Holdings":
                cleaned_row["Percentage_of_Total_Holdings"] = float(value.replace('%', '')) / 100 if value != '-' else None # Convert to float
            elif key == "1M Change":
                cleaned_row["One_Month_Change_Percentage"] = float(value.replace('%', '')) / 100 if value != '-' else None # Convert to float
            elif key == "1Y Highest Holding":
                match = re.search(r'([\d.]+)%\s*\((.*?)\)', value) # Extract percentage and date info
                if match:
                    cleaned_row["One_Year_Highest_Holding"] = {
                        "percentage": float(match.group(1)) / 100,
                        "month_year": match.group(2)
                    }
                else:
                    cleaned_row["One_Year_Highest_Holding"] = None if value == '-' else value # Keep as string if no percentage and date format, or None if '-'
            elif key == "1Y Lowest Holding":
                match = re.search(r'([\d.]+)%\s*\((.*?)\)', value) # Extract percentage and date info
                if match:
                    cleaned_row["One_Year_Lowest_Holding"] = {
                        "percentage": float(match.group(1)) / 100,
                        "month_year": match.group(2)
                    }
                else:
                    cleaned_row["One_Year_Lowest_Holding"] = None if value == '-' else value # Keep as string if no percentage and date format, or None if '-'
            elif key == "Quantity":
                cleaned_row["Quantity"] = value if value != '-' else None # Keep as string
            elif key == "1M Change in Qty":
                cleaned_row["One_Month_Quantity_Change"] = value if value != '-' else None # Keep as string
            else:
                cleaned_row[key] = value # For any other columns if present

        cleaned_data.append(cleaned_row)
    return cleaned_data

# Main code
app = FirecrawlApp(api_key=os.getenv('FIRECRAWL_API_KEY'))

response = app.scrape_url(url='https://www.moneycontrol.com/mutual-funds/dsp-small-cap-fund-direct-plan/portfolio-holdings/MDS584', params={
	'formats': [ 'markdown' ],
})

markdown_output = response['markdown']

cleaned_holding_data = clean_holding_data(markdown_output)

with open('cleaned_holding_dsp_smallcap.json', 'w') as f:
    json.dump(cleaned_holding_data, f, indent=4)