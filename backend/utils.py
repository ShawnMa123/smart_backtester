# backend/utils.py
import pandas as pd
import akshare as ak
import yfinance as yf
from functools import lru_cache

@lru_cache(maxsize=128)
def get_price_data_and_name(ticker, start_date, end_date): # Renamed function
    print(f"尝试为代码 '{ticker}' 获取数据和名称...")
    ak_start_date = start_date.replace('-', '')
    ak_end_date = end_date.replace('-', '')
    ak_code = ticker.replace('.SS', '').replace('.SZ', '').replace('.SH', '')
    stock_name = ticker # Default to ticker if name not found

    try:
        df = pd.DataFrame()
        index_map = {
            '000300': ('sh000300', '沪深300'),
            '399006': ('sz399006', '创业板指'),
            # Add other common indices if needed
        }
        if ak_code in index_map:
            print(f"检测到指数代码，使用 ak.stock_zh_index_daily 接口...")
            symbol_to_fetch, stock_name = index_map[ak_code]
            df = ak.stock_zh_index_daily(symbol=symbol_to_fetch)
            df = df.rename(columns={'close': 'Close', 'date': 'Date'})

        elif ak_code.startswith('5') or ak_code.startswith('1'): # Typically ETFs
            print(f"检测到ETF/基金代码，使用 ak.fund_etf_hist_em 接口...")
            df = ak.fund_etf_hist_em(symbol=ak_code, period="daily", start_date=ak_start_date, end_date=ak_end_date,
                                     adjust="hfq")
            df = df.rename(columns={'日期': 'Date', '收盘': 'Close', '名称': 'Name'})
            if not df.empty and 'Name' in df.columns:
                stock_name = df['Name'].iloc[0]

        else: # Assume stock
            print(f"检测到股票代码，使用 ak.stock_zh_a_hist 接口...")
            # For individual stocks, name might be harder to get consistently with price
            # We can try to get it separately or rely on ticker
            df = ak.stock_zh_a_hist(symbol=ak_code, period="daily", start_date=ak_start_date, end_date=ak_end_date,
                                    adjust="hfq")
            df = df.rename(columns={'日期': 'Date', '收盘': 'Close', '股票名称': 'Name'}) # Some Akshare versions might have it
            if not df.empty and 'Name' in df.columns:
                 stock_name = df['Name'].iloc[0]
            else: # Fallback: try getting name from a different source if needed
                try:
                    stock_info_df = ak.stock_individual_info_em(symbol=ak_code)
                    if not stock_info_df.empty and 'value' in stock_info_df.columns:
                        name_val = stock_info_df[stock_info_df['item'] == '股票简称']['value']
                        if not name_val.empty:
                            stock_name = name_val.iloc[0]
                except Exception:
                    print(f"无法通过 ak.stock_individual_info_em 获取 {ak_code} 的名称。")


        if df.empty:
            raise ValueError(f"akshare 未返回代码 '{ticker}' 的数据。")

        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        df = df.sort_index()
        df = df.loc[start_date:end_date] # Filter by date *after* setting index

        print(f"成功通过 akshare 获取到 '{ticker}' ({stock_name}) 的数据。")
        return df[['Close']], stock_name

    except Exception as e_ak:
        print(f"使用 akshare 获取 '{ticker}' 数据失败: {e_ak}。正在尝试备用方案 yfinance...")
        try:
            yf_ticker = ticker
            # yfinance doesn't easily provide Chinese names, so we'll use ticker for name
            stock_name = ticker # Or try to get from yf.Ticker(yf_ticker).info['shortName']
            try:
                ticker_info = yf.Ticker(yf_ticker).info
                stock_name = ticker_info.get('shortName', ticker_info.get('longName', ticker))
            except Exception:
                print(f"无法通过 yfinance Ticker info 获取 {yf_ticker} 的名称。")


            if yf_ticker == '000300': yf_ticker = '000300.SS'
            elif ticker.endswith('.SZ') or ticker.endswith('.SS') or ticker.startswith('^'): # Already yf format
                 pass
            elif ticker.startswith('6'): # Shanghai stock
                yf_ticker = f"{ticker}.SS"
            elif ticker.startswith('0') or ticker.startswith('3'): # Shenzhen stock
                yf_ticker = f"{ticker}.SZ"


            data_yf = yf.download(yf_ticker, start=start_date, end=end_date, auto_adjust=True, progress=False) # Renamed to data_yf
            if data_yf.empty: raise ValueError(f"yfinance 未能获取 '{yf_ticker}'")

            print(f"成功通过备用方案 yfinance 获取到 '{yf_ticker}' ({stock_name}) 的数据。")
            return data_yf[['Close']], stock_name
        except Exception as e_yf:
            raise ValueError(f"所有数据源均获取失败。akshare 错误: {e_ak} | yfinance 错误: {e_yf}")

# Keep the old function if other parts of your code still use it directly,
# or update them to use the new one and handle the tuple return.
@lru_cache(maxsize=128)
def get_price_data(ticker, start_date, end_date):
    df, _ = get_price_data_and_name(ticker, start_date, end_date)
    return df