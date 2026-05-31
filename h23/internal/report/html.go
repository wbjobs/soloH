package report

import (
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"time"

	"randomness-tester/internal/config"
	"randomness-tester/internal/tests"
)

type VisualReportData struct {
	Report     *FullReport
	Corrections []config.ParameterRecommendation
}

func GenerateHTMLReport(data *VisualReportData, w io.Writer) error {
	report := data.Report
	jsonResults, _ := json.Marshal(report.Results)

	html := fmt.Sprintf(`<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NIST 随机性测试报告 - %s</title>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        }
        .header h1 {
            color: #333;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .header .subtitle {
            color: #666;
            font-size: 14px;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .summary-card {
            background: linear-gradient(135deg, #f5f7fa 0%%, #c3cfe2 100%%);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        .summary-card .label {
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .summary-card .value {
            color: #333;
            font-size: 32px;
            font-weight: bold;
            margin-top: 5px;
        }
        .summary-card.passed .value { color: #10b981; }
        .summary-card.failed .value { color: #ef4444; }
        .summary-card.overall-passed {
            background: linear-gradient(135deg, #a7f3d0 0%%, #34d399 100%%);
        }
        .summary-card.overall-failed {
            background: linear-gradient(135deg, #fecaca 0%%, #f87171 100%%);
        }
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        @media (max-width: 1000px) {
            .main-content { grid-template-columns: 1fr; }
        }
        .chart-container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        }
        .chart-container h2 {
            color: #333;
            font-size: 18px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e5e7eb;
        }
        .chart {
            width: 100%%;
            height: 400px;
        }
        .full-width {
            grid-column: 1 / -1;
        }
        .details-table {
            width: 100%%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .details-table th {
            background: #f3f4f6;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #374151;
            position: sticky;
            top: 0;
        }
        .details-table td {
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }
        .details-table tr:hover {
            background: #f9fafb;
        }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }
        .status-passed {
            background: #d1fae5;
            color: #065f46;
        }
        .status-failed {
            background: #fee2e2;
            color: #991b1b;
        }
        .status-error {
            background: #fef3c7;
            color: #92400e;
        }
        .pvalue-bar {
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 4px;
        }
        .pvalue-fill {
            height: 100%%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        .corrections-section {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        }
        .corrections-section h2 {
            color: #333;
            font-size: 18px;
            margin-bottom: 15px;
        }
        .correction-item {
            padding: 12px;
            margin-bottom: 8px;
            border-radius: 8px;
            border-left: 4px solid;
        }
        .correction-item.warning {
            background: #fef3c7;
            border-color: #f59e0b;
        }
        .correction-item.ok {
            background: #d1fae5;
            border-color: #10b981;
        }
        .correction-item.error {
            background: #fee2e2;
            border-color: #ef4444;
        }
        .table-scroll {
            max-height: 500px;
            overflow-y: auto;
        }
        .footer {
            text-align: center;
            color: rgba(255, 255, 255, 0.8);
            padding: 20px;
            font-size: 12px;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        .info-item {
            background: #f3f4f6;
            padding: 10px;
            border-radius: 8px;
        }
        .info-item .label {
            font-size: 11px;
            color: #6b7280;
            text-transform: uppercase;
        }
        .info-item .value {
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;
            margin-top: 2px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎲 NIST 随机性测试报告</h1>
            <div class="subtitle">生成时间: %s</div>

            <div class="info-grid">
                <div class="info-item">
                    <div class="label">输入类型</div>
                    <div class="value">%s</div>
                </div>
                <div class="info-item">
                    <div class="label">输入源</div>
                    <div class="value" title="%s">%s</div>
                </div>
                <div class="info-item">
                    <div class="label">比特长度</div>
                    <div class="value">%d bits</div>
                </div>
                <div class="info-item">
                    <div class="label">显著水平</div>
                    <div class="value">%.4f</div>
                </div>
                <div class="info-item">
                    <div class="label">并行度</div>
                    <div class="value">%d 核</div>
                </div>
                <div class="info-item">
                    <div class="label">执行时间</div>
                    <div class="value">%.2f 秒</div>
                </div>
            </div>

            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">总测试数</div>
                    <div class="value">%d</div>
                </div>
                <div class="summary-card passed">
                    <div class="label">通过</div>
                    <div class="value">%d</div>
                </div>
                <div class="summary-card failed">
                    <div class="label">失败</div>
                    <div class="value">%d</div>
                </div>
                <div class="summary-card %s">
                    <div class="label">总体结果</div>
                    <div class="value">%s</div>
                </div>
            </div>
        </div>

        <div class="main-content">
            <div class="chart-container">
                <h2>📊 P-Value 分布</h2>
                <div id="pvalueChart" class="chart"></div>
            </div>

            <div class="chart-container">
                <h2>🥧 测试结果统计</h2>
                <div id="pieChart" class="chart"></div>
            </div>

            <div class="chart-container">
                <h2>📈 通过/失败对比</h2>
                <div id="barChart" class="chart"></div>
            </div>

            <div class="chart-container">
                <h2>🎯 P-Value 与显著水平对比</h2>
                <div id="thresholdChart" class="chart"></div>
            </div>
        </div>

        %s

        <div class="chart-container full-width">
            <h2>📋 详细测试结果</h2>
            <div class="table-scroll">
                <table class="details-table">
                    <thead>
                        <tr>
                            <th>测试名称</th>
                            <th>P-Value</th>
                            <th>状态</th>
                            <th>统计量</th>
                            <th>详细信息</th>
                        </tr>
                    </thead>
                    <tbody id="resultsTableBody">
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">
            <p>NIST SP 800-22 随机性测试套件 | 基于 Go 实现 | %s</p>
        </div>
    </div>

    <script>
        const results = %s;
        const alpha = %.6f;

        function generateCharts() {
            const testNames = results.map(r => r.display_name);
            const pValues = results.map(r => r.p_value);
            const passed = results.filter(r => r.passed).length;
            const failed = results.length - passed;
            const statuses = results.map(r => r.passed ? '通过' : '失败');
            const colors = results.map(r => r.p_value >= alpha ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)');
            const borderColors = results.map(r => r.p_value >= alpha ? '#10b981' : '#ef4444');

            // P-Value 分布柱状图
            const pvalueTrace = {
                x: testNames,
                y: pValues,
                type: 'bar',
                marker: {
                    color: colors,
                    line: { color: borderColors, width: 2 }
                },
                text: pValues.map(v => v.toFixed(6)),
                textposition: 'auto',
                hovertemplate: '<b>%%{x}</b><br>P-Value: %%{y:.6f}<extra></extra>'
            };

            const thresholdLine = {
                type: 'line',
                x0: -0.5,
                y0: alpha,
                x1: testNames.length - 0.5,
                y1: alpha,
                line: {
                    color: '#f59e0b',
                    width: 2,
                    dash: 'dash'
                },
                name: '显著水平 (α=' + alpha + ')'
            };

            const pvalueLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: {
                    tickangle: -45,
                    tickfont: { size: 10 }
                },
                yaxis: {
                    title: 'P-Value',
                    range: [0, 1],
                    gridcolor: '#e5e7eb'
                },
                showlegend: true,
                legend: { x: 1, y: 1 },
                margin: { b: 150, t: 20 },
                shapes: [thresholdLine],
                annotations: [{
                    x: testNames.length - 1,
                    y: alpha + 0.02,
                    xref: 'x',
                    yref: 'y',
                    text: '显著水平 α=' + alpha,
                    showarrow: false,
                    font: { color: '#f59e0b', size: 12 }
                }]
            };

            Plotly.newPlot('pvalueChart', [pvalueTrace], pvalueLayout, { responsive: true, displayModeBar: true });

            // 饼图
            const pieTrace = {
                values: [passed, failed],
                labels: ['通过', '失败'],
                type: 'pie',
                marker: {
                    colors: ['#10b981', '#ef4444']
                },
                textinfo: 'label+percent+value',
                hole: 0.4,
                hovertemplate: '<b>%%{label}</b><br>数量: %%{value}<br>百分比: %%{percent}<extra></extra>'
            };

            const pieLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { t: 20 },
                annotations: [{
                    text: passed + '/' + results.length,
                    showarrow: false,
                    font: { size: 24 }
                }]
            };

            Plotly.newPlot('pieChart', [pieTrace], pieLayout, { responsive: true, displayModeBar: true });

            // 横向柱状图
            const barTrace = {
                y: testNames,
                x: pValues,
                type: 'bar',
                orientation: 'h',
                marker: {
                    color: colors,
                    line: { color: borderColors, width: 2 }
                },
                text: pValues.map(v => v.toFixed(6)),
                textposition: 'auto',
                hovertemplate: '<b>%%{y}</b><br>P-Value: %%{x:.6f}<extra></extra>'
            };

            const vline = {
                type: 'line',
                x0: alpha,
                y0: -0.5,
                x1: alpha,
                y1: testNames.length - 0.5,
                line: {
                    color: '#f59e0b',
                    width: 2,
                    dash: 'dash'
                }
            };

            const barLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: {
                    title: 'P-Value',
                    range: [0, 1],
                    gridcolor: '#e5e7eb'
                },
                yaxis: {
                    tickfont: { size: 10 }
                },
                margin: { l: 200, t: 20 },
                shapes: [vline]
            };

            Plotly.newPlot('barChart', [barTrace], barLayout, { responsive: true, displayModeBar: true });

            // 阈值对比图
            const sortedPValues = [...pValues].sort((a, b) => b - a);
            const sortedNames = [...results].sort((a, b) => b.p_value - a.p_value).map(r => r.display_name);

            const sortedColors = sortedPValues.map(v => v >= alpha ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)');

            const trace1 = {
                x: sortedNames,
                y: sortedPValues,
                mode: 'lines+markers',
                name: 'P-Value',
                line: { color: '#3b82f6', width: 3 },
                marker: {
                    color: sortedColors,
                    size: 10,
                    line: { color: '#1f2937', width: 2 }
                }
            };

            const trace2 = {
                x: sortedNames,
                y: new Array(sortedNames.length).fill(alpha),
                mode: 'lines',
                name: '显著水平 α',
                line: { color: '#f59e0b', width: 2, dash: 'dash' }
            };

            const thresholdLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                xaxis: {
                    tickangle: -45,
                    tickfont: { size: 10 }
                },
                yaxis: {
                    title: 'P-Value',
                    range: [0, 1],
                    gridcolor: '#e5e7eb'
                },
                margin: { b: 150, t: 20 },
                showlegend: true
            };

            Plotly.newPlot('thresholdChart', [trace1, trace2], thresholdLayout, { responsive: true, displayModeBar: true });

            // 填充表格
            const tableBody = document.getElementById('resultsTableBody');
            results.forEach(r => {
                const row = document.createElement('tr');
                const pValueClass = r.p_value >= alpha ? 'status-passed' : 'status-failed';
                const pValueText = r.p_value === 0 && r.details.startsWith('ERROR:') ? 'ERROR' : r.p_value.toFixed(6);
                const statusText = r.p_value === 0 && r.details.startsWith('ERROR:') ? 'ERROR' : (r.passed ? '通过' : '失败');
                const statusClass = r.p_value === 0 && r.details.startsWith('ERROR:') ? 'status-error' : pValueClass;
                const barColor = r.p_value >= alpha ? '#10b981' : '#ef4444';
                const barWidth = Math.max(5, r.p_value * 100);

                row.innerHTML = `
                    <td><strong>${r.display_name}</strong><br><small style="color:#666">${r.name}</small></td>
                    <td>
                        ${pValueText}
                        <div class="pvalue-bar"><div class="pvalue-fill" style="width:${barWidth}%%;background:${barColor}"></div></div>
                    </td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td>${r.statistic ? r.statistic.toFixed(4) : '-'}</td>
                    <td><small style="color:#666">${r.details || '-'}</small></td>
                `;
                tableBody.appendChild(row);
            });
        }

        window.addEventListener('load', generateCharts);
    </script>
</body>
</html>`,
		report.Timestamp.Format("2006-01-02 15:04:05"),
		report.Timestamp.Format("2006-01-02 15:04:05"),
		report.InputType,
		report.InputSource,
		truncateString(report.InputSource, 30),
		report.BitLength,
		report.SignificanceLevel,
		report.Parallelism,
		report.Duration.Seconds(),
		len(report.Results),
		report.Passed,
		report.Failed,
		map[bool]string{true: "overall-passed", false: "overall-failed"}[report.OverallPassed],
		map[bool]string{true: "通过 ✅", false: "失败 ❌"}[report.OverallPassed],
		generateCorrectionsHTML(data.Corrections),
		report.Timestamp.Format(time.RFC3339),
		string(jsonResults),
		report.SignificanceLevel,
	)

	_, err := io.WriteString(w, html)
	return err
}

func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

func generateCorrectionsHTML(corrections []config.ParameterRecommendation) string {
	if len(corrections) == 0 {
		return ""
	}

	var items []string
	for _, c := range corrections {
		statusClass := "ok"
		icon := "✅"
		message := "参数验证通过"
		if !c.Validated && c.Reason != "" {
			statusClass = "warning"
			icon = "⚠️"
			message = c.Reason
		}

		var recText string
		if c.Recommended > 0 && c.CurrentValue != c.Recommended {
			recText = fmt.Sprintf(" (建议值: %d)", c.Recommended)
		}

		item := fmt.Sprintf(`
			<div class="correction-item %s">
				<strong>%s [%s]</strong> - %s
				<br>
				<small style="opacity:0.8">当前值: %d%s | %s</small>
			</div>
		`, statusClass, icon, c.TestName, message, c.CurrentValue, recText, c.ParameterName)
		items = append(items, item)
	}

	return fmt.Sprintf(`
		<div class="corrections-section full-width">
			<h2>⚙️ 参数校正与验证</h2>
			%s
		</div>
	`, strings.Join(items, ""))
}

func SaveHTMLReport(data *VisualReportData, path string) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return GenerateHTMLReport(data, f)
}
