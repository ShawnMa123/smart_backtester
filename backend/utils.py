# backend/utils.py

"""
工具函数模块，主要负责数据获取和缓存。
"""

import yfinance as yf
from functools import lru_cache


# @lru_cache 是一个装饰器，它会缓存函数的输入和输出。
# 当函数以相同的参数再次被调用时，它会立即返回缓存的结果，而无需再次执行函数体。
# 这对于避免重复下载相同的历史数据非常有效。
@lru_cache(maxsize=128)
def get_price_data(ticker, start_date, end_date):
    """
    获取指定股票/ETF在时间范围内的历史价格数据。

    Args:
        ticker (str): 股票或ETF的代码。
        start_date (str): 起始日期, 格式 'YYYY-MM-DD'。
        end_date (str): 结束日期, 格式 'YYYY-MM-DD'。

    Returns:
        pandas.DataFrame: 包含 'Close' 价格的DataFrame，索引为日期。

    Raises:
        ValueError: 如果无法获取到数据或ticker无效。
    """
    try:
        # 使用 yfinance 下载数据
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)

        if data.empty:
            raise ValueError(f"无法获取到代码 '{ticker}' 的数据。请检查代码是否正确或时间范围是否有效。")

        # 我们使用'Adj Close'（复权收盘价），因为它已经处理了分红和拆股，
        # 这对于计算真实的回报率至关重要。将其重命名为'Close'以方便后续统一使用。
        adj_close = data[['Adj Close']].rename(columns={'Adj Close': 'Close'})

        return adj_close
    except Exception as e:
        # 捕获所有可能的异常，并将其包装成一个更友好的ValueError
        raise ValueError(f"下载 {ticker} 数据时发生错误: {e}")