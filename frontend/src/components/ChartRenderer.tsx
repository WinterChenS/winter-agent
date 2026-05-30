import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { LineChart, BarChart, PieChart, ScatterChart } from 'echarts/charts';
import {
  TitleComponent, TooltipComponent, GridComponent, LegendComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { ChartSpecData } from '../types/chat';

echarts.use([
  LineChart, BarChart, PieChart, ScatterChart,
  TitleComponent, TooltipComponent, GridComponent, LegendComponent,
  CanvasRenderer,
]);

interface ChartRendererProps {
  chartData: ChartSpecData;
}

const DEFAULT_COLORS = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272',
  '#fc8452', '#9a60b4', '#ea7ccc',
];

export const ChartRenderer: React.FC<ChartRendererProps> = ({ chartData }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current, undefined, {
        renderer: 'canvas',
      });
    }

    const option = buildEChartsOption(chartData);
    instanceRef.current.setOption(option, true);

    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [chartData]);

  useEffect(() => {
    return () => {
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, []);

  return (
    <div
      ref={chartRef}
      style={{ width: '100%', height: '400px', minHeight: '300px' }}
    />
  );
};

function buildEChartsOption(data: ChartSpecData): echarts.EChartsCoreOption {
  const { chartType, title, data: chartPoints, xAxisLabel, yAxisLabel } = data;

  const groups = new Map<string, number[]>();
  const names: string[] = [];
  const seen = new Set<string>();

  for (const point of chartPoints) {
    if (!seen.has(point.name)) {
      names.push(point.name);
      seen.add(point.name);
    }
    const g = point.group || 'value';
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g)!.push(point.value);
  }

  const baseOption: echarts.EChartsCoreOption = {
    color: DEFAULT_COLORS,
    title: { text: title, left: 'center', textStyle: { fontSize: 16 } },
    tooltip: { trigger: chartType === 'pie' ? 'item' : 'axis' },
    legend: groups.size > 1 ? { bottom: 0 } : undefined,
  };

  switch (chartType) {
    case 'pie':
      return {
        ...baseOption,
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data: chartPoints.map(p => ({ name: p.name, value: p.value })),
          emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } },
        }],
      };

    case 'scatter':
      return {
        ...baseOption,
        xAxis: { type: 'value', name: xAxisLabel },
        yAxis: { type: 'value', name: yAxisLabel },
        series: Array.from(groups.entries()).map(([g, vals]) => ({
          name: g, type: 'scatter',
          data: vals.map((v, i) => [i, v]),
        })),
      };

    case 'area':
      return {
        ...baseOption,
        xAxis: { type: 'category', data: names, name: xAxisLabel },
        yAxis: { type: 'value', name: yAxisLabel },
        series: Array.from(groups.entries()).map(([g, vals]) => ({
          name: g, type: 'line', data: vals, areaStyle: {},
        })),
      };

    case 'radar':
      const maxVal = Math.max(...chartPoints.map(p => p.value)) * 1.2;
      return {
        ...baseOption,
        radar: { indicator: names.map(n => ({ name: n, max: maxVal })) },
        series: Array.from(groups.entries()).map(([g, vals]) => ({
          name: g, type: 'radar', data: [{ value: vals, name: g }],
        })),
      };

    case 'line':
      return {
        ...baseOption,
        xAxis: { type: 'category', data: names, name: xAxisLabel },
        yAxis: { type: 'value', name: yAxisLabel },
        series: Array.from(groups.entries()).map(([g, vals]) => ({
          name: g, type: 'line', data: vals, smooth: true,
        })),
      };

    case 'bar':
    default:
      return {
        ...baseOption,
        xAxis: { type: 'category', data: names, name: xAxisLabel },
        yAxis: { type: 'value', name: yAxisLabel },
        series: Array.from(groups.entries()).map(([g, vals]) => ({
          name: g, type: 'bar', data: vals,
        })),
      };
  }
}
