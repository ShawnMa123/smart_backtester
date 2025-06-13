# backend/backtest_engine.py

"""
核心回测引擎。
这是所有逻辑的粘合剂，负责运行完整的回测流程。
"""

from utils import get_price_data
from strategies import generate_signals
from analysis import analyze_performance


def run_backtest(config):
    """
    主回测函数，执行整个回测过程。

    Args:
        config (dict): 包含所有回测配置的字典。

    Returns:
        dict: 包含回测结果的字典。
    """
    # --- 1. 解构配置 ---
    ticker = config['ticker']
    start_date = config['startDate']
    end_date = config['endDate']
    initial_capital = float(config.get('initialCapital', 100000))
    strategy_name = config['strategy']['name']
    strategy_params = config['strategy'].get('params', {})
    commission_config = config.get('commission', {})
    benchmark_ticker = config.get('benchmarkTicker')

    # --- 2. 数据准备 ---
    data = get_price_data(ticker, start_date, end_date)

    # --- 3. 生成交易信号 ---
    data = generate_signals(data, strategy_name, strategy_params)

    # --- 4. 核心回测循环 ---
    cash = initial_capital
    shares = 0
    portfolio_values = []
    # last_signal用于判断信号变化，避免在持续的买入/卖出信号下重复交易
    last_signal = 0

    for i in range(len(data)):
        price = data['Close'].iloc[i]
        signal = data['Signal'].iloc[i]

        # 定投策略有特殊的交易逻辑
        if strategy_name == 'fixed_frequency' and signal == 1:
            amount = data['InvestmentAmount'].iloc[i]
            if cash >= amount:
                commission = _calculate_commission(amount, commission_config)
                if amount > commission:
                    shares_to_buy = (amount - commission) / price
                    shares += shares_to_buy
                    cash -= amount

        # 信号驱动策略的交易逻辑
        elif strategy_name != 'fixed_frequency':
            # 当信号从非正数变为1时，执行买入
            if signal == 1 and last_signal <= 0:
                if cash > 0:
                    commission = _calculate_commission(cash, commission_config)
                    shares_to_buy = (cash - commission) / price
                    shares += shares_to_buy
                    cash = 0
            # 当信号从非负数变为-1时，执行卖出
            elif signal == -1 and last_signal >= 0:
                if shares > 0:
                    trade_value = shares * price
                    commission = _calculate_commission(trade_value, commission_config)
                    cash += trade_value - commission
                    shares = 0

        last_signal = signal
        portfolio_values.append(cash + shares * price)

    data['Portfolio_Value'] = portfolio_values

    # --- 5. 计算基准 ---
    # 标的自身的买入并持有作为默认基准
    data['Benchmark_Value'] = (data['Close'] / data['Close'].iloc[0]) * initial_capital

    # 如果用户选择了额外的大盘指数基准
    if benchmark_ticker:
        try:
            benchmark_data = get_price_data(benchmark_ticker, start_date, end_date)
            # 将大盘指数数据合并到主DataFrame，并处理可能不匹配的交易日（向前填充）
            data = data.join(benchmark_data.rename(columns={'Close': 'Benchmark_Index'}), how='left').ffill()
            data['Benchmark_Index_Value'] = (data['Benchmark_Index'] / data['Benchmark_Index'].iloc[
                0]) * initial_capital
        except ValueError as e:
            # 如果大盘指数获取失败，则忽略，不中断主回测
            print(f"Warning: Could not process benchmark {benchmark_ticker}. Error: {e}")

    # --- 6. 性能分析 ---
    results = analyze_performance(data, initial_capital)

    # 将额外的大盘基准曲线加入到返回结果中
    if benchmark_ticker and 'Benchmark_Index_Value' in data.columns:
        results['chart_data']['extra_benchmark_curve'] = {
            'name': benchmark_ticker,
            'dates': data.index.strftime('%Y-%m-%d').tolist(),
            'values': data['Benchmark_Index_Value'].round(2).tolist(),
        }

    return results


def _calculate_commission(trade_value, config):
    """内部辅助函数，用于计算交易佣金。"""
    comm_type = config.get('type', 'none')
    if comm_type == 'percentage':
        rate = float(config.get('rate', 0.0003))
        min_fee = float(config.get('min_fee', 5.0))
        return max(trade_value * rate, min_fee)
    elif comm_type == 'fixed':
        return float(config.get('fee', 5.0))
    return 0