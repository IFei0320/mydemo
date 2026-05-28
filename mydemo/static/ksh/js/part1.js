// Chart 1: Pie Chart - 景点评分分布
    var chartDom1 = document.getElementById('part1');
    var myChart1 = echarts.init(chartDom1);

    var option1 = {
        backgroundColor: 'transparent',
        title: {
            text: '评分占比分析',
            subtext: '数据驱动决策',
            left: 'center',
            top: 20,
            textStyle: {
                color: '#4a4a6a',
                fontSize: 18,
                fontWeight: '600'
            },
            subtextStyle: {
                color: '#8a8aae',
                fontSize: 13
            }
        },
        tooltip: {
            trigger: 'item',
            formatter: '{a} <br/>{b}: {c} ({d}%)',
            backgroundColor: 'rgba(255, 255, 255, 0.85)',
            borderColor: 'rgba(255, 255, 255, 0.5)',
            borderWidth: 1,
            textStyle: { color: '#4a4a6a' },
            extraCssText: 'backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15); border-radius: 12px;'
        },
        legend: {
            orient: 'vertical',
            left: 'left',
            top: 'middle',
            textStyle: { color: '#6b6b8a', fontSize: 12 },
            itemGap: 15,
            backgroundColor: 'rgba(255,255,255,0.35)',
            padding: 15,
            borderRadius: 12,
            borderColor: 'rgba(255,255,255,0.5)',
            borderWidth: 1
        },
        series: [{
            name: '评分',
            type: 'pie',
            selectedMode: 'single',
            selectedOffset: 30,
            clockwise: true,
            radius: ['40%', '70%'],
            center: ['60%', '55%'],
            avoidLabelOverlap: false,
            itemStyle: {
                borderRadius: 10,
                borderColor: 'rgba(255,255,255,0.7)',
                borderWidth: 2
            },
            label: {
                show: true,
                fontSize: 13,
                fontWeight: '500',
                color: '#4a4a6a',
                formatter: '{b}\n{d}%',
                lineHeight: 18
            },
            emphasis: {
                label: {
                    show: true,
                    fontSize: 15,
                    fontWeight: '600',
                    color: '#7B8CDE'
                },
                itemStyle: {
                    shadowBlur: 20,
                    shadowOffsetX: 0,
                    shadowColor: 'rgba(0, 0, 0, 0.15)'
                }
            },
            labelLine: {
                show: true,
                lineStyle: { color: 'rgba(150,150,180,0.4)' }
            },
            data: window.part1Config.dataList,
            color: ['#A0B4F0', '#A0D2DB', '#F7C5CC', '#D4A5D9', '#9FB4CC', '#BB9AB1', '#F0D78C', '#B8D4C8', '#C5B8E0']
        }]
    };

    myChart1.setOption(option1);
    window.addEventListener('resize', function() { myChart1.resize(); });

// Chart 2: Mixed Chart - 各省份景点平均评分
    var chartDom8 = document.getElementById('part8');
    var myChart8 = echarts.init(chartDom8);

    var option8 = {
        backgroundColor: 'transparent',
        title: {
            text: '省份旅游数据对比',
            subtext: '数量与质量双维度分析',
            left: 'center',
            top: 20,
            textStyle: { color: '#4a4a6a', fontSize: 18, fontWeight: '600' },
            subtextStyle: { color: '#8a8aae', fontSize: 13 }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                crossStyle: { color: 'rgba(150,150,180,0.3)' }
            },
            backgroundColor: 'rgba(255, 255, 255, 0.85)',
            borderColor: 'rgba(255, 255, 255, 0.5)',
            borderWidth: 1,
            textStyle: { color: '#4a4a6a' },
            extraCssText: 'backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15); border-radius: 12px;'
        },
        toolbox: {
            feature: {
                dataView: { show: true, readOnly: false, title: '数据视图', lang: ['数据视图', '关闭', '刷新'], textStyle: { color: '#4a4a6a' }, buttonColor: '#7B8CDE', buttonTextColor: '#fff' },
                magicType: { show: true, type: ['line', 'bar'], title: { line: '切换为折线', bar: '切换为柱状' } },
                restore: { show: true, title: '还原' },
                saveAsImage: { show: true, title: '保存为图片' }
            },
            iconStyle: { borderColor: '#a0a0c0' },
            right: 20,
            top: 20
        },
        legend: {
            data: ['景点数量', '平均评分'],
            top: 70,
            textStyle: { color: '#6b6b8a', fontSize: 14 },
            itemGap: 20
        },
        grid: { left: '3%', right: '4%', bottom: '15%', top: '20%', containLabel: true },
        xAxis: [{
            type: 'category',
            data: window.part1Config.nameList,
            axisPointer: { type: 'shadow' },
            axisLine: { lineStyle: { color: 'rgba(150,150,180,0.3)' } },
            axisLabel: { color: '#6b6b8a', fontSize: 12, rotate: 45, interval: 0 },
            axisTick: { alignWithLabel: true }
        }],
        yAxis: [
            {
                type: 'value',
                name: '景点数量',
                min: 0, max: 300, interval: 50,
                nameTextStyle: { color: '#8a8aae', fontSize: 13 },
                axisLabel: { formatter: '{value}', color: '#8a8aae' },
                axisLine: { lineStyle: { color: 'rgba(150,150,180,0.3)' } },
                splitLine: { lineStyle: { color: 'rgba(150,150,180,0.15)', type: 'dashed' } }
            },
            {
                type: 'value',
                name: '平均评分',
                min: 0, max: 5, interval: 1,
                nameTextStyle: { color: '#8a8aae', fontSize: 13 },
                axisLabel: { formatter: '{value}', color: '#8a8aae' },
                axisLine: { lineStyle: { color: 'rgba(150,150,180,0.3)' } },
                splitLine: { show: false }
            }
        ],
        dataZoom: [
            { type: 'inside', start: 0, end: 100 },
            {
                start: 0, end: 100,
                handleIcon: 'path://M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
                handleSize: '80%',
                handleStyle: { color: '#fff', shadowBlur: 3, shadowColor: 'rgba(0, 0, 0, 0.6)', shadowOffsetX: 2, shadowOffsetY: 2 },
                textStyle: { color: '#6b6b8a' },
                borderColor: 'rgba(150,150,180,0.2)',
                fillerColor: 'rgba(123,140,222,0.15)'
            }
        ],
        series: [
            {
                name: '景点数量',
                type: 'bar',
                barWidth: '40%',
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#A0B4F0' },
                        { offset: 0.5, color: '#7B8CDE' },
                        { offset: 1, color: '#7B8CDE' }
                    ]),
                    borderRadius: [6, 6, 0, 0],
                    shadowColor: 'rgba(123, 140, 222, 0.25)',
                    shadowBlur: 8,
                    shadowOffsetY: 4
                },
                emphasis: {
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#7B8CDE' },
                            { offset: 0.7, color: '#7B8CDE' },
                            { offset: 1, color: '#A0B4F0' }
                        ]),
                        shadowColor: 'rgba(123, 140, 222, 0.4)',
                        shadowBlur: 12
                    }
                },
                tooltip: { valueFormatter: function (value) { return value + ' 个'; } },
                data: window.part1Config.travelNumList,
                animationDelay: function (idx) { return idx * 50; }
            },
            {
                name: '平均评分',
                type: 'line',
                yAxisIndex: 1,
                smooth: true,
                symbol: 'circle',
                symbolSize: 10,
                lineStyle: {
                    width: 4,
                    color: '#E8A0BF',
                    shadowColor: 'rgba(232, 160, 191, 0.4)',
                    shadowBlur: 10
                },
                itemStyle: {
                    color: '#E8A0BF',
                    borderColor: '#fff',
                    borderWidth: 2,
                    shadowColor: 'rgba(232, 160, 191, 0.3)',
                    shadowBlur: 6
                },
                emphasis: {
                    scale: 1.5,
                    itemStyle: { shadowBlur: 12, shadowColor: 'rgba(232, 160, 191, 0.5)' }
                },
                tooltip: { valueFormatter: function (value) { return value + ' 分'; } },
                data: window.part1Config.avgScoreList,
                animationDelay: 500
            }
        ]
    };

    myChart8.setOption(option8);
    window.addEventListener('resize', function() { myChart8.resize(); });
