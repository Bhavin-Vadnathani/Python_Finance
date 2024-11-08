import sys
import pandas as pd
import datetime
import requests

pd.set_option('display.max_columns', None)  # Display all columns
pd.set_option('display.width', None)        # Disable line wrapping to allow a single line
pd.set_option('display.max_colwidth', None) # Display full column content without truncation

def get_data():
    # url = "https://www.mcxindia.com/backpage.aspx/GetMarketWatch"
    
    import requests

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
    CE_data = Opt_df.loc[(Opt_df.OptionType == "CE")]
    PE_data = Opt_df.loc[(Opt_df.OptionType == "PE")]
    merged_df = pd.merge(CE_data, PE_data, on='StrikePrice', suffixes= ('_CE','_PE'))
    #merged_df = merged_df[['Open', 'Low', 'Volume', 'OpenInterest','NotionalValue', 'PremiumValue', 'OptionType','StrikePrice']]
    merged_df = merged_df[['Open_CE', 'Low_CE', 'Volume_CE', 'OpenInterest_CE', 
                       'NotionalValue_CE', 'PremiumValue_CE', 'OptionType_CE', 'StrikePrice',
                       'Open_PE', 'Low_PE', 'Volume_PE', 'OpenInterest_PE', 
                       'NotionalValue_PE', 'PremiumValue_PE', 'OptionType_PE']]

    return merged_df

def MCX_Live_Data(segment, symbol):
    if segment == 'FUT':
        print(Future())
    elif segment == 'OPT':
        print(Options(symbol))
    else:
        print("Invalid Segment")

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python MCX_Live_Data.py <segment> [<symbol>]")
        print("<segment> should be either 'FUT' or 'OPT'.")
        print("<symbol> is required if segment is 'OPT'.")
    else:
        segment = sys.argv[1]  # Get the segment from command line argument
        symbol = sys.argv[2] if len(sys.argv) == 3 else None  # Get the symbol if provided
        MCX_Live_Data(segment, symbol)

