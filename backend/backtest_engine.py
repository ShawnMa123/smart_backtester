# backend/backtest_engine.py
from utils import get_price_data_and_name
from strategies import generate_signals
from analysis import analyze_performance
import pandas as pd
import numpy as np  # Ensure numpy is imported


def run_backtest(config):
    ticker = config['ticker']
    start_date = config['startDate']
    end_date = config['endDate']
    initial_capital_ref = float(config.get('initialCapital', 0))
    strategy_name = config['strategy']['name']
    strategy_params = config['strategy'].get('params', {})
    commission_config = config.get('commission', {})
    benchmark_ticker = config.get('benchmarkTicker')
    take_profit_pct = config.get('takeProfit', None)
    stop_loss_pct = config.get('stopLoss', None)

    data, asset_name = get_price_data_and_name(ticker, start_date, end_date)
    config['assetName'] = asset_name

    benchmark_data_df = None
    if benchmark_ticker:
        benchmark_data_df, benchmark_name = get_price_data_and_name(benchmark_ticker, start_date, end_date)
        config['benchmarkAssetName'] = benchmark_name

    data = generate_signals(data.copy(), strategy_name, strategy_params)

    cash = 0
    shares = 0
    portfolio_values = []
    actual_invested_capital_history = [0]  # Track actual capital invested over time for PnL calcs
    first_investment_amount_for_benchmark = 0  # For scaling benchmarks if initial_capital_ref is 0

    last_signal = 0
    current_position_entry_price = None

    # Store cash and shares for analysis if needed later for PnL calculation
    data['cash_flow'] = 0.0
    data['shares_held'] = 0.0

    for i in range(len(data)):
        price = data['Close'].iloc[i]
        original_signal = data['Signal'].iloc[i]
        actual_signal_for_day = original_signal

        # SL/TP Logic
        if shares > 0 and current_position_entry_price is not None:
            if take_profit_pct is not None and price >= current_position_entry_price * (1 + take_profit_pct):
                actual_signal_for_day = -1
            elif stop_loss_pct is not None and price <= current_position_entry_price * (1 - stop_loss_pct):
                actual_signal_for_day = -1

        if actual_signal_for_day == -1 and original_signal != -1:
            data.loc[data.index[i], 'Signal'] = -1

        current_iter_investment = 0  # Investment made in this iteration

        if strategy_name == 'fixed_frequency' and original_signal == 1:
            amount_to_invest = data['InvestmentAmount'].iloc[i]
            if amount_to_invest > 0:
                commission = _calculate_commission(amount_to_invest, commission_config)
                if amount_to_invest > commission:
                    shares_to_buy = (amount_to_invest - commission) / price
                    if shares > 0 and current_position_entry_price is not None:
                        current_total_value = shares * current_position_entry_price
                        new_total_value = current_total_value + shares_to_buy * price
                        total_shares_after_buy = shares + shares_to_buy
                        current_position_entry_price = new_total_value / total_shares_after_buy if total_shares_after_buy > 0 else price
                    else:
                        current_position_entry_price = price
                    shares += shares_to_buy
                    cash -= amount_to_invest
                    current_iter_investment = amount_to_invest
                    if first_investment_amount_for_benchmark == 0:
                        first_investment_amount_for_benchmark = amount_to_invest

        elif strategy_name != 'fixed_frequency':
            if actual_signal_for_day == 1 and last_signal <= 0:  # Buy
                hypothetical_buy_amount = strategy_params.get('amount',
                                                              1000)  # Default if not specified for signal strategies
                if strategy_name == 'buy_and_hold':  # Special for B&H
                    # If ref > 0, B&H invests ref. If ref=0, B&H invests a default (e.g. first定投额 or this hypo)
                    hypothetical_buy_amount = initial_capital_ref if initial_capital_ref > 0 else strategy_params.get(
                        'amount', 1000)

                commission = _calculate_commission(hypothetical_buy_amount, commission_config)
                if hypothetical_buy_amount > commission:
                    shares_to_buy = (hypothetical_buy_amount - commission) / price
                    if shares > 0 and current_position_entry_price is not None:
                        current_total_value = shares * current_position_entry_price
                        new_total_value = current_total_value + shares_to_buy * price
                        total_shares_after_buy = shares + shares_to_buy
                        current_position_entry_price = new_total_value / total_shares_after_buy if total_shares_after_buy > 0 else price
                    else:
                        current_position_entry_price = price
                    shares += shares_to_buy
                    cash -= hypothetical_buy_amount
                    current_iter_investment = hypothetical_buy_amount
                    if first_investment_amount_for_benchmark == 0:
                        first_investment_amount_for_benchmark = hypothetical_buy_amount

            elif actual_signal_for_day == -1 and shares > 0:  # Sell
                trade_value = shares * price
                commission = _calculate_commission(trade_value, commission_config)
                cash += trade_value - commission
                shares = 0
                current_position_entry_price = None

        data.loc[data.index[i], 'cash_flow'] = cash
        data.loc[data.index[i], 'shares_held'] = shares

        # Track cumulative actual investment (sum of positive outflows)
        # This is a bit simplified, actual_invested_capital is more like -cash if cash is always <=0
        # For PnL % when initial_capital_ref is 0, we need total capital deployed.
        # Let's use -min(0, cash) which is total outflow.
        # A better way is to sum all 'amount_to_invest' or 'hypothetical_buy_amount'
        if i == 0:
            actual_invested_capital_history.append(current_iter_investment)
        else:
            actual_invested_capital_history.append(actual_invested_capital_history[-1] + current_iter_investment)

        last_signal = original_signal
        portfolio_values.append(cash + shares * price)

    data['Portfolio_Value'] = portfolio_values
    data['Cumulative_Investment'] = actual_invested_capital_history[1:]  # Store for analysis

    # --- Asset Benchmark (Buy & Hold of the asset itself) ---
    if not data.empty and data['Close'].iloc[0] != 0:
        asset_first_price = data['Close'].iloc[0]
        if initial_capital_ref > 0:
            data['Asset_Benchmark_Value'] = (data['Close'] / asset_first_price) * initial_capital_ref
        elif first_investment_amount_for_benchmark > 0:  # If ref=0, scale by first strategy investment
            # Value = (current_price / first_price) * first_investment_amount - first_investment_amount
            # This makes it comparable to portfolio_value which is PnL from 0
            # Asset B&H value = (shares_bought_with_first_investment * current_price) - first_investment_amount
            shares_equiv_asset_benchmark = first_investment_amount_for_benchmark / asset_first_price
            data['Asset_Benchmark_Value'] = (shares_equiv_asset_benchmark * data[
                'Close']) - first_investment_amount_for_benchmark
        else:  # No investment made by strategy, B&H also 0 PnL
            data['Asset_Benchmark_Value'] = 0.0
    else:
        data['Asset_Benchmark_Value'] = 0.0

    # --- Market Benchmark (e.g., S&P 500) ---
    if benchmark_ticker and benchmark_data_df is not None and not benchmark_data_df.empty:
        benchmark_data_df = benchmark_data_df.rename(columns={'Close': 'Market_Benchmark_Price'})
        # Ensure 'Market_Benchmark_Price' is present after join, otherwise create it with NaN
        if 'Market_Benchmark_Price' not in data.columns:
            data = data.join(benchmark_data_df['Market_Benchmark_Price'],
                             how='left')  # .ffill().bfill() # ffill then bfill
        else:  # if it was already there (e.g. from a previous failed attempt to join)
            data['Market_Benchmark_Price'] = data['Market_Benchmark_Price'].fillna(
                benchmark_data_df['Market_Benchmark_Price'])

        data['Market_Benchmark_Price'] = data['Market_Benchmark_Price'].ffill().bfill()  # Fill NaNs after join

        if 'Market_Benchmark_Price' in data.columns and not data['Market_Benchmark_Price'].empty and not pd.isna(
                data['Market_Benchmark_Price'].iloc[0]) and data['Market_Benchmark_Price'].iloc[0] != 0:
            market_first_price = data['Market_Benchmark_Price'].iloc[0]
            if initial_capital_ref > 0:
                data['Market_Benchmark_Value'] = (data[
                                                      'Market_Benchmark_Price'] / market_first_price) * initial_capital_ref
            elif first_investment_amount_for_benchmark > 0:  # If ref=0, scale by first strategy investment
                shares_equiv_market_benchmark = first_investment_amount_for_benchmark / market_first_price
                data['Market_Benchmark_Value'] = (shares_equiv_market_benchmark * data[
                    'Market_Benchmark_Price']) - first_investment_amount_for_benchmark
            else:  # No investment made by strategy, so market benchmark also 0 PnL
                data['Market_Benchmark_Value'] = 0.0
        else:
            data['Market_Benchmark_Value'] = 0.0  # Default to 0 if market price is NaN or 0
    else:
        data['Market_Benchmark_Value'] = 0.0

    config['first_investment_amount'] = first_investment_amount_for_benchmark  # Pass to analysis

    results = analyze_performance(data, initial_capital_ref, config)
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