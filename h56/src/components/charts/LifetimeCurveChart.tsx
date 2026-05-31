import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface LifetimePoint {
  temperature: number;
  lifetime: number;
}

interface LifetimeCurveChartProps {
  data: LifetimePoint[];
  currentTemperature: number;
  estimatedLifetime: number;
  activationEnergy: number;
  width?: number;
  height?: number;
}

function formatLifetime(hours: number): string {
  if (hours < 1000) return hours.toFixed(0) + ' 小时';
  if (hours < 8760 * 10) return (hours / 8760).toFixed(1) + ' 年';
  return (hours / 8760).toFixed(0) + ' 年';
}

export function LifetimeCurveChart({
  data,
  currentTemperature,
  estimatedLifetime,
  activationEnergy,
  width = 850,
  height = 350,
}: LifetimeCurveChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const margin = { top: 30, right: 60, bottom: 50, left: 80 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear()
      .domain(d3.extent(data, d => d.temperature) as [number, number])
      .range([0, innerWidth]);

    const y = d3.scaleLog()
      .domain([d3.min(data, d => d.lifetime) * 0.5 || 1, d3.max(data, d => d.lifetime) * 2 || 1e6])
      .range([innerHeight, 0]);

    const gradient = svg.append('defs')
      .append('linearGradient')
      .attr('id', 'lifetimeGradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '100%')
      .attr('y2', '100%');
    gradient.append('stop').attr('offset', '0%').attr('stop-color', '#a855f7');
    gradient.append('stop').attr('offset', '100%').attr('stop-color', '#6366f1');

    const area = d3.area<LifetimePoint>()
      .x(d => x(d.temperature))
      .y0(innerHeight)
      .y1(d => y(d.lifetime))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'url(#lifetimeGradient)')
      .attr('opacity', 0.25)
      .attr('d', area);

    const line = d3.line<LifetimePoint>()
      .x(d => x(d.temperature))
      .y(d => y(d.lifetime))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', 'url(#lifetimeGradient)')
      .attr('stroke-width', 3)
      .attr('d', line);

    g.append('line')
      .attr('x1', x(currentTemperature))
      .attr('x2', x(currentTemperature))
      .attr('y1', 0)
      .attr('y2', y(estimatedLifetime))
      .attr('stroke', '#f97316')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '5,4');

    g.append('line')
      .attr('x1', 0)
      .attr('x2', x(currentTemperature))
      .attr('y1', y(estimatedLifetime))
      .attr('y2', y(estimatedLifetime))
      .attr('stroke', '#f97316')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '5,4');

    g.append('circle')
      .attr('cx', x(currentTemperature))
      .attr('cy', y(estimatedLifetime))
      .attr('r', 7)
      .attr('fill', '#f97316')
      .attr('stroke', 'white')
      .attr('stroke-width', 2);

    const annotation = g.append('g')
      .attr('transform', `translate(${x(currentTemperature) + 15}, ${y(estimatedLifetime) - 30})`);
    
    annotation.append('rect')
      .attr('x', 0)
      .attr('y', -15)
      .attr('width', 180)
      .attr('height', 55)
      .attr('fill', 'rgba(30, 30, 40, 0.95)')
      .attr('rx', 6)
      .attr('stroke', '#f97316')
      .attr('stroke-width', 1);
    
    annotation.append('text')
      .attr('x', 10)
      .attr('y', 5)
      .attr('fill', '#f97316')
      .attr('font-size', '11px')
      .attr('font-weight', 'bold')
      .text(`工作温度: ${currentTemperature.toFixed(0)} K`);
    
    annotation.append('text')
      .attr('x', 10)
      .attr('y', 22)
      .attr('fill', '#a855f7')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .text(`寿命: ${formatLifetime(estimatedLifetime)}`);
    
    annotation.append('text')
      .attr('x', 10)
      .attr('y', 38)
      .attr('fill', '#9ca3af')
      .attr('font-size', '10px')
      .text(`Ea = ${activationEnergy.toFixed(2)} eV`);

    const xAxis = d3.axisBottom(x)
      .tickFormat(d => (d as number).toFixed(0) + ' K');

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis)
      .attr('color', '#6b7280')
      .style('font-size', '11px');

    const yTicks = [1e3, 1e4, 1e5, 1e6];
    const yAxis = d3.axisLeft(y)
      .tickValues(yTicks)
      .tickFormat(d => formatLifetime(d as number));

    g.append('g')
      .call(yAxis)
      .attr('color', '#6b7280')
      .style('font-size', '11px');

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 35)
      .attr('text-anchor', 'middle')
      .attr('fill', '#9ca3af')
      .attr('font-size', '12px')
      .text('工作温度 (K)');

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -60)
      .attr('text-anchor', 'middle')
      .attr('fill', '#a855f7')
      .attr('font-size', '12px')
      .text('估计寿命');

    svg.selectAll('.data-point')
      .data(data)
      .enter().append('circle')
      .attr('class', 'data-point')
      .attr('cx', d => x(d.temperature))
      .attr('cy', d => y(d.lifetime))
      .attr('r', 4)
      .attr('fill', '#a855f7')
      .attr('opacity', 0)
      .on('mouseover', function(event, d) {
        d3.select(this).attr('opacity', 1).attr('r', 6);
        if (tooltipRef.current) {
          tooltipRef.current.style.display = 'block';
          tooltipRef.current.style.left = (event.pageX + 10) + 'px';
          tooltipRef.current.style.top = (event.pageY - 10) + 'px';
          tooltipRef.current.innerHTML = `
            <div class="font-mono text-xs">
              <div class="text-accent-400 font-bold">温度: ${d.temperature.toFixed(0)} K</div>
              <div class="text-purple-400">寿命: ${formatLifetime(d.lifetime)}</div>
            </div>
          `;
        }
      })
      .on('mouseout', function() {
        d3.select(this).attr('opacity', 0).attr('r', 4);
        if (tooltipRef.current) {
          tooltipRef.current.style.display = 'none';
        }
      });

  }, [data, currentTemperature, estimatedLifetime, activationEnergy, width, height]);

  return (
    <div className="relative">
      <svg ref={svgRef} width={width} height={height} className="chart-container" />
      <div
        ref={tooltipRef}
        className="fixed z-50 pointer-events-none bg-dark-800/95 backdrop-blur rounded-lg px-3 py-2 border border-dark-600 shadow-xl hidden"
      />
    </div>
  );
}
