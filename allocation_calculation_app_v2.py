import streamlit as st
import pandas as pd
import yfinance as yf
import math
import json
import time
from datetime import datetime
import os

# Set wide layout
st.set_page_config(layout="wide")

# Stock name mappings
name_mapping_inv = {
    "Bajaj Finance": "BAJFINANCE", "Reliance Industries": "RELIANCE", "KPIT Technologies": "KPITTECH",
    "PI Industries": "PIIND", "Tata Power Company": "TATAPOWER", "Kaynes Technology India": "KAYNES",
    "Zomato": "ZOMATO", "Tejas Networks": "TEJASNET", "Star Health and Allied Insurance Company": "STARHEALTH",
    "IDFC First Bank": "IDFCFIRSTB", "Polycab India": "POLYCAB", "Varun Beverages": "VBL",
    "Dr. Lal PathLabs": "LALPATHLAB", "Kalyan Jewellers India": "KALYANKJIL",
    "HDFC Bank Limited": "HDFCBANK", "ICICI Bank Limited": "ICICIBANK", "Axis Bank Limited": "AXISBANK"
}

# Create a mapping for yfinance tickers
yfinance_symbols = {k: f"{k}.NS" for k in name_mapping_inv.values()}

# Process JSON holdings
def process_json_holdings(file):
    data = json.load(file)
    df = pd.DataFrame(data)
    # Rename columns to match expected format
    df = df.rename(columns={
        "Symbol": "Instrument",
        "Value": "Cur_val"
    })
    # Add Qty and LTP columns (we'll calculate LTP from Value if Qty isn't provided)
    if 'Qty' not in df.columns:
        df['Qty'] = 0  # Initial quantity can be 0 since we'll use current value
    df['LTP'] = df['Cur_val']  # Will be updated with real prices
    return df.groupby('Instrument').agg({'Qty': 'sum', 'LTP': 'first', 'Cur_val': 'sum'}).reset_index()

# Fetch latest prices using yfinance
def fetch_latest_prices(stocks):
    latest_prices = {}
    for stock in stocks:
        ticker_symbol = yfinance_symbols.get(stock, f"{stock}.NS")
        try:
            ticker = yf.Ticker(ticker_symbol)
            quote = ticker.history(period="1d", interval="1m")
            latest_prices[stock] = quote['Close'].iloc[-1] if not quote.empty else ticker.info.get('regularMarketPrice', 0)
            time.sleep(1)
        except Exception as e:
            st.error(f"Error fetching price for {stock}: {e}")
            latest_prices[stock] = 0
    return latest_prices

# Calculate ideal allocation percentages
def calculate_ideal_allocations(target_ratios):
    total_ratio = sum(target_ratios.values())
    return {stock: round(ratio / total_ratio * 100, 2) if total_ratio > 0 else 0 for stock, ratio in target_ratios.items()}

# Calculate rebalancing actions
def calculate_rebalancing(holdings_df, target_ratios, extra_funds=0, allocation_margin_percent=2.0):
    if not target_ratios:
        return [], {"status": "No Action", "amount": 0, "message": "No target ratios provided"}, holdings_df, [], {}

    target_stocks = list(target_ratios.keys())
    latest_prices = fetch_latest_prices(target_stocks)

    # Include all target stocks
    if not holdings_df.empty:
        existing_holdings = holdings_df[holdings_df['Instrument'].isin(target_stocks)].copy()
    else:
        existing_holdings = pd.DataFrame()
    existing_stocks = set(existing_holdings['Instrument'].tolist()) if not existing_holdings.empty else set()
    missing_stocks = [stock for stock in target_stocks if stock not in existing_stocks]

    new_stock_entries = pd.DataFrame([
        {"Instrument": stock, "Qty": 0, "LTP": latest_prices.get(stock, 0), "Cur_val": 0}
        for stock in missing_stocks
    ])

    filtered_holdings = pd.concat([existing_holdings, new_stock_entries], ignore_index=True)

    # Update current value with latest prices
    filtered_holdings['Current Value'] = filtered_holdings.apply(
        lambda row: row['Qty'] * latest_prices.get(row['Instrument'], row['LTP']) if row['Qty'] > 0 else row['Cur_val'],
        axis=1)
    sell_proceeds = filtered_holdings['Current Value'].sum()
    total_available_funds = sell_proceeds + extra_funds

    total_ratio = sum(target_ratios.values())
    if total_ratio == 0:
        return [], {"status": "No Action", "amount": 0, "message": "Sum of target ratios is zero"}, filtered_holdings, [], {}

    target_values = {stock: (target_ratios[stock] / total_ratio) * total_available_funds for stock in target_stocks}
    ideal_allocations_percent = calculate_ideal_allocations(target_ratios)

    updated_quantities = {
        stock: math.floor(target_values[stock] / latest_prices.get(stock, 0))
        if latest_prices.get(stock, 0) > 0 else 0
        for stock in target_stocks
    }
    initial_cost = sum(updated_quantities[stock] * latest_prices.get(stock, 0) for stock in target_stocks)
    available_funds = total_available_funds - initial_cost

    min_price = min((price for price in latest_prices.values() if price > 0), default=float('inf'))
    while available_funds > min_price:
        current_portfolio_value = sum(updated_quantities[stock] * latest_prices.get(stock, 0) for stock in target_stocks)
        total_value = current_portfolio_value + available_funds
        candidates = [
            (stock, ideal_allocations_percent[stock] - (updated_quantities[stock] * latest_prices.get(stock, 0) / total_value * 100 if total_value > 0 else 0), latest_prices[stock])
            for stock in target_stocks if latest_prices.get(stock, 0) <= available_funds and latest_prices.get(stock, 0) > 0
        ]
        if not candidates:
            break
        stock_to_buy, _, ltp = max(candidates, key=lambda x: x[1])
        updated_quantities[stock_to_buy] += 1
        available_funds -= ltp

    rebalancing_actions = []
    for stock in target_stocks:
        original_qty = filtered_holdings.loc[filtered_holdings['Instrument'] == stock, 'Qty'].iloc[0] if stock in filtered_holdings['Instrument'].values else 0
        updated_qty = updated_quantities[stock]
        stock_price = latest_prices.get(stock, 0)
        if updated_qty > original_qty:
            shares = math.floor(updated_qty - original_qty) # floor for buy
            if shares > 0: # only add action if shares > 0
                rebalancing_actions.append({
                    "Instrument": stock,
                    "Original Qty": original_qty,
                    "Action": "Buy",
                    "Shares": shares,
                    "Value Bought/Sold": shares * stock_price,
                    "Stock Price": stock_price,
                    "New Qty": updated_qty
                })
        elif updated_qty < original_qty:
            shares = math.floor(original_qty - updated_qty) # floor for sell
            if shares > 0: # only add action if shares > 0
                rebalancing_actions.append({
                    "Instrument": stock,
                    "Original Qty": original_qty,
                    "Action": "Sell",
                    "Shares": shares,
                    "Value Bought/Sold": shares * stock_price,
                    "Stock Price": stock_price,
                    "New Qty": updated_qty
                })

    updated_holdings_df = pd.DataFrame([
        {"Instrument": stock, "Qty": qty, "LTP": latest_prices.get(stock, 0), "Current Value": qty * latest_prices.get(stock, 0)}
        for stock, qty in updated_quantities.items()
    ])
    new_portfolio_value = updated_holdings_df['Current Value'].sum()
    updated_holdings_df['Allocation %'] = (
        updated_holdings_df['Current Value'] / new_portfolio_value * 100
    ).round(2) if new_portfolio_value > 0 else 0

    non_target_holdings = holdings_df[~holdings_df['Instrument'].isin(target_stocks)].copy() if not holdings_df.empty else pd.DataFrame()
    if not non_target_holdings.empty:
        non_target_holdings['Current Value'] = non_target_holdings['Qty'] * non_target_holdings['Instrument'].map(latest_prices)
        non_target_holdings['Allocation %'] = (
            non_target_holdings['Current Value'] / (new_portfolio_value + non_target_holdings['Current Value'].sum()) * 100
        ).round(2) if (new_portfolio_value + non_target_holdings['Current Value'].sum()) > 0 else 0
        updated_holdings_df = pd.concat([updated_holdings_df, non_target_holdings], ignore_index=True)

    funds_display = {
        "status": "Excess Funds",
        "amount": available_funds,
        "message": f"₹{available_funds:.2f} remains unused after rebalancing."
    }
    tentative_holdings = [
        {
            "Stock": name_mapping_inv.get(row['Instrument'], row['Instrument']),
            "Qty": row['Qty'],
            "LTP": row['LTP'],
            "Current Value (Qty × LTP)": row['Current Value'],
            "Ideal Allocation %": ideal_allocations_percent.get(row['Instrument'], 0),
            "Actual Allocation %": row['Allocation %']
        }
        for _, row in updated_holdings_df.iterrows()
    ]

    return (
        sorted(rebalancing_actions, key=lambda x: x["Instrument"]),
        funds_display,
        updated_holdings_df,
        sorted(tentative_holdings, key=lambda x: x["Stock"]),
        ideal_allocations_percent
    )

# Streamlit UI
st.title("📈 Portfolio Rebalancing Tool")
st.markdown("Optimize your portfolio based on target ratios with real-time prices from Yahoo Finance.")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Input Data")
    uploaded_file = st.file_uploader("Upload Holdings JSON File", type="json", help="Upload your portfolio holdings JSON file")

    st.subheader("Target Ratios")
    target_ratio_file = "data/mapping_data/asset_allocation.json"
    
    user_target_ratios = {} # Initialize as empty dictionary
    try:
        with open(target_ratio_file, 'r') as f:
            ratios_list = json.load(f) # Load as list
        st.success(f"Target ratios loaded from `{target_ratio_file}`")

        for item in ratios_list: # Iterate through the list
            stock_symbol = item.get("Stock Symbol") # Safely get stock symbol
            weight = item.get("Total Weight (%)") # Safely get weight, or use "Total Weight (%)" if needed
            if stock_symbol and weight is not None: # Check if both are present
                user_target_ratios[stock_symbol] = float(weight) # Convert weight to float and add to dict
            else:
                st.warning(f"Missing 'Stock Symbol' or 'Direct Holding Weight (%)' in item: {item}. Skipping.")


        # Display ratios for review (optional)
        # st.json(user_target_ratios)
    except FileNotFoundError:
        st.error(f"Target ratio file not found at `{target_ratio_file}`. Please create it or check the path.")
        user_target_ratios = {}
    except json.JSONDecodeError:
        st.error(f"Error decoding JSON from `{target_ratio_file}`. Please ensure it's valid JSON.")
        user_target_ratios = {}


    extra_funds = st.number_input("Extra Funds (₹)", min_value=0.0, value=0.0, step=1000.0)
    allocation_margin_percent = st.slider("Allocation Margin (%)", 0.0, 10.0, 2.0, 0.5)

    if st.button("Calculate", key="calc_button"):
        if not uploaded_file:
            st.warning("Please upload a holdings JSON file to proceed.")
        elif not user_target_ratios:
            st.warning("Target ratios are not loaded correctly. Please check the file and path.")
        else:
            holdings_df = process_json_holdings(uploaded_file)
            holdings_df['Current Value'] = holdings_df['Cur_val']  # Use value from JSON initially
            # holdings_df['Current Value'] = holdings_df['Qty'] * holdings_df['LTP']
            total_value = holdings_df['Current Value'].sum()
            holdings_df['Allocation %'] = (
                holdings_df['Current Value'] / total_value * 100
            ).round(2) if total_value > 0 else 0

with col2:
    if 'holdings_df' in locals():
        st.subheader("Initial Holdings")
        st.dataframe(
            holdings_df.style.format({
                "LTP": "₹{:.2f}", "Cur_val": "₹{:.2f}",
                "Current Value": "₹{:.2f}", "Allocation %": "{:.2f}%"
            }),
            use_container_width=True
        )

        rebalancing_actions, funds_info, _, tentative_holdings, _ = calculate_rebalancing(
            holdings_df, user_target_ratios, extra_funds, allocation_margin_percent
        )

        if rebalancing_actions:
            st.subheader("Rebalancing Actions")
            actions_df = pd.DataFrame(rebalancing_actions)
            st.dataframe(
                actions_df.style.format({
                    "Value Bought/Sold": "₹{:.2f}",
                    "Stock Price": "₹{:.2f}"
                }),
                use_container_width=True
            )

        st.subheader(funds_info["status"])
        st.write(f"{funds_info['message']} (Prices as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} PST)")

        if tentative_holdings:
            st.subheader("Updated Holdings")
            tentative_df = pd.DataFrame(tentative_holdings)
            st.dataframe(
                tentative_df.style.format({
                    "LTP": "₹{:.2f}",
                    "Current Value (Qty × LTP)": "₹{:.2f}",
                    "Ideal Allocation %": "{:.2f}%",
                    "Actual Allocation %": "{:.2f}%"
                }),
                use_container_width=True
            )