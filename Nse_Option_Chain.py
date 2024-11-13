import json
import sys
import argparse
import pandas as pd
import numpy as np
import datetime
import pytz
import requests
import requests.cookies
from scipy.stats import norm
from scipy.optimize import minimize
import warnings
import argparse


warnings.filterwarnings("ignore")

pd.set_option('display.max_columns', None)  # Display all columns
pd.set_option('display.max_rows', None)     # Display all rows
pd.set_option('display.width', None)        # Disable line wrapping to allow a single line
pd.set_option('display.max_colwidth', None) # Display full column content without truncation


def black_scholes_price(S,K, T, r, sigma, option_type= "call"):
    d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type == 'call':
        option_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type == "put":
        option_price = K * np.exp(-r * T)  * norm.cdf(-d2) - S  * norm.cdf(-d1)
    else : 
        raise ValueError("Invalid option type. Use 'call' or 'put'")
    
    return option_price

def calculate_greeks(row):
    S = row['CE.underlyingValue'] # FUTPx / underlying contact value
    K = row['CE.strikePrice']
    T = row['TTE']
    r = 0
    market_price_call = row['CE.lastPrice']
    market_price_put = row['PE.lastPrice']
    
    objective_function_call  = (lambda sigma : (black_scholes_price(S,K, T, r, sigma, option_type= "call") - market_price_call) ** 2)
    objective_function_put = (lambda sigma : (black_scholes_price(S,K, T, r, sigma, option_type= "put") - market_price_call) ** 2)

    #intital guess for implide volatality
    initial_guess_sigma = 0.2

    result_call = minimize(objective_function_call, initial_guess_sigma, bounds=[(0,1)])
    implied_volatility_call = result_call.x[0]

    result_put = minimize(objective_function_put, initial_guess_sigma, bounds=[(0,1)])
    implied_volatility_put = result_put.x[0]

    #Calulate delta using the IV
    d1_call = (np.log(S / K) + (r + 0.5 * implied_volatility_call**2) * T) / (implied_volatility_call * np.sqrt(T))
    delta_call = norm.cdf(d1_call)

    d1_put = (np.log(S / K) + (r + 0.5 * implied_volatility_put**2) * T) / (implied_volatility_put * np.sqrt(T))
    delta_put = norm.cdf(d1_put) - 1

     # Round the Delta values to 2 decimal places
    delta_call = round(delta_call, 2)
    delta_put = round(delta_put, 2)

    return pd.Series(
        {
            'ImpliedVolatilityCall': implied_volatility_call,
            'DeltaCall': delta_call,
            'ImpliedVolatilityPut': implied_volatility_put,
            'DeltaPut': delta_put
        }
    )


def nse_option_chain(symbol, expiry):
    baseurl = "https://www.nseindia.com"
    date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date()
    if symbol.endswith("NIFTY"):
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=" + symbol
    elif symbol.endswith("INR" or "USD"):
        url = "https://www.nseindia.com/api/option-chain-currency?symbol=" + symbol
    else:
        url = "https://www.nseindia.com/api/option-chain-equities?symbol=" + symbol
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8,gu;q=0.7',
        'Connection': 'keep-alive',
        # 'Content-Length': '0',
        'Content-Type': 'application/json',
        # 'Cookie': 'ASP.NET_SessionId=vdmqtncuh30zzqmt5ue1par1; device-source=https://www.mcxindia.com/; device-referrer=https://www.google.com/; _gid=GA1.2.1970540842.1730985018; _ga=GA1.2.503645859.1725971174; _ga_8BQ43G0902=GS1.1.1730985017.3.1.1730985085.0.0.0; _gat_gtag_UA_121835541_1=1',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }
    session = requests.Session()
    request = session.get(baseurl, headers=headers, timeout=30)
    page = session.get(url, headers=headers, timeout=30)
    dictr = json.loads(page.text)

    df = pd.json_normalize(dictr["records"]['data'])
    df['expiryDate'] = pd.to_datetime(df['expiryDate'], errors='coerce')
    df = df.sort_values(by='expiryDate')


    if expiry == "week":
        if datetime.datetime.now(pytz.timezone('Asia/Kolkata')).time() > datetime.datetime.strptime("15:30", "%H:%M").time() and df['expiryDate'].dt.date.unique()[0] == datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date():
            # Choose the second unique expiry date
            df = df[df['expiryDate'] == df['expiryDate'].unique()[1]]
        else:
            # Choose the first unique expiry date
            df = df[df['expiryDate'] == df['expiryDate'].unique()[0]]

    elif expiry == "month":
        last_dates = df.groupby(df['expiryDate'].dt.to_period('M'))['expiryDate'].max()[0]
        # Filter data to keep only the rows with the last expiry date of each month
        df = df[df['expiryDate'] == last_dates]

    # Ensure expiryDate is a datetime object
    end_of_lasttrade_day = pd.to_datetime(df['expiryDate'].unique()[0]).replace(hour=15, minute=29, second=59, microsecond=999999)
    time_to_expiry = (pd.to_datetime(end_of_lasttrade_day, format="%d%b%y", errors="coerce")).tz_localize("Asia/Kolkata") - pd.Timestamp.now(tz="Asia/Kolkata")
    df['TTE'] = (time_to_expiry.days + time_to_expiry.seconds/(60*60*24)) / 265
    #calculate greeks
    df[['ImpliedVolatilityCall','DeltaCall','ImpliedVolatilityPut','DeltaPut']] = df.apply(calculate_greeks, axis =1)

    df = df[['ImpliedVolatilityPut', 'DeltaPut','PE.openInterest','PE.pChange','PE.lastPrice','strikePrice','CE.lastPrice','CE.pChange','CE.openInterest','DeltaCall','ImpliedVolatilityCall']]
    df = df.sort_values(by='strikePrice')
    print(df)

def main():
    parser = argparse.ArgumentParser(description="Get Live option chain for NSE with greeks", 
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('symbol', choices=['NIFTY', 'USDINR', 'SBIN'], help='Which symbol?')
    parser.add_argument('expiry', choices=['week', 'month'], nargs='?', help='Please provide expiry')
    args = parser.parse_args()
    nse_option_chain(args.symbol, args.expiry)

if __name__ == "__main__":
    main()

