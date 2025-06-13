# backend/backtest_engine.py
from utils import get_price_data
from strategies import generate_signals
from analysis import analyze_performance


def run_backtest(config):
    """主回测函数"""
    # --- 1. 解构配置 ---
    ticker = config['ticker']
    start_date = config['startDate']
    end_date = config['endDate']
    initial_capital = config.get('initialCapital', 100000)
    strategy_name = config['strategy']['name']
    strategy_params = config['strategy']['params']
    commission_config = config.get('commission', {})
    benchmark_ticker = config.get('benchmarkTicker')

    # --- 2. 数据准备 ---
    data = get_price_data(ticker, start_date, end_date)

    # --- 3. 生成信号 ---
    data = generate_signals(data, strategy_name, strategy_params)

    # --- 4. 回测循环 ---
    cash = float(initial_capital)
    shares = 0
    portfolio_values = []
    last_signal = 0

    for i in range(len(data)):
        # --- 交易逻辑 ---
        signal = data['Signal'].iloc[i]
        price = data['Close'].iloc[i]

        # 定投策略有特殊逻辑
        if strategy_name == 'fixed_frequency' and signal == 1:
            amount = data['InvestmentAmount'].iloc[i]
            if cash >= amount:
                commission = _calculate_commission(amount, commission_config)
                shares_to_buy = (amount - commission) / price
                shares += shares_to_buy
                cash -= amount
        # 信号驱动策略逻辑
        elif strategy_name != 'fixed_frequency':
            if signal == 1 and last_signal <= 0:  # 买入信号
                if cash > 0:
                    commission = _calculate_commission(cash, commission_config)
                    shares_to_buy = (cash - commission) / price
                    shares += shares_to_buy
                    cash = 0
            elif signal == -1 and last_signal >= 0:  # 卖出信号
                if shares > 0:
                    trade_value = shares * price
                    commission = _calculate_commission(trade_value, commission_config)
                    cash += trade_value - commission
                    shares = 0

        last_signal = signal
        portfolio_values.append(cash + shares * price)

    data['Portfolio_Value'] = portfolio_values

    # --- 5. 计算基准 ---
    data['Benchmark_Value'] = (data['Close'] / data['Close'].iloc[0]) * initial_capital
    # 如果有额外的大盘基准，也一并获取和计算
    if benchmark_ticker:
        benchmark_data = get_price_data(benchmark_ticker, start_date, end_date)
        # 对齐日期
        data = data.join(benchmark_data.rename(columns={'Close': 'Benchmark_Index'}), how='left').ffill()
        data['Benchmark_Index_Value'] = (data['Benchmark_Index'] / data['Benchmark_Index'].iloc[0]) * initial_capital

    # --- 6. 性能分析 ---
    results = analyze_performance(data, initial_capital)

    # 把大盘指数曲线也加入返回结果
    if benchmark_ticker and 'Benchmark_Index_Value' in data.columns:
        results['chart_data']['extra_benchmark_curve'] = {
            'dates': data.index.strftime('%Y-%m-%d').tolist(),
            'values': data['Benchmark_Index_Value'].round(2).tolist(),
        }

    return results


def _calculate_commission(trade_value, config):
    """内部函数，计算佣金"""
    comm_type = config.get('type', 'none')
    if comm_type == 'percentage':
        rate = float(config.get('rate', 0.0003))
        min_fee = float(config.get('min_fee', 5))
        return max(trade_value * rate, min_fee)
    elif comm_type == 'fixed':
        return float(config.get('fee', 5))
    return 0