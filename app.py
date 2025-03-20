import streamlit as st
import pandas as pd
import yfinance as yf
import math
import json
import time
from datetime import datetime

# Set wide layout
st.set_page_config(layout="wide")

# Stock name mappings (for some stocks)
name_mapping_inv = {
    "Bajaj Finance": "BAJFINANCE", "Reliance Industries": "RELIANCE", "KPIT Technologies": "KPITTECH",
    "PI Industries": "PIIND", "Tata Power Company": "TATAPOWER", "Kaynes Technology India": "KAYNES",
    "Zomato": "ZOMATO", "Tejas Networks": "TEJASNET", "Star Health and Allied Insurance Company": "STARHEALTH",
    "IDFC First Bank": "IDFCFIRSTB", "Polycab India": "POLYCAB", "Varun Beverages": "VBL",
    "Dr. Lal PathLabs": "LALPATHLAB", "Kalyan Jewellers India": "KALYANKJIL"
}

# Create a mapping for yfinance tickers using the above values.
yfinance_symbols = {k: f"{k}.NS" for k in name_mapping_inv.values()}

# Aggregate holdings from multiple CSVs
def aggregate_holdings(files):
    dfs = [pd.read_csv(file) for file in files]
    combined_df = pd.concat(dfs, ignore_index=True).rename(columns={'Qty.': 'Qty', 'Cur. val': 'Cur_val'})
    return combined_df.groupby('Instrument').agg({'Qty': 'sum', 'LTP': 'first', 'Cur_val': 'sum'}).reset_index()

# Fetch latest prices using yfinance; use fallback if the stock isn’t in yfinance_symbols.
def fetch_latest_prices(stocks):
    latest_prices = {}
    for stock in stocks:
        # Use predefined ticker if available; otherwise assume stock + ".NS"
        ticker_symbol = yfinance_symbols.get(stock, f"{stock}.NS")
        try:
            ticker = yf.Ticker(ticker_symbol)
            quote = ticker.history(period="1d", interval="1m")
            # If minute data is available, take the last close price; otherwise use market price info
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
    
    # Include all target stocks, even if not present in holdings_df
    if not holdings_df.empty:
        existing_holdings = holdings_df[holdings_df['Instrument'].isin(target_stocks)].copy()
    else:
        existing_holdings = pd.DataFrame()
    existing_stocks = set(existing_holdings['Instrument'].tolist()) if not existing_holdings.empty else set()
    missing_stocks = [stock for stock in target_stocks if stock not in existing_stocks]
    
    # Create entries for missing stocks with 0 quantity and a fetched LTP (or 0 if not available)
    new_stock_entries = pd.DataFrame([
        {"Instrument": stock, "Qty": 0, "LTP": latest_prices.get(stock, 0), "Cur_val": 0} 
        for stock in missing_stocks
    ])
    
    filtered_holdings = pd.concat([existing_holdings, new_stock_entries], ignore_index=True)

    # Calculate current value for each stock using the latest price (fallback to LTP)
    filtered_holdings['Current Value'] = filtered_holdings.apply(
        lambda row: row['Qty'] * latest_prices.get(row['Instrument'], row['LTP']), axis=1)
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
            shares = updated_qty - original_qty
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
            shares = original_qty - updated_qty
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
    uploaded_files = st.file_uploader("Upload CSV Files", accept_multiple_files=True, type="csv", help="Upload your portfolio CSV files")

    default_ratios = {
        "BAJFINANCE": 6, "RELIANCE": 6, "KPITTECH": 5, "SOLARINDS": 5, "TATAPOWER": 5,
        "KAYNES": 5, "ZOMATO": 5, "TEJASNET": 4.5, "STARHEALTH": 4, "IDFCFIRSTB": 4,
        "POLYCAB": 4, "VBL": 4, "LALPATHLAB": 4, "KALYANKJIL": 3.5
    }
    st.subheader("Target Ratios (JSON)")
    ratio_input = st.text_area("Edit ratios", json.dumps(default_ratios, indent=2), height=200)
    try:
        user_target_ratios = json.loads(ratio_input) if ratio_input else default_ratios
    except json.JSONDecodeError:
        st.error("Invalid JSON format!")
        user_target_ratios = default_ratios

    extra_funds = st.number_input("Extra Funds (₹)", min_value=0.0, value=0.0, step=1000.0)
    allocation_margin_percent = st.slider("Allocation Margin (%)", 0.0, 10.0, 2.0, 0.5)

    if st.button("Calculate", key="calc_button"):
        if not uploaded_files:
            st.warning("Please upload CSV files to proceed.")
        else:
            holdings_df = aggregate_holdings(uploaded_files)
            holdings_df['Current Value'] = holdings_df['Qty'] * holdings_df['LTP']
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
