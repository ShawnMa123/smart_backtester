// frontend/script.js
document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('run-backtest-btn');
    // ... 获取其他所有输入框和选择框的DOM元素 ...

    // 初始化 ECharts 实例
    const portfolioChart = echarts.init(document.getElementById('portfolio-chart'));
    const periodicReturnsChart = echarts.init(document.getElementById('periodic-returns-chart'));

    runBtn.addEventListener('click', async () => {
        // 1. 收集配置
        const config = buildConfigFromUI();

        // 显示加载动画...

        // 2. 发送API请求
        try {
            const response = await fetch('http://127.0.0.1:5001/api/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '回测失败');
            }

            const results = await response.json();

            // 3. 渲染结果
            renderResults(results);
            document.getElementById('results-panel').style.display = 'block';

        } catch (error) {
            alert(`错误: ${error.message}`);
        } finally {
            // 隐藏加载动画...
        }
    });

    function buildConfigFromUI() {
        // 这个函数非常重要，它从所有UI输入框中读取值，
        // 并组装成一个与后端API期望的结构完全一致的JSON对象。
        // 例如:
        return {
            ticker: document.getElementById('ticker-input').value,
            startDate: document.getElementById('start-date-input').value,
            endDate: document.getElementById('end-date-input').value,
            initialCapital: 100000,
            strategy: {
                name: document.getElementById('strategy-select').value,
                params: {
                    // 根据选择的策略动态获取参数
                    period: parseInt(document.getElementById('sma-period-input')?.value || 20)
                }
            },
            commission: { /* ... 从UI收集佣金配置 ... */ },
            benchmarkTicker: document.getElementById('benchmark-select').value
        };
    }

    function renderResults(results) {
        // 渲染KPI卡片
        renderKPIs(results.metrics);

        // 渲染资金曲线图
        renderPortfolioChart(results.chart_data);

        // 渲染周期收益图
        renderPeriodicReturnsChart(results.chart_data);
    }

    function renderKPIs(metrics) {
        // 更新HTML中的指标显示
        document.getElementById('total-return-kpi').innerText = `${metrics.totalReturn}%`;
        // ... 更新其他KPIs ...
    }

    function renderPortfolioChart(chartData) {
        const series = [
            { name: '策略', type: 'line', data: chartData.portfolio_curve.values, showSymbol: false },
            { name: '标的基准', type: 'line', data: chartData.benchmark_curve.values, showSymbol: false, lineStyle: { type: 'dashed' } }
        ];

        if (chartData.extra_benchmark_curve) {
             series.push({ name: '大盘基准', type: 'line', data: chartData.extra_benchmark_curve.values, showSymbol: false, lineStyle: { type: 'dotted' } });
        }

        const option = {
            xAxis: { type: 'category', data: chartData.portfolio_curve.dates },
            yAxis: { type: 'value', scale: true },
            tooltip: { trigger: 'axis' },
            legend: { data: series.map(s => s.name) },
            series: series
        };
        portfolioChart.setOption(option, true); // true表示不合并，清除旧图表
    }

    function renderPeriodicReturnsChart(chartData) {
        // 类似地，使用ECharts渲染月度/年度收益柱状图
        const option = {
            xAxis: { type: 'category', data: chartData.monthly_returns.dates },
            yAxis: { type: 'value', axisLabel: { formatter: '{value} %' } },
            tooltip: { trigger: 'axis' },
            series: [{
                name: '月度收益',
                type: 'bar',
                data: chartData.monthly_returns.values
            }]
        };
        periodicReturnsChart.setOption(option, true);
    }

    // ... 还需要实现动态生成策略参数UI的逻辑 ...
});