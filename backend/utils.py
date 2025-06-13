# backend/utils.py
import yfinance as yf
from functools import lru_cache

# 使用lru_cache作为简单的内存缓存，避免重复下载
# maxsize可以根据你的内存大小调整
@lru_cache(maxsize=32)
def get_price_data(ticker, start_date, end_date):
    """
    获取指定ticker在时间范围内的历史价格数据。
    使用'Adj Close'并重命名为'Close'，因为它已处理分红和拆股，适合计算回报。
    """
    try:
        data = yf.download(ticker, start=start_date, end=end_date)
        if data.empty:
            raise ValueError(f"No data found for ticker '{ticker}'")
        # 我们需要原始的'Close'用于交易模拟，'Adj Close'用于回报计算
        # 为简化，这里我们只用 'Adj Close'
        adj_close = data[['Adj Close']].rename(columns={'Adj Close': 'Close'})
        return adj_close
    except Exception as e:
        # 抛出更具体的错误信息
        raise ValueError(f"Failed to download data for {ticker}. Error: {e}")
