import React, { useEffect, useRef, useState } from 'react';
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

/** Loading skeleton shown while chart is initializing */
const ChartSkeleton: React.FC = () => (
  <div className="animate-pulse rounded-lg bg-gray-100 p-4" style={{ height: '400px' }}>
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <div className="flex items-center gap-2">
        <svg className="w-5 h-5 text-blue-500 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <span className="text-sm text-gray-400 font-medium">正在生成图表...</span>
      </div>
      <div className="w-3/4 h-3 bg-gray-200 rounded" />
      <div className="w-1/2 h-3 bg-gray-200 rounded" />
      <div className="w-2/3 h-40 bg-gray-200 rounded" />
    </div>
  </div>
);

export const ChartRenderer: React.FC<ChartRendererProps> = ({ chartData }) => {
  const [ready, setReady] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  // Show skeleton briefly then fade in chart
  useEffect(() => {
    setReady(false);
    const timer = setTimeout(() => setReady(true), 600);
    return () => clearTimeout(timer);
  }, [chartData.id]);

  useEffect(() => {
    if (!ready || !chartRef.current) return;

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
  }, [ready, chartData]);

  useEffect(() => {
    return () => {
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, []);

  if (!ready) {
    return <ChartSkeleton />;
  }

  return (
    <div className="animate-[fadeIn_400ms_ease-out]">
      <div
        ref={chartRef}
        style={{ width: '100%', height: '400px', minHeight: '300px' }}
      />
    </div>
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
          type: 'pie', radius: ['40%', '70%'],
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
