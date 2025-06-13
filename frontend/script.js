document.addEventListener('DOMContentLoaded', () => {
    // --- DOM元素获取 ---
    // 输入区域
    const tickerInput = document.getElementById('tickerInput');
    const periodSelect = document.getElementById('periodSelect');
    const benchmarkSelect = document.getElementById('benchmarkSelect');
    
    // 策略区域
    const strategySelect = document.getElementById('strategySelect');
    const strategyParamsContainer = document.getElementById('strategyParams');
    const presetSelect = document.getElementById('presetSelect');

    // 成本区域
    const commissionTypeSelect = document.getElementById('commissionType');
    const commissionParamsContainer = document.getElementById('commissionParams');

    // 控制与反馈
    const runButton = document.getElementById('runButton');
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('error-alert');
    const errorMessageSpan = document.getElementById('error-message');
    
    // 结果区域
    const resultsDiv = document.getElementById('results');
    const kpiContainer = document.getElementById('kpi-cards');
    const portfolioChartDiv = document.getElementById('portfolio-chart');
    const periodicReturnsChartDiv = document.getElementById('periodic-returns-chart');
    
    // 初始化ECharts实例
    const portfolioChart = echarts.init(portfolioChartDiv);
    const periodicReturnsChart = echarts.init(periodicReturnsChartDiv);

    // --- 数据与配置 ---
    const presets = {
        'tech-power': {
            name: '科技巨头动力组合 (QQQ)',
            config: {
                ticker: 'QQQ',
                benchmark: '^NDX',
                strategy: { name: 'dma_cross', params: { fast: 20, slow: 50 } },
                commission: { type: 'percentage', rate: 0.03, min_fee: 1 }
            }
        },
        'a-share-core': {
            name: 'A股核心资产定投 (沪深300)',
            config: {
                ticker: '510300.SS',
                benchmark: '000300.SS',
                strategy: { name: 'fixed_frequency', params: { frequency: 'M', amount: 1000 } },
                commission: { type: 'percentage', rate: 0.03, min_fee: 5 }
            }
        },
        'sp500-buy-hold': {
            name: '标普500指数投资 (SPY)',
            config: {
                ticker: 'SPY',
                benchmark: '^GSPC',
                strategy: { name: 'buy_and_hold', params: {} },
                commission: { type: 'none' }
            }
        }
    };

    // --- 事件监听 ---
    strategySelect.addEventListener('change', renderStrategyParams);
    commissionTypeSelect.addEventListener('change', renderCommissionParams);
    presetSelect.addEventListener('change', applyPreset);
    runButton.addEventListener('click', runBacktest);

    // --- 初始化 ---
    initializeUI();

    /**
     * 初始化UI界面，设置默认值并首次渲染动态部分
     */
    function initializeUI() {
        populatePresets();
        renderStrategyParams();
        renderCommissionParams();
    }

    /**
     * 填充预设策略的下拉菜单
     */
    function populatePresets() {
        for (const key in presets) {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = presets[key].name;
            presetSelect.appendChild(option);
        }
    }

    /**
     * 应用选定的预设配置到UI上
     */
    function applyPreset() {
        const selectedPresetKey = presetSelect.value;
        if (!selectedPresetKey) return;

        const preset = presets[selectedPresetKey].config;

        tickerInput.value = preset.ticker;
        benchmarkSelect.value = preset.benchmark;
        strategySelect.value = preset.strategy.name;
        
        // 渲染对应策略的参数UI，并填充预设值
        renderStrategyParams();
        for (const paramKey in preset.strategy.params) {
            const input = document.getElementById(`param-${paramKey}`);
            if (input) {
                input.value = preset.strategy.params[paramKey];
            }
        }

        commissionTypeSelect.value = preset.commission.type;
        // 渲染对应佣金的参数UI，并填充预设值
        renderCommissionParams();
         for (const paramKey in preset.commission) {
            if (paramKey === 'type') continue;
            const input = document.getElementById(`param-${paramKey}`);
            if (input) {
                input.value = preset.commission[paramKey];
            }
        }

        // 重置选择，避免混淆
        presetSelect.value = "";
    }


    /**
     * 主函数：执行回测
     */
    async function runBacktest() {
        // 1. 校验输入
        if (!tickerInput.value.trim()) {
            showError('请输入ETF或股票代码！');
            return;
        }

        // 2. 准备阶段
        setLoading(true);
        const config = buildConfigFromUI();

        // 3. 发送API请求
        try {
            const response = await fetch('http://127.0.0.1:5001/api/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `服务器错误: ${response.status}`);
            }
            
            const results = await response.json();
            
            // 4. 渲染结果
            renderResults(results);

        } catch (error) {
            showError(`回测失败: ${error.message}`);
        } finally {
            setLoading(false);
        }
    }

    /**
     * 从UI收集所有配置，构建成API需要的JSON对象
     * @returns {object} - 回测配置对象
     */
    function buildConfigFromUI() {
        // 计算日期
        const period = periodSelect.value;
        const endDate = new Date();
        const startDate = new Date();
        const daysMap = { '3m': 90, '6m': 180, '1y': 365, '5y': 365 * 5 };
        startDate.setDate(endDate.getDate() - (daysMap[period] || 365));

        const formatDate = (date) => date.toISOString().split('T')[0];

        // 构建策略参数
        const strategyName = strategySelect.value;
        const strategyParams = {};
        const paramInputs = strategyParamsContainer.querySelectorAll('input, select');
        paramInputs.forEach(input => {
            // 从id 'param-xxx' 中提取 'xxx'
            const key = input.id.split('-')[1];
            strategyParams[key] = isNaN(input.value) ? input.value : parseFloat(input.value);
        });
        
        // 构建佣金参数
        const commissionType = commissionTypeSelect.value;
        const commissionParams = { type: commissionType };
        const commissionInputs = commissionParamsContainer.querySelectorAll('input');
        commissionInputs.forEach(input => {
            const key = input.id.split('-')[1];
            // 后端需要的是费率，不是万分之几
            if (key === 'rate') {
                commissionParams[key] = parseFloat(input.value) / 10000;
            } else {
                commissionParams[key] = parseFloat(input.value);
            }
        });

        return {
            ticker: tickerInput.value.trim().toUpperCase(),
            startDate: formatDate(startDate),
            endDate: formatDate(endDate),
            initialCapital: 100000,
            strategy: { name: strategyName, params: strategyParams },
            commission: commissionParams,
            benchmarkTicker: benchmarkSelect.value || null
        };
    }

    /**
     * 渲染所有结果：指标和图表
     * @param {object} results - 后端返回的结果数据
     */
    function renderResults(results) {
        renderKPIs(results.metrics, results.chart_data);
        renderPortfolioChart(results.chart_data);
        renderPeriodicReturnsChart(results.chart_data);
        resultsDiv.style.display = 'block';
    }

    /**
     * 渲染关键性能指标(KPI)
     */
    function renderKPIs(metrics, chartData) {
        // 计算基准的回报
        const benchmarkReturn = ((chartData.benchmark_curve.values.slice(-1)[0] / 100000 - 1) * 100).toFixed(2);
        
        kpiContainer.innerHTML = `
            <div class="col-md-3"><div class="card p-3 text-center">
                <div class="metric-value ${metrics.totalReturn >= 0 ? 'text-success' : 'text-danger'}">${metrics.totalReturn}%</div>
                <div class="metric-label">策略总回报</div>
            </div></div>
            <div class="col-md-3"><div class="card p-3 text-center">
                <div class="metric-value ${benchmarkReturn >= 0 ? 'text-success' : 'text-danger'}">${benchmarkReturn}%</div>
                <div class="metric-label">基准总回报</div>
            </div></div>
            <div class="col-md-3"><div class="card p-3 text-center">
                <div class="metric-value ${metrics.annualizedReturn >= 0 ? 'text-success' : 'text-danger'}">${metrics.annualizedReturn}%</div>
                <div class="metric-label">年化回报</div>
            </div></div>
            <div class="col-md-3"><div class="card p-3 text-center">
                <div class="metric-value text-danger">${metrics.maxDrawdown}%</div>
                <div class="metric-label">最大回撤</div>
            </div></div>
        `;
    }

    /**
     * 渲染资金曲线图
     */
    function renderPortfolioChart(chartData) {
        const series = [
            { name: '策略', type: 'line', data: chartData.portfolio_curve.values, showSymbol: false },
            { name: '标的基准', type: 'line', data: chartData.benchmark_curve.values, showSymbol: false, lineStyle: { type: 'dashed' } }
        ];
        
        if (chartData.extra_benchmark_curve) {
             series.push({ name: '大盘基准', type: 'line', data: chartData.extra_benchmark_curve.values, showSymbol: false, lineStyle: { type: 'dotted' } });
        }

        const option = {
            title: { text: '资金曲线' },
            tooltip: { trigger: 'axis' },
            legend: { data: series.map(s => s.name), top: 'bottom' },
            grid: { left: '10%', right: '10%', bottom: '15%', containLabel: true },
            xAxis: { type: 'category', data: chartData.portfolio_curve.dates },
            yAxis: { type: 'value', scale: true, axisLabel: { formatter: '{value}' } },
            series: series
        };
        portfolioChart.setOption(option, true);
    }
    
    /**
     * 渲染周期收益图
     */
    function renderPeriodicReturnsChart(chartData) {
        // 默认显示月度，可以增加切换按钮来显示年度
        const returnsData = chartData.monthly_returns;
        const titleText = '月度收益率分布';

        const option = {
            title: { text: titleText },
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: { type: 'category', data: returnsData.dates },
            yAxis: { type: 'value', axisLabel: { formatter: '{value} %' } },
            series: [{
                name: '收益率',
                type: 'bar',
                data: returnsData.values,
                itemStyle: {
                    color: (params) => params.value >= 0 ? '#91cc75' : '#ee6666'
                }
            }]
        };
        periodicReturnsChart.setOption(option, true);
    }

    /**
     * 根据选择的策略，动态渲染其参数输入框
     */
    function renderStrategyParams() {
        const strategy = strategySelect.value;
        let html = '';
        switch (strategy) {
            case 'fixed_frequency':
                html = `
                    <div class="col-auto"><label class="form-label">投资频率</label><select id="param-frequency" class="form-select"><option value="W">每周</option><option value="M" selected>每月</option><option value="Y">每年</option></select></div>
                    <div class="col-auto"><label class="form-label">每次金额</label><input type="number" id="param-amount" class="form-control" value="1000"></div>
                `;
                break;
            case 'sma_cross':
                html = `<div class="col-auto"><label class="form-label">均线周期</label><input type="number" id="param-period" class="form-control" value="20"></div>`;
                break;
            case 'dma_cross':
                html = `
                    <div class="col-auto"><label class="form-label">快线</label><input type="number" id="param-fast" class="form-control" value="10"></div>
                    <div class="col-auto"><label class="form-label">慢线</label><input type="number" id="param-slow" class="form-control" value="30"></div>
                `;
                break;
        }
        strategyParamsContainer.innerHTML = html;
    }

    /**
     * 根据选择的佣金类型，动态渲染其参数输入框
     */
    function renderCommissionParams() {
        const type = commissionTypeSelect.value;
        let html = '';
        if (type === 'percentage') {
            html = `
                <div class="col-auto"><label class="form-label">费率(万分之)</label><input type="number" id="param-rate" class="form-control" value="3"></div>
                <div class="col-auto"><label class="form-label">最低收费(元)</label><input type="number" id="param-min-fee" class="form-control" value="5"></div>
            `;
        } else if (type === 'fixed') {
            html = `<div class="col-auto"><label class="form-label">每笔费用(元)</label><input type="number" id="param-fee" class="form-control" value="5"></div>`;
        }
        commissionParamsContainer.innerHTML = html;
    }
    
    /**
     * 控制加载状态的显示
     * @param {boolean} isLoading - 是否正在加载
     */
    function setLoading(isLoading) {
        if (isLoading) {
            runButton.disabled = true;
            runButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 回测中...`;
            loadingDiv.style.display = 'block';
            resultsDiv.style.display = 'none';
            errorDiv.style.display = 'none';
        } else {
            runButton.disabled = false;
            runButton.textContent = '开始回测';
            loadingDiv.style.display = 'none';
        }
    }

    /**
     * 显示错误信息
     * @param {string} message - 错误消息文本
     */
    function showError(message) {
        errorMessageSpan.textContent = message;
        errorDiv.style.display = 'block';
        resultsDiv.style.display = 'none'; // 隐藏旧的结果
    }
});