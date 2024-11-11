import sys
import argparse
import pandas as pd
import numpy as np
import datetime
import requests
from scipy.stats import norm
from scipy.optimize import minimize
import warnings
import argparse

warnings.filterwarnings("ignore")

pd.set_option('display.max_columns', None)  # Display all columns
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
    S = row['UnderlineValue_CE'] # FUTPx / underlying contact value
    K = row['StrikePrice']
    T = row['TTE']
    r = 0
    market_price_call = row['LTP_CE']
    market_price_put = row['LTP_PE']
    
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



def get_data():
    cookies = {
        'ASP.NET_SessionId': 'vdmqtncuh30zzqmt5ue1par1',
        'device-source': 'https://www.mcxindia.com/',
        'device-referrer': 'https://www.google.com/',
        '_gid': 'GA1.2.1970540842.1730985018',
        '_ga': 'GA1.2.503645859.1725971174',
        '_ga_8BQ43G0902': 'GS1.1.1730985017.3.1.1730985085.0.0.0',
        '_gat_gtag_UA_121835541_1': '1',
    }

    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8,gu;q=0.7',
        'Connection': 'keep-alive',
        # 'Content-Length': '0',
        'Content-Type': 'application/json',
        # 'Cookie': 'ASP.NET_SessionId=vdmqtncuh30zzqmt5ue1par1; device-source=https://www.mcxindia.com/; device-referrer=https://www.google.com/; _gid=GA1.2.1970540842.1730985018; _ga=GA1.2.503645859.1725971174; _ga_8BQ43G0902=GS1.1.1730985017.3.1.1730985085.0.0.0; _gat_gtag_UA_121835541_1=1',
        'DNT': '1',
        'Origin': 'https://www.mcxindia.com',
        'Referer': 'https://www.mcxindia.com/market-data/market-watch',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    response = requests.post('https://www.mcxindia.com/backpage.aspx/GetMarketWatch', cookies=cookies, headers=headers)
    market_data = response.json()
    df = pd.json_normalize(market_data["d"]["Data"])
    df['ExpiryDate'] = pd.to_datetime(df["ExpiryDate"])
    df['LTT'] = pd.to_datetime(df['LTT'].str.extract(r'(\d+)')[0].astype(float) / 1000, unit='s')
    return df
   

def Future():
    df = get_data()
    Fut_df = df.loc[(df.InstrumentName == "FUTCOM")] #['FUTCOM' 'OPTFUT' 'FUTIDX']
    month_code = {"Jan" : "F", "Feb" : "G", "Mar" : "H", "Apr" : "J", "May" : "K", "Jun" : "M", "Jul" : "N", "Aug" : "Q", "Sep" : "U", "Oct" : "V", "Nov" : "X", "Dec" : "Z"}
    Fut_df['Tiker'] = Fut_df["Symbol"] + Fut_df['ExpiryDate'].dt.strftime("%b").map(month_code) + Fut_df['ExpiryDate'].dt.strftime('%y').str[-1]
    Fut_df = Fut_df[[
        'Tiker',
        'ExpiryDate',
        'Open',
        'Low',
        'Volume',
        'LTT','AbsoluteChange', 'PercentChange',
        'NotionalValue', 'Unit'
    ]]
    return Fut_df

def Options(Symbol):
    df = get_data()
    Opt_df = df.loc[(df.InstrumentName == "OPTFUT")]
    Opt_df = df.loc[(df.Symbol == Symbol)]
    Opt_df = Opt_df.sort_values(by='ExpiryDate')
    Opt_df = Opt_df.loc[(Opt_df.ExpiryDate == Opt_df['ExpiryDate'].unique()[0])]
    CE_data = Opt_df.loc[(Opt_df.OptionType == "CE")]
    PE_data = Opt_df.loc[(Opt_df.OptionType == "PE")]
    merged_df = pd.merge(CE_data, PE_data, on='StrikePrice', suffixes= ('_CE','_PE'))
    #Filter current exp data only
    #merged_df = merged_df.loc[(merged_df.ExpiryDate_CE == merged_df['ExpiryDate_CE'].unique()[0])]

    #calculate time to expiry for product
    end_of_lasttrade_day = merged_df['ExpiryDate_CE'].unique()[0].replace(hour = 23, minute = 59, second=59, microsecond=999999)
    time_to_expiry = (pd.to_datetime(end_of_lasttrade_day, format="%d%b%y", errors="coerce")).tz_localize("Asia/Kolkata") - pd.Timestamp.now(tz="Asia/Kolkata")

    merged_df['TTE'] = (time_to_expiry.days + time_to_expiry.seconds/(60*60*24)) / 265

    #calculate greeks
    merged_df[['ImpliedVolatilityCall','DeltaCall','ImpliedVolatilityPut','DeltaPut']] = merged_df.apply(calculate_greeks, axis =1)

    # ['__type_CE', 'Symbol_CE', 'ProductCode_CE', 'ExpiryDate_CE', 'Unit_CE','Open_CE', 'Low_CE', 'LTP_CE', 'High_CE', 'PreviousClose_CE',
    # 'AbsoluteChange_CE', 'PercentChange_CE', 'Volume_CE', 'LTT_CE','BuyQuantity_CE', 'SellQuantity_CE', 'OpenInterest_CE','ValueInLacs_CE', 'BuyPrice_CE', 'SellPrice_CE', 'InstrumentName_CE',
    # 'StrikePrice', 'OptionType_CE', 'PremiumValue_CE', 'NotionalValue_CE','UnderlineValue_CE', 'UnderlineContract_CE', '__type_PE', 'Symbol_PE','ProductCode_PE', 'ExpiryDate_PE', 'Unit_PE', 'Open_PE', 'Low_PE',
    # 'LTP_PE', 'High_PE', 'PreviousClose_PE', 'AbsoluteChange_PE','PercentChange_PE', 'Volume_PE', 'LTT_PE', 'BuyQuantity_PE','SellQuantity_PE', 'OpenInterest_PE', 'ValueInLacs_PE', 'BuyPrice_PE',
    # 'SellPrice_PE', 'InstrumentName_PE', 'OptionType_PE', 'PremiumValue_PE','NotionalValue_PE', 'UnderlineValue_PE', 'UnderlineContract_PE', 'TTE','ImpliedVolatilityCall', 'DeltaCall', 'ImpliedVolatilityPut','DeltaPut']
    merged_df = merged_df[['ImpliedVolatilityCall', 'DeltaCall','Open_CE', 'Low_CE', 'Volume_CE', 'OpenInterest_CE', 
                       'NotionalValue_CE', 'PremiumValue_CE', 'StrikePrice',
                       'Open_PE', 'Low_PE', 'Volume_PE', 'OpenInterest_PE', 
                       'NotionalValue_PE', 'PremiumValue_PE','DeltaPut','ImpliedVolatilityPut']]

    merged_df = merged_df.sort_values(by='StrikePrice')
    return merged_df

def MCX_Live_Data(segment, symbol):
    if segment == 'FUT':
        print(Future())
    elif segment == 'OPT':
        print(Options(symbol))
    else:
        print("Invalid Segment")

if __name__ == "__main__":
    parser = argparse.ArgumentParser( description= "Get Live data for MCX Futures and Options with greeks", formatter_class= argparse.ArgumentDefaultsHelpFormatter,)
    parser.add_argument('segment', choices=['FUT', 'OPT'], help='Which derivative?')
    parser.add_argument('symbol', nargs='?', help='Please provide ticker in uppercase')
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python MCX_Live_Data.py <segment> [<symbol>]")
    else:
        segment = sys.argv[1]  # Get the segment from command line argument
        symbol = sys.argv[2] if len(sys.argv) == 3 else None  # Get the symbol if provided
        args = parser.parse_args()
        MCX_Live_Data(segment, symbol)

