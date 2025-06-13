# backend/utils.py

"""
工具函数模块，主要使用akshare获取数据，yfinance作为备用。
"""

import pandas as pd
import akshare as ak
import yfinance as yf
from functools import lru_cache


@lru_cache(maxsize=128)
def get_price_data(ticker, start_date, end_date):
    """
    获取价格数据，优先使用 akshare。如果失败或为非国内代码，则尝试 yfinance。

    Args:
        ticker (str): 股票或ETF的代码 (例如 'sh510300', '600519', 'QQQ')。
        start_date (str): 起始日期, 格式 'YYYY-MM-DD'。
        end_date (str): 结束日期, 格式 'YYYY-MM-DD'。

    Returns:
        pandas.DataFrame: 包含复权后 'Close' 价格的DataFrame。

    Raises:
        ValueError: 如果所有数据源都获取失败。
    """
    print(f"尝试为代码 '{ticker}' 获取数据...")

    # --- 1. 优先使用 akshare ---
    try:
        # akshare 的日期格式是 'YYYYMMDD'
        ak_start_date = start_date.replace('-', '')
        ak_end_date = end_date.replace('-', '')

        # akshare 的代码格式没有后缀，但需要前缀 sh/sz
        # 我们先清理一下前端可能传来的各种格式
        ak_code = ticker.replace('.SS', '').replace('.SZ', '').replace('.SH', '')

        # --- 判断是股票还是ETF/基金 ---
        # A股ETF通常是 5 或 1 开头
        if ak_code.startswith('5') or ak_code.startswith('1'):
            print(f"检测到ETF/基金代码，使用 ak.fund_etf_hist_em 接口...")
            # 使用东方财富的ETF历史行情接口
            # 注意：akshare接口可能会变化，请根据最新文档调整
            df = ak.fund_etf_hist_em(symbol=ak_code, period="daily", start_date=ak_start_date, end_date=ak_end_date,
                                     adjust="hfq")
            # 'hfq' 表示后复权

            # --- 数据格式化 ---
            df = df.rename(columns={'日期': 'Date', '收盘': 'Close'})

        # 股票
        else:
            print(f"检测到股票代码，使用 ak.stock_zh_a_hist 接口...")
            # 使用A股历史行情数据接口
            df = ak.stock_zh_a_hist(symbol=ak_code, period="daily", start_date=ak_start_date, end_date=ak_end_date,
                                    adjust="hfq")

            # --- 数据格式化 ---
            df = df.rename(columns={'日期': 'Date', '收盘': 'Close'})

        if df.empty:
            raise ValueError(f"akshare 未返回代码 '{ticker}' 的数据。")

        # --- 通用的数据处理 ---
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')
        df = df.sort_index()

        print(f"成功通过 akshare 获取到 '{ticker}' 的数据。")
        return df[['Close']]

    except Exception as e_ak:
        print(f"使用 akshare 获取 '{ticker}' 数据失败: {e_ak}。正在尝试备用方案 yfinance...")

        # --- 2. akshare 失败后，回退到 yfinance ---
        # yfinance 通常用于非A股市场或作为备用
        try:
            # 转换成yfinance能识别的格式
            yf_ticker = ticker
            if '.SS' not in yf_ticker.upper() and '.SZ' not in yf_ticker.upper() and yf_ticker.startswith(('6', '5')):
                yf_ticker += '.SS'
            elif '.SS' not in yf_ticker.upper() and '.SZ' not in yf_ticker.upper() and yf_ticker.startswith(
                    ('0', '3', '1')):
                yf_ticker += '.SZ'

            data = yf.download(
                yf_ticker,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                progress=False
            )

            if data.empty:
                raise ValueError(f"yfinance 也未能获取到代码 '{yf_ticker}' 的数据。")

            print(f"成功通过备用方案 yfinance 获取到 '{yf_ticker}' 的数据。")
            return data[['Close']]

        except Exception as e_yf:
            raise ValueError(f"所有数据源均获取失败。akshare 错误: {e_ak} | yfinance 错误: {e_yf}")