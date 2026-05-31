import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { IVPoint } from '@/types';

interface IVCurveChartProps {
  data: IVPoint[];
  width?: number;
  height?: number;
  vmp?: number;
  jmp?: number;
}

export function IVCurveChart({ 
  data, 
  width = 800, 
  height = 350,
  vmp,
  jmp
}: IVCurveChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || data.length === 0) return;

    const margin = { top: 20, right: 30, bottom: 50, left: 70 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const mainGroup = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.v) || 1])
      .range([0, innerWidth])
      .nice();

    const yScale = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.j) || 1])
      .range([innerHeight, 0])
      .nice();

    const area = d3.area<IVPoint>()
      .x(d => xScale(d.v))
      .y0(innerHeight)
      .y1(d => yScale(d.j))
      .curve(d3.curveMonotoneX);

    const gradient = svg.append('defs')
      .append('linearGradient')
      .attr('id', 'iv-gradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '0%')
      .attr('y2', '100%');

    gradient.append('stop').attr('offset', '0%').attr('stop-color', '#165DFF').attr('stop-opacity', 0.6);
    gradient.append('stop').attr('offset', '100%').attr('stop-color', '#165DFF').attr('stop-opacity', 0.05);

    mainGroup.append('path')
      .datum(data)
      .attr('fill', 'url(#iv-gradient)')
      .attr('d', area);

    const line = d3.line<IVPoint>()
      .x(d => xScale(d.v))
      .y(d => yScale(d.j))
      .curve(d3.curveMonotoneX);

    mainGroup.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#165DFF')
      .attr('stroke-width', 3)
      .attr('d', line);

    if (vmp !== undefined && jmp !== undefined) {
      mainGroup.append('rect')
        .attr('x', 0)
        .attr('y', yScale(jmp))
        .attr('width', xScale(vmp))
        .attr('height', innerHeight - yScale(jmp))
        .attr('fill', '#FF7D00')
        .attr('opacity', 0.2)
        .attr('stroke', '#FF7D00')
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '3,3');

      mainGroup.append('circle')
        .attr('cx', xScale(vmp))
        .attr('cy', yScale(jmp))
        .attr('r', 6)
        .attr('fill', '#FF7D00')
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);

      mainGroup.append('text')
        .attr('x', xScale(vmp) + 10)
        .attr('y', yScale(jmp) - 10)
        .attr('fill', '#FF7D00')
        .attr('font-size', '11px')
        .attr('font-family', 'JetBrains Mono, monospace')
        .text(`MPP: ${vmp.toFixed(2)}V, ${jmp.toFixed(3)}A/cm²`);
    }

    const xAxis = d3.axisBottom(xScale)
      .ticks(8)
      .tickFormat(d => `${d}`);

    const yAxis = d3.axisLeft(yScale)
      .ticks(5)
      .tickFormat(d => d3.format('.2f')(d));

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
      .text('电压 (V)');

    mainGroup.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -55)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94A3B8')
      .attr('font-size', '13px')
      .text('电流密度 (A/cm²)');

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

    mainGroup.selectAll('.grid-x')
      .data(xScale.ticks(8))
      .enter()
      .append('line')
      .attr('class', 'grid-x')
      .attr('x1', d => xScale(d))
      .attr('x2', d => xScale(d))
      .attr('y1', 0)
      .attr('y2', innerHeight)
      .attr('stroke', '#334155')
      .attr('stroke-width', 0.5)
      .attr('stroke-dasharray', '2,2');

    const bisect = d3.bisector<IVPoint, number>(d => d.v).left;
    
    const tooltip = mainGroup.append('g')
      .attr('display', 'none');

    tooltip.append('line')
      .attr('y1', 0)
      .attr('y2', innerHeight)
      .attr('stroke', '#FF7D00')
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '3,3');

    tooltip.append('circle')
      .attr('r', 5)
      .attr('fill', '#FF7D00')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2);

    const tooltipRect = tooltip.append('rect')
      .attr('width', 140)
      .attr('height', 45)
      .attr('rx', 8)
      .attr('fill', '#1E293B')
      .attr('stroke', '#334155')
      .attr('opacity', 0.95);

    const tooltipText1 = tooltip.append('text')
      .attr('x', 10)
      .attr('y', 18)
      .attr('fill', '#E2E8F0')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace');

    const tooltipText2 = tooltip.append('text')
      .attr('x', 10)
      .attr('y', 35)
      .attr('fill', '#E2E8F0')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace');

    const overlay = mainGroup.append('rect')
      .attr('width', innerWidth)
      .attr('height', innerHeight)
      .attr('fill', 'none')
      .attr('pointer-events', 'all')
      .on('mouseover', () => tooltip.attr('display', null))
      .on('mouseout', () => tooltip.attr('display', 'none'))
      .on('mousemove', function(event) {
        const [mouseX] = d3.pointer(event);
        const x0 = xScale.invert(mouseX);
        const i = bisect(data, x0, 1);
        const d0 = data[i - 1];
        const d1 = data[i] || d0;
        const d = x0 - d0.v > d1.v - x0 ? d1 : d0;

        tooltip.attr('transform', `translate(${xScale(d.v)},0)`);
        tooltip.select('circle').attr('cy', yScale(d.j));
        
        const bgX = xScale(d.v) > innerWidth - 150 ? -150 : 10;
        
        tooltipRect.attr('x', bgX);
        tooltipText1.attr('x', bgX + 10).text(`V = ${d.v.toFixed(2)} V`);
        tooltipText2.attr('x', bgX + 10).text(`J = ${d.j.toFixed(3)} A/cm²`);
      });

  }, [data, width, height, vmp, jmp]);

  return (
    <svg 
      ref={svgRef} 
      width={width} 
      height={height}
      className="w-full h-auto"
    />
  );
}
