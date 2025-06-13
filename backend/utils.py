# backend/utils.py
import pandas as pd
import akshare as ak
import yfinance as yf
from functools import lru_cache


@lru_cache(maxsize=128)
def get_price_data(ticker, start_date, end_date):
    print(f"尝试为代码 '{ticker}' 获取数据...")
    ak_start_date = start_date.replace('-', '')
    ak_end_date = end_date.replace('-', '')
    ak_code = ticker.replace('.SS', '').replace('.SZ', '').replace('.SH', '')

    try:
        df = pd.DataFrame()
        index_map = {
            '000300': 'sh000300', '399006': 'sz399006',
        }
        if ak_code in index_map:
            print(f"检测到指数代码，使用 ak.stock_zh_index_daily 接口...")
            df = ak.stock_zh_index_daily(symbol=index_map[ak_code])
            df = df.rename(columns={'close': 'Close', 'date': 'Date'})

        elif ak_code.startswith('5') or ak_code.startswith('1'):
            print(f"检测到ETF/基金代码，使用 ak.fund_etf_hist_em 接口...")
            df = ak.fund_etf_hist_em(symbol=ak_code, period="daily", start_date=ak_start_date, end_date=ak_end_date,
                                     adjust="hfq")
            df = df.rename(columns={'日期': 'Date', '收盘': 'Close'})

        else:
            print(f"检测到股票代码，使用 ak.stock_zh_a_hist 接口...")
            df = ak.stock_zh_a_hist(symbol=ak_code, period="daily", start_date=ak_start_date, end_date=ak_end_date,
                                    adjust="hfq")
            df = df.rename(columns={'日期': 'Date', '收盘': 'Close'})

        if df.empty:
            raise ValueError(f"akshare 未返回代码 '{ticker}' 的数据。")

        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        df = df.sort_index()
        df = df.loc[start_date:end_date]

        print(f"成功通过 akshare 获取到 '{ticker}' 的数据。")
        return df[['Close']]

    except Exception as e_ak:
        print(f"使用 akshare 获取 '{ticker}' 数据失败: {e_ak}。正在尝试备用方案 yfinance...")
        try:
            yf_ticker = ticker
            if yf_ticker == '000300': yf_ticker = '000300.SS'  # 特殊处理沪深300

            data = yf.download(yf_ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
            if data.empty: raise ValueError(f"yfinance 未能获取 '{yf_ticker}'")
            print(f"成功通过备用方案 yfinance 获取到 '{yf_ticker}' 的数据。")
            return data[['Close']]
        except Exception as e_yf:
            raise ValueError(f"所有数据源均获取失败。akshare 错误: {e_ak} | yfinance 错误: {e_yf}")