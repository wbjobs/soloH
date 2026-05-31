import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { QEPoint, ReflectancePoint } from '@/types';

interface QuantumEfficiencyChartProps {
  qeData: QEPoint[];
  reflectanceData?: ReflectancePoint[];
  width?: number;
  height?: number;
}

export function QuantumEfficiencyChart({ 
  qeData, 
  reflectanceData,
  width = 800, 
  height = 350 
}: QuantumEfficiencyChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || qeData.length === 0) return;

    const margin = { top: 20, right: 30, bottom: 50, left: 70 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const mainGroup = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3.scaleLinear()
      .domain([200, d3.max(qeData, d => d.wavelength) || 5000])
      .range([0, innerWidth])
      .nice();

    const yScale = d3.scaleLinear()
      .domain([0, 1])
      .range([innerHeight, 0]);

    if (reflectanceData && reflectanceData.length > 0) {
      const refLine = d3.line<ReflectancePoint>()
        .x(d => xScale(d.wavelength))
        .y(d => yScale(d.r))
        .curve(d3.curveMonotoneX);

      mainGroup.append('path')
        .datum(reflectanceData)
        .attr('fill', 'none')
        .attr('stroke', '#F59E0B')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '4,4')
        .attr('d', refLine);

      mainGroup.append('circle')
        .attr('cx', innerWidth - 150)
        .attr('cy', 10)
        .attr('r', 4)
        .attr('fill', '#F59E0B');

      mainGroup.append('text')
        .attr('x', innerWidth - 140)
        .attr('y', 14)
        .attr('fill', '#94A3B8')
        .attr('font-size', '11px')
        .text('反射率');
    }

    const qeArea = d3.area<QEPoint>()
      .x(d => xScale(d.wavelength))
      .y0(innerHeight)
      .y1(d => yScale(d.eqe))
      .curve(d3.curveMonotoneX);

    const qeGradient = svg.append('defs')
      .append('linearGradient')
      .attr('id', 'qe-gradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '0%')
      .attr('y2', '100%');

    qeGradient.append('stop').attr('offset', '0%').attr('stop-color', '#10B981').attr('stop-opacity', 0.5);
    qeGradient.append('stop').attr('offset', '100%').attr('stop-color', '#10B981').attr('stop-opacity', 0.05);

    mainGroup.append('path')
      .datum(qeData)
      .attr('fill', 'url(#qe-gradient)')
      .attr('d', qeArea);

    const qeLine = d3.line<QEPoint>()
      .x(d => xScale(d.wavelength))
      .y(d => yScale(d.eqe))
      .curve(d3.curveMonotoneX);

    mainGroup.append('path')
      .datum(qeData)
      .attr('fill', 'none')
      .attr('stroke', '#10B981')
      .attr('stroke-width', 2.5)
      .attr('d', qeLine);

    mainGroup.append('circle')
      .attr('cx', innerWidth - 150)
      .attr('cy', 30)
      .attr('r', 4)
      .attr('fill', '#10B981');

    mainGroup.append('text')
      .attr('x', innerWidth - 140)
      .attr('y', 34)
      .attr('fill', '#94A3B8')
      .attr('font-size', '11px')
      .text('外量子效率');

    const xAxis = d3.axisBottom(xScale)
      .ticks(8)
      .tickFormat(d => `${d}`);

    const yAxis = d3.axisLeft(yScale)
      .ticks(5)
      .tickFormat(d => `${((d as number) * 100).toFixed(0)}%`);

    mainGroup.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis)
      .attr('color', '#94A3B8')
      .selectAll('text')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-size', '11px');

    mainGroup.append('g')
      .call(yAxis)
      .attr('color', '#94A3B8')
      .selectAll('text')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-size', '11px');

    mainGroup.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 40)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94A3B8')
      .attr('font-size', '13px')
      .text('波长 (nm)');

    mainGroup.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -55)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94A3B8')
      .attr('font-size', '13px')
      .text('效率 / 反射率');

    mainGroup.selectAll('.grid')
      .data(yScale.ticks(5))
      .enter()
      .append('line')
      .attr('class', 'grid')
      .attr('x1', 0)
      .attr('x2', innerWidth)
      .attr('y1', d => yScale(d))
      .attr('y2', d => yScale(d))
      .attr('stroke', '#334155')
      .attr('stroke-width', 0.5)
      .attr('stroke-dasharray', '2,2');

  }, [qeData, reflectanceData, width, height]);

  return (
    <svg 
      ref={svgRef} 
      width={width} 
      height={height}
      className="w-full h-auto"
    />
  );
}
