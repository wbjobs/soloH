import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { SpectrumPoint } from '@/types';
import { bandgapToCutoffWavelength } from '@/utils/physics/blackbody';

interface BlackbodySpectrumChartProps {
  data: SpectrumPoint[];
  bandgap?: number;
  width?: number;
  height?: number;
}

export function BlackbodySpectrumChart({ 
  data, 
  bandgap,
  width = 800, 
  height = 350 
}: BlackbodySpectrumChartProps) {
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
      .domain([200, d3.max(data, d => d.wavelength) || 5000])
      .range([0, innerWidth])
      .nice();

    const yScale = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.intensity) || 1])
      .range([innerHeight, 0])
      .nice();

    const colorScale = d3.scaleLinear<string>()
      .domain([400, 500, 600, 700, 800])
      .range(['#8B5CF6', '#3B82F6', '#10B981', '#F59E0B', '#EF4444'])
      .clamp(true);

    const area = d3.area<SpectrumPoint>()
      .x(d => xScale(d.wavelength))
      .y0(innerHeight)
      .y1(d => yScale(d.intensity))
      .curve(d3.curveMonotoneX);

    const gradient = svg.append('defs')
      .append('linearGradient')
      .attr('id', 'spectrum-gradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '100%')
      .attr('y2', '0%');

    gradient.append('stop').attr('offset', '0%').attr('stop-color', '#8B5CF6').attr('stop-opacity', 0.8);
    gradient.append('stop').attr('offset', '25%').attr('stop-color', '#3B82F6').attr('stop-opacity', 0.8);
    gradient.append('stop').attr('offset', '50%').attr('stop-color', '#10B981').attr('stop-opacity', 0.8);
    gradient.append('stop').attr('offset', '75%').attr('stop-color', '#F59E0B').attr('stop-opacity', 0.8);
    gradient.append('stop').attr('offset', '100%').attr('stop-color', '#EF4444').attr('stop-opacity', 0.8);

    mainGroup.append('path')
      .datum(data)
      .attr('fill', 'url(#spectrum-gradient)')
      .attr('d', area)
      .attr('opacity', 0.3);

    const line = d3.line<SpectrumPoint>()
      .x(d => xScale(d.wavelength))
      .y(d => yScale(d.intensity))
      .curve(d3.curveMonotoneX);

    mainGroup.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#165DFF')
      .attr('stroke-width', 2)
      .attr('d', line);

    if (bandgap) {
      const cutoffWavelength = bandgapToCutoffWavelength(bandgap);
      
      mainGroup.append('line')
        .attr('x1', xScale(cutoffWavelength))
        .attr('y1', 0)
        .attr('x2', xScale(cutoffWavelength))
        .attr('y2', innerHeight)
        .attr('stroke', '#FF7D00')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '5,5');

      mainGroup.append('text')
        .attr('x', xScale(cutoffWavelength) + 5)
        .attr('y', 20)
        .attr('fill', '#FF7D00')
        .attr('font-size', '12px')
        .attr('font-family', 'JetBrains Mono, monospace')
        .text(`λ_cutoff = ${cutoffWavelength.toFixed(0)} nm`);
    }

    const xAxis = d3.axisBottom(xScale)
      .tickFormat(d => `${d}`);

    const yAxis = d3.axisLeft(yScale)
      .ticks(5)
      .tickFormat(d => d3.format('.2e')(d));

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
      .attr('y', -50)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94A3B8')
      .attr('font-size', '13px')
      .text('光谱辐射度 (W/m²/nm/sr)');

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

    const bisect = d3.bisector<SpectrumPoint, number>(d => d.wavelength).left;
    
    const tooltip = mainGroup.append('g')
      .attr('display', 'none');

    tooltip.append('line')
      .attr('class', 'tooltip-line')
      .attr('y1', 0)
      .attr('y2', innerHeight)
      .attr('stroke', '#FF7D00')
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '3,3');

    tooltip.append('circle')
      .attr('class', 'tooltip-circle')
      .attr('r', 5)
      .attr('fill', '#FF7D00')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2);

    const tooltipRect = tooltip.append('rect')
      .attr('class', 'tooltip-bg')
      .attr('width', 180)
      .attr('height', 50)
      .attr('rx', 8)
      .attr('fill', '#1E293B')
      .attr('stroke', '#334155')
      .attr('opacity', 0.95);

    const tooltipText1 = tooltip.append('text')
      .attr('class', 'tooltip-text')
      .attr('x', 10)
      .attr('y', 20)
      .attr('fill', '#E2E8F0')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace');

    const tooltipText2 = tooltip.append('text')
      .attr('class', 'tooltip-text')
      .attr('x', 10)
      .attr('y', 38)
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
        const d = x0 - d0.wavelength > d1.wavelength - x0 ? d1 : d0;

        tooltip.attr('transform', `translate(${xScale(d.wavelength)},0)`);
        tooltip.select('.tooltip-circle').attr('cy', yScale(d.intensity));
        
        const tooltipX = xScale(d.wavelength) + 10;
        const bgX = tooltipX > innerWidth - 190 ? -195 : 10;
        
        tooltipRect.attr('x', bgX);
        tooltipText1.attr('x', bgX + 10).text(`λ = ${d.wavelength.toFixed(0)} nm`);
        tooltipText2.attr('x', bgX + 10).text(`I = ${d3.format('.2e')(d.intensity)}`);
      });

  }, [data, bandgap, width, height]);

  return (
    <svg 
      ref={svgRef} 
      width={width} 
      height={height}
      className="w-full h-auto"
    />
  );
}
