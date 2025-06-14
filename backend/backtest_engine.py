# backend/backtest_engine.py
from utils import get_price_data_and_name  # Use the new function
from strategies import generate_signals
from analysis import analyze_performance
import pandas as pd


def run_backtest(config):
    ticker = config['ticker']
    start_date = config['startDate']
    end_date = config['endDate']
    # ---- MODIFIED: Initial Capital ----
    initial_capital = float(config.get('initialCapital', 100000))  # Default 100k if not provided
    # ---- END MODIFIED ----
    strategy_name = config['strategy']['name']
    strategy_params = config['strategy'].get('params', {})
    commission_config = config.get('commission', {})
    benchmark_ticker = config.get('benchmarkTicker')

    # ---- NEW: Stop-Loss / Take-Profit params ----
    take_profit_pct = config.get('takeProfit', None)  # e.g., 0.1 for 10%
    stop_loss_pct = config.get('stopLoss', None)  # e.g., 0.05 for 5%
    # ---- END NEW ----

    # --- 2. 数据准备 ---
    # ---- MODIFIED: Use new util function ----
    data, asset_name = get_price_data_and_name(ticker, start_date, end_date)
    config['assetName'] = asset_name  # Store asset name in config to pass to analysis
    if benchmark_ticker:
        benchmark_data_df, benchmark_name = get_price_data_and_name(benchmark_ticker, start_date, end_date)
        config['benchmarkAssetName'] = benchmark_name
    # ---- END MODIFIED ----

    # --- 3. 生成交易信号 ---
    data = generate_signals(data.copy(), strategy_name, strategy_params)  # Pass a copy

    # --- 4. 核心回测循环 ---
    cash = initial_capital
    shares = 0
    portfolio_values = []
    last_signal = 0  # From strategy

    # For SL/TP, track entry price for current position
    current_position_entry_price = None
    positions = []  # To store trade details for advanced P&L (optional for now)

    for i in range(len(data)):
        price = data['Close'].iloc[i]
        original_signal = data['Signal'].iloc[i]  # Signal from strategy

        # --- Apply SL/TP logic (overrides strategy signal if triggered) ---
        actual_signal_for_day = original_signal  # Start with strategy signal

        if shares > 0 and current_position_entry_price is not None:  # If holding a position
            # Check Take Profit
            if take_profit_pct is not None and price >= current_position_entry_price * (1 + take_profit_pct):
                actual_signal_for_day = -1  # Force sell for Take Profit
                print(f"{data.index[i].strftime('%Y-%m-%d')}: Take Profit triggered at {price:.2f}")
            # Check Stop Loss (importantly, check *after* take profit)
            elif stop_loss_pct is not None and price <= current_position_entry_price * (1 - stop_loss_pct):
                actual_signal_for_day = -1  # Force sell for Stop Loss
                print(f"{data.index[i].strftime('%Y-%m-%d')}: Stop Loss triggered at {price:.2f}")

        # Override the 'Signal' column for this day if SL/TP triggered a sell
        # This ensures analysis.py correctly identifies SL/TP sell points
        if actual_signal_for_day == -1 and original_signal != -1:
            data.loc[data.index[i], 'Signal'] = -1  # Update DataFrame for analysis

        # --- 定投策略有特殊的交易逻辑 ---
        if strategy_name == 'fixed_frequency' and actual_signal_for_day == 1:
            # For fixed_frequency, 'Signal' being 1 means it's an investment day.
            # SL/TP should ideally not interfere with a buy signal of fixed_frequency,
            # as it's a regular investment. SL/TP applies to *existing* holdings.
            # So, if actual_signal_for_day was forced to -1 by SL/TP, that sell happens first.
            # If not, and original_signal was 1 (buy day), proceed with buy.
            if original_signal == 1:  # ensure it was a buy day from strategy
                amount_to_invest = data['InvestmentAmount'].iloc[i]
                if cash >= amount_to_invest and amount_to_invest > 0:
                    commission = _calculate_commission(amount_to_invest, commission_config)
                    if amount_to_invest > commission:
                        shares_to_buy = (amount_to_invest - commission) / price
                        shares += shares_to_buy
                        cash -= amount_to_invest

                        # Update entry price for averaging down or new position
                        if current_position_entry_price is None or shares_to_buy == shares:  # first buy or full reinvest
                            current_position_entry_price = price
                        else:  # Averaging
                            current_position_entry_price = ((
                                                                        shares - shares_to_buy) * current_position_entry_price + shares_to_buy * price) / shares
                        # print(f"{data.index[i].strftime('%Y-%m-%d')}: Fixed Freq Buy {shares_to_buy:.2f} at {price:.2f}. Entry: {current_position_entry_price:.2f}")


        # --- 信号驱动策略的交易逻辑 (Non-fixed_frequency) ---
        elif strategy_name != 'fixed_frequency':
            # 当信号从非正数变为1时 (BUY from strategy, and not SL/TP sell)
            if actual_signal_for_day == 1 and last_signal <= 0:
                if cash > 0:  # Only buy if we have cash
                    # Sell existing shares if any (e.g., if strategy flipped from short to long, though not supported yet)
                    if shares > 0:  # This case should ideally not happen if last_signal <=0
                        trade_value_sell = shares * price
                        commission_sell = _calculate_commission(trade_value_sell, commission_config)
                        cash += trade_value_sell - commission_sell
                        shares = 0
                        current_position_entry_price = None

                    commission_buy = _calculate_commission(cash, commission_config)  # All in
                    if cash > commission_buy:
                        shares_to_buy = (cash - commission_buy) / price
                        shares += shares_to_buy
                        cash = 0
                        current_position_entry_price = price  # New position entry price
                        # print(f"{data.index[i].strftime('%Y-%m-%d')}: Signal Buy {shares_to_buy:.2f} at {price:.2f}. Entry: {current_position_entry_price:.2f}")

            # 当信号从非负数变为-1时 (SELL from strategy OR SL/TP)
            elif actual_signal_for_day == -1 and (last_signal >= 0 or (
                    original_signal != -1 and actual_signal_for_day == -1)):  # (last_signal from strategy >=0 OR SL/TP override)
                if shares > 0:
                    trade_value = shares * price
                    commission = _calculate_commission(trade_value, commission_config)
                    cash += trade_value - commission
                    shares = 0
                    current_position_entry_price = None  # Position closed
                    # print(f"{data.index[i].strftime('%Y-%m-%d')}: Signal/SLTP Sell at {price:.2f}")

        last_signal = original_signal  # Track strategy's signal for next iteration's comparison
        portfolio_values.append(cash + shares * price)

    data['Portfolio_Value'] = portfolio_values

    # --- 5. 计算基准 ---
    data['Benchmark_Value'] = (data['Close'] / data['Close'].iloc[0]) * initial_capital if initial_capital > 0 else 0

    if benchmark_ticker:
        try:
            # benchmark_data_df already fetched
            data = data.join(benchmark_data_df.rename(columns={'Close': 'Benchmark_Index'}), how='left').ffill()
            data['Benchmark_Index_Value'] = (data['Benchmark_Index'] / data['Benchmark_Index'].iloc[
                0]) * initial_capital if initial_capital > 0 else 0
        except ValueError as e:
            print(f"Warning: Could not process benchmark {benchmark_ticker}. Error: {e}")

    # --- 6. 性能分析 ---
    results = analyze_performance(data, initial_capital, config)  # Pass full config for names

    # (Extra benchmark curve already handled in analyze_performance if data is there)
    return results


def _calculate_commission(trade_value, config):
    comm_type = config.get('type', 'none')
    if comm_type == 'percentage':
        rate = float(config.get('rate', 0.0003))
        min_fee = float(config.get('min_fee', 5.0))
        return max(trade_value * rate, min_fee)
    elif comm_type == 'fixed':
        return float(config.get('fee', 5.0))
    return 0