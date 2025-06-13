# backend/app.py

"""
Flask主应用文件，提供API接口。
这是前端与后端通信的桥梁。
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from backtest_engine import run_backtest
from datetime import datetime, timedelta

# 初始化Flask应用
app = Flask(__name__)
# 允许所有来源的跨域请求，这在开发阶段非常方便
CORS(app)


@app.route('/api/backtest', methods=['POST'])
def backtest_endpoint():
    """
    接收前端回测请求的API端点。
    """
    try:
        # 获取前端发送的JSON配置数据
        config = request.get_json()

        if not config:
            return jsonify({'error': '请求体为空或非JSON格式。'}), 400

        # 对关键参数进行基础校验
        if 'ticker' not in config or 'strategy' not in config:
            return jsonify({'error': '缺少 ticker 或 strategy 配置。'}), 400

        # 如果前端没有提供日期，可以设置一个默认值（例如，最近一年）
        if 'startDate' not in config or 'endDate' not in config:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            config['startDate'] = start_date.strftime('%Y-%m-%d')
            config['endDate'] = end_date.strftime('%Y-%m-%d')

        # 调用核心回测引擎
        results = run_backtest(config)

        # 将结果以JSON格式返回给前端
        return jsonify(results)

    except ValueError as e:
        # 捕获已知的、可以友好提示给用户的错误（如无效代码，配置错误）
        # 返回400 Bad Request状态码
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # 捕获所有其他未预料到的服务器内部错误
        # 在服务器日志中记录详细错误，方便调试
        app.logger.error(f"发生未预料的错误: {e}", exc_info=True)
        # 返回500 Internal Server Error状态码
        return jsonify({'error': '服务器内部发生错误，请稍后再试或联系管理员。'}), 500


# 使得这个脚本可以直接通过 `python app.py` 运行
if __name__ == '__main__':
    # debug=True 会在代码变动后自动重启服务，并提供详细的错误追溯
    app.run(debug=True, port=5001)