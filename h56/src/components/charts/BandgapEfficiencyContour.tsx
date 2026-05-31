import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { BandgapScanResult } from '@/types';

interface BandgapEfficiencyContourProps {
  data: BandgapScanResult;
  currentBandgap?: number;
  currentTemperature?: number;
  width?: number;
  height?: number;
}

export function BandgapEfficiencyContour({ 
  data, 
  currentBandgap,
  currentTemperature,
  width = 800, 
  height = 400 
}: BandgapEfficiencyContourProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data.bandgaps.length || !data.temperatures.length) return;

    const margin = { top: 20, right: 60, bottom: 60, left: 70 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const mainGroup = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3.scaleLinear()
      .domain(d3.extent(data.temperatures) as [number, number])
      .range([0, innerWidth])
      .nice();

    const yScale = d3.scaleLinear()
      .domain(d3.extent(data.bandgaps) as [number, number])
      .range([innerHeight, 0])
      .nice();

    const zMax = d3.max(data.efficiencies.flat()) || 1;
    const zScale = d3.scaleLinear()
      .domain([0, zMax])
      .range([0, 1]);

    const colorScale = d3.scaleSequential<string>()
      .domain([0, zMax])
      .interpolator(d3.interpolateViridis);

    const contours = d3.contours()
      .size([data.temperatures.length, data.bandgaps.length])
      .thresholds(d3.range(0, zMax, zMax / 12))
      (data.efficiencies.flat());

    const xStep = innerWidth / (data.temperatures.length - 1);
    const yStep = innerHeight / (data.bandgaps.length - 1);

    const transformContour = d3.geoTransform({
      point: function(x: number, y: number) {
        this.stream.point(x * xStep, (data.bandgaps.length - 1 - y) * yStep);
      }
    });

    const path = d3.geoPath().projection(transformContour);

    mainGroup.selectAll('.contour')
      .data(contours)
      .enter()
      .append('path')
      .attr('class', 'contour')
      .attr('d', path)
      .attr('fill', d => colorScale(d.value))
      .attr('stroke', 'none')
      .attr('opacity', 0.85);

    mainGroup.selectAll('.contour-line')
      .data(contours.filter((_, i) => i % 2 === 0))
      .enter()
      .append('path')
      .attr('class', 'contour-line')
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', 'rgba(255,255,255,0.3)')
      .attr('stroke-width', 0.5);

    mainGroup.selectAll('.contour-label')
      .data(contours.filter((_, i) => i % 2 === 1))
      .enter()
      .append('text')
      .attr('class', 'contour-label')
      .attr('x', d => {
        const center = d3.geoCentroid(d);
        return center[0] * xStep;
      })
      .attr('y', d => {
        const center = d3.geoCentroid(d);
        return (data.bandgaps.length - 1 - center[1]) * yStep;
      })
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('fill', 'rgba(255,255,255,0.9)')
      .attr('font-size', '10px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .text(d => `${d.value.toFixed(1)}%`);

    if (currentTemperature !== undefined && currentBandgap !== undefined) {
      const xPos = xScale(currentTemperature);
      const yPos = yScale(currentBandgap);

      mainGroup.append('line')
        .attr('x1', xPos)
        .attr('y1', 0)
        .attr('x2', xPos)
        .attr('y2', innerHeight)
        .attr('stroke', '#FF7D00')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '5,5');

      mainGroup.append('line')
        .attr('x1', 0)
        .attr('y1', yPos)
        .attr('x2', innerWidth)
        .attr('y2', yPos)
        .attr('stroke', '#FF7D00')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '5,5');

      mainGroup.append('circle')
        .attr('cx', xPos)
        .attr('cy', yPos)
        .attr('r', 8)
        .attr('fill', '#FF7D00')
        .attr('stroke', '#fff')
        .attr('stroke-width', 3);

      mainGroup.append('text')
        .attr('x', xPos + 15)
        .attr('y', yPos - 15)
        .attr('fill', '#FF7D00')
        .attr('font-size', '12px')
        .attr('font-family', 'JetBrains Mono, monospace')
        .attr('font-weight', 'bold')
        .text('当前参数');
    }

    const xAxis = d3.axisBottom(xScale)
      .ticks(8)
      .tickFormat(d => `${d}`);

    const yAxis = d3.axisLeft(yScale)
      .ticks(6)
      .tickFormat(d => `${d}`);

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
      .attr('y', innerHeight + 45)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94A3B8')
      .attr('font-size', '13px')
      .text('热源温度 (K)');

    mainGroup.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -55)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94A3B8')
      .attr('font-size', '13px')
      .text('带隙 (eV)');

    const legendWidth = 20;
    const legendHeight = innerHeight;
    const legendX = innerWidth + 20;

    const legendGroup = mainGroup.append('g')
      .attr('transform', `translate(${legendX},0)`);

    const legendScale = d3.scaleLinear()
      .domain([0, zMax])
      .range([legendHeight, 0]);

    const legendGradient = svg.append('defs')
      .append('linearGradient')
      .attr('id', 'contour-gradient')
      .attr('x1', '0%')
      .attr('y1', '100%')
      .attr('x2', '0%')
      .attr('y2', '0%');

    for (let i = 0; i <= 10; i++) {
      legendGradient.append('stop')
        .attr('offset', `${i * 10}%`)
        .attr('stop-color', colorScale((i / 10) * zMax));
    }

    legendGroup.append('rect')
      .attr('width', legendWidth)
      .attr('height', legendHeight)
      .attr('fill', 'url(#contour-gradient)')
      .attr('rx', 4);

    const legendAxis = d3.axisRight(legendScale)
      .ticks(5)
      .tickFormat(d => `${(d as number).toFixed(1)}%`);

    legendGroup.append('g')
      .attr('transform', `translate(${legendWidth},0)`)
      .call(legendAxis)
      .attr('color', '#94A3B8')
      .selectAll('text')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-size', '10px');

    legendGroup.append('text')
      .attr('transform', 'rotate(90)')
      .attr('x', legendHeight / 2)
      .attr('y', legendWidth + 30)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94A3B8')
      .attr('font-size', '12px')
      .text('转换效率');

    const bisectX = d3.bisector<number, number>(d => d).left;
    const bisectY = d3.bisector<number, number>(d => d).left;
    
    const tooltip = mainGroup.append('g')
      .attr('display', 'none');

    tooltip.append('rect')
      .attr('width', 160)
      .attr('height', 55)
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

    const tooltipText3 = tooltip.append('text')
      .attr('x', 10)
      .attr('y', 52)
      .attr('fill', '#E2E8F0')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-weight', 'bold');

    const overlay = mainGroup.append('rect')
      .attr('width', innerWidth)
      .attr('height', innerHeight)
      .attr('fill', 'none')
      .attr('pointer-events', 'all')
      .on('mouseover', () => tooltip.attr('display', null))
      .on('mouseout', () => tooltip.attr('display', 'none'))
      .on('mousemove', function(event) {
        const [mouseX, mouseY] = d3.pointer(event);
        
        const temp = xScale.invert(mouseX);
        const bg = yScale.invert(mouseY);
        
        const i = bisectY(data.bandgaps, bg, 1);
        const j = bisectX(data.temperatures, temp, 1);
        
        const d = data.efficiencies[Math.min(i, data.bandgaps.length - 1)][Math.min(j, data.temperatures.length - 1)];
        
        const bgX = mouseX > innerWidth - 170 ? -165 : 10;
        const bgY = mouseY > innerHeight - 65 ? -60 : 10;
        
        tooltip.attr('transform', `translate(${mouseX + bgX},${mouseY + bgY})`);
        tooltipText1.attr('x', bgX + 10).attr('y', bgY + 18).text(`T = ${temp.toFixed(0)} K`);
        tooltipText2.attr('x', bgX + 10).attr('y', bgY + 35).text(`Eg = ${bg.toFixed(2)} eV`);
        tooltipText3.attr('x', bgX + 10).attr('y', bgY + 52).text(`η = ${d.toFixed(2)}%`);
      });

  }, [data, currentBandgap, currentTemperature, width, height]);

  return (
    <svg 
      ref={svgRef} 
      width={width} 
      height={height}
      className="w-full h-auto"
    />
  );
}
