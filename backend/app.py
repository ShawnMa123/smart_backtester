# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from backtest_engine import run_backtest
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # 允许跨域


@app.route('/api/backtest', methods=['POST'])
def backtest_endpoint():
    try:
        config = request.get_json()

        # 基本校验
        if not config or 'ticker' not in config or 'strategy' not in config:
            return jsonify({'error': 'Invalid configuration provided.'}), 400

        # 自动填充日期（如果前端没提供）
        if 'startDate' not in config or 'endDate' not in config:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            config['startDate'] = start_date.strftime('%Y-%m-%d')
            config['endDate'] = end_date.strftime('%Y-%m-%d')

        results = run_backtest(config)
        return jsonify(results)

    except (ValueError, KeyError) as e:
        # 捕获已知错误，如无效ticker、无效策略
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # 捕获其他未知错误
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({'error': 'An internal server error occurred.'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)
