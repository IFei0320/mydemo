var chartDom = document.getElementById('part3');
var myChart = echarts.init(chartDom);
var currentChartType = 'line';
var chartMode = window.part3Config.chartMode;
var selectedProvince = window.part3Config.selectedProvince;

var nameList = window.part3Config.nameList;
var valueList = (window.part3Config.valueList).map(function (v) { return Number(v); });

function calculateStats(values) {
    if (!values || values.length === 0) {
        $('#avgPrice').text('-');
        $('#maxPrice').text('-');
        $('#minPrice').text('-');
        $('#priceRange').text('-');
        return;
    }

    var sum = values.reduce(function (a, b) { return a + b; }, 0);
    var avg = (sum / values.length).toFixed(2);
    var max = Math.max(...values);
    var min = Math.min(...values);
    var range = max - min;

    $('#avgPrice').text('¥' + avg);
    $('#maxPrice').text('¥' + Number(max).toFixed(2));
    $('#minPrice').text('¥' + Number(min).toFixed(2));
    $('#priceRange').text('¥' + range.toFixed(2));
}

if (nameList.length === 0) {
    $('#noDataAlert').removeClass('d-none');
} else {
    calculateStats(valueList);
}

function fillTable(names, values) {
    var tbody = $('#priceTableBody');
    tbody.empty();

    var data = names.map(function(name, index) {
        return { name: name, value: values[index] };
    });
    data.sort(function(a, b) { return b.value - a.value; });

    data.forEach(function(item, index) {
        var level = '';
        var badgeClass = '';

        if (item.value > 200) {
            level = '高价';
            badgeClass = 'tag-rose';
        } else if (item.value >= 100) {
            level = '中价';
            badgeClass = 'tag-amber';
        } else {
            level = '低价';
            badgeClass = 'tag-teal';
        }

        var row = $('<tr></tr>');
        row.append('<td style="text-align: center;"><span class="table-rank">' + (index + 1) + '</span></td>');
        row.append('<td class="spot-name">' + item.name + '</td>');
        row.append('<td style="text-align: right;"><span class="price-value">¥' + Number(item.value).toFixed(2) + '</span></td>');
        row.append('<td style="text-align: center;"><span class="table-tag ' + badgeClass + '">' + level + '</span></td>');

        tbody.append(row);
    });
}

if (nameList.length > 0) {
    fillTable(nameList, valueList);
}

function getOption(type) {
    var isLine = type === 'line';

    return {
        backgroundColor: 'transparent',
        title: {
            text: chartMode === 'summary' ? '各省份平均门票价格对比' : (selectedProvince ? selectedProvince + ' - 景点门票价格分布' : '景点门票价格分布'),
            subtext: chartMode === 'summary' ? '按省份聚合的平均票价对比' : '数据更新时间：' + new Date().toLocaleString(),
            left: 'center',
            top: 20,
            textStyle: { fontSize: 20, fontWeight: '600', color: '#4a4a6a' },
            subtextStyle: { fontSize: 12, color: '#8a8aae' }
        },
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(255, 255, 255, 0.85)',
            borderColor: 'rgba(255, 255, 255, 0.5)',
            borderWidth: 1,
            textStyle: { color: '#4a4a6a', fontSize: 14 },
            extraCssText: 'backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15); border-radius: 12px;',
            formatter: function(params) {
                var value = params[0].value;
                var level = value > 200 ? '高价区' : (value >= 100 ? '中价区' : '低价区');
                var color = value > 200 ? '#E8A0BF' : (value >= 100 ? '#F0D78C' : '#7EC8B8');
                var labelPrefix = chartMode === 'summary' ? '平均门票价格' : '门票价格';

                return (
                    '<div style="padding: 10px;">' +
                    '<div style="font-weight: 600; font-size: 15px; color: #4a4a6a; margin-bottom: 8px;">' + params[0].name + '</div>' +
                    '<div style="color: #6b6b8a; margin-bottom: 5px;">' +
                    labelPrefix + '：<span style="color: ' + color + '; font-weight: 600; font-size: 17px;">¥' + value + '</span>' +
                    '</div>' +
                    '<div style="color: #6b6b8a;">' +
                    '价格等级：<span style="color: ' + color + '; font-weight: 600;">' + level + '</span>' +
                    '</div>' +
                    '</div>'
                );
            }
        },
        toolbox: {
            feature: {
                dataView: { show: true, readOnly: false, title: '数据视图', lang: ['数据视图', '关闭', '刷新'] },
                magicType: { show: true, type: ['line', 'bar'], title: { line: '切换为折线图', bar: '切换为柱状图' } },
                restore: { show: true, title: '还原' },
                saveAsImage: { show: true, title: '保存为图片' }
            },
            iconStyle: { borderColor: '#a0a0c0' },
            right: 30,
            top: 20
        },
        grid: { left: '3%', right: '4%', bottom: '15%', top: '20%', containLabel: true },
        xAxis: {
            type: 'category',
            data: nameList,
            axisLine: { lineStyle: { color: 'rgba(150, 150, 180, 0.3)' } },
            axisLabel: { color: '#6b6b8a', fontSize: 12, rotate: 45, interval: 0 },
            axisTick: { alignWithLabel: true }
        },
        yAxis: {
            type: 'value',
            name: chartMode === 'summary' ? '平均价格 (元)' : '价格 (元)',
            nameTextStyle: { color: '#8a8aae', fontSize: 14 },
            axisLine: { lineStyle: { color: 'rgba(150, 150, 180, 0.3)' } },
            axisLabel: { color: '#8a8aae', formatter: '¥{value}' },
            splitLine: { lineStyle: { color: 'rgba(150, 150, 180, 0.15)', type: 'dashed' } }
        },
        dataZoom: [
            { type: 'inside', start: 0, end: 100 },
            {
                start: 0, end: 100, height: 30, bottom: 20,
                handleIcon: 'path://M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
                handleSize: '80%',
                handleStyle: { color: '#fff', shadowBlur: 3, shadowColor: 'rgba(0, 0, 0, 0.6)', shadowOffsetX: 2, shadowOffsetY: 2 },
                textStyle: { color: '#6b6b8a' },
                borderColor: 'rgba(150,150,180,0.2)',
                fillerColor: 'rgba(123,140,222,0.15)'
            }
        ],
        visualMap: {
            show: false,
            pieces: [
                {gt: 200, color: '#E8A0BF'},
                {gt: 100, lte: 200, color: '#F0D78C'},
                {lte: 100, color: '#7EC8B8'}
            ],
            outOfRange: { color: '#999' }
        },
        series: [
            {
                name: '门票价格',
                type: type,
                data: valueList,
                smooth: isLine,
                symbol: 'circle',
                symbolSize: 10,
                lineStyle: isLine ? {
                    width: 4,
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: '#A0B4F0' },
                        { offset: 1, color: '#BB9AB1' }
                    ]),
                    shadowColor: 'rgba(160, 180, 240, 0.3)',
                    shadowBlur: 10,
                    shadowOffsetY: 5
                } : undefined,
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#A0B4F0' },
                        { offset: 1, color: '#BB9AB1' }
                    ]),
                    borderRadius: isLine ? undefined : [8, 8, 0, 0]
                },
                areaStyle: isLine ? {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(160, 180, 240, 0.25)' },
                        { offset: 1, color: 'rgba(187, 154, 177, 0.05)' }
                    ])
                } : undefined,
                emphasis: {
                    itemStyle: {
                        color: '#E8A0BF',
                        borderColor: '#fff',
                        borderWidth: 2,
                        shadowBlur: 10,
                        shadowColor: 'rgba(0, 0, 0, 0.15)'
                    },
                    scale: true
                },
                markLine: {
                    silent: true,
                    lineStyle: { color: 'rgba(150,150,180,0.5)', type: 'dashed' },
                    label: { color: '#8a8aae', fontSize: 11 },
                    data: [
                        { yAxis: 100, label: { formatter: '低价线 ¥100', position: 'end' } },
                        { yAxis: 200, label: { formatter: '中价线 ¥200', position: 'end' } }
                    ]
                },
                markPoint: {
                    data: [
                        { type: 'max', name: '最高价' },
                        { type: 'min', name: '最低价' },
                        { type: 'average', name: '平均值' }
                    ],
                    itemStyle: { color: '#E8A0BF' },
                    label: { color: '#fff', fontWeight: '500' }
                }
            }
        ]
    };
}

var option = {};
if (nameList.length > 0) {
    option = getOption('line');
    myChart.setOption(option);
}

function toggleChartType() {
    if (nameList.length === 0) return;
    currentChartType = currentChartType === 'line' ? 'bar' : 'line';
    myChart.clear();
    myChart.setOption(getOption(currentChartType));
}

function downloadChart() {
    var url = myChart.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff'
    });
    var link = document.createElement('a');
    link.download = '景点价格分析_' + new Date().toLocaleDateString() + '.png';
    link.href = url;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

window.addEventListener('resize', function() {
    myChart.resize();
});
