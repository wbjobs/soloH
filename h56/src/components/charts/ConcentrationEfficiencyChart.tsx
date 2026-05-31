import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface ConcentrationPoint {
  cr: number;
  efficiency: number;
  jsc: number;
}

interface ConcentrationEfficiencyChartProps {
  data: ConcentrationPoint[];
  currentCR: number;
  optimumCR: number;
  maxEfficiency: number;
  width?: number;
  height?: number;
}

export function ConcentrationEfficiencyChart({
  data,
  currentCR,
  optimumCR,
  maxEfficiency,
  width = 850,
  height = 350,
}: ConcentrationEfficiencyChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const margin = { top: 30, right: 60, bottom: 50, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLog()
      .domain(d3.extent(data, d => d.cr) as [number, number])
      .range([0, innerWidth]);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.efficiency) * 1.15 || 1])
      .range([innerHeight, 0]);

    const yJsc = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.jsc) * 1.1 || 1])
      .range([innerHeight, 0]);

    const gradient = svg.append('defs')
      .append('linearGradient')
      .attr('id', 'concLineGradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '100%')
      .attr('y2', '0%');
    gradient.append('stop').attr('offset', '0%').attr('stop-color', '#facc15');
    gradient.append('stop').attr('offset', '100%').attr('stop-color', '#f97316');

    const area = d3.area<ConcentrationPoint>()
      .x(d => x(d.cr))
      .y0(innerHeight)
      .y1(d => y(d.efficiency))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'url(#concLineGradient)')
      .attr('opacity', 0.2)
      .attr('d', area);

    const line = d3.line<ConcentrationPoint>()
      .x(d => x(d.cr))
      .y(d => y(d.efficiency))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', 'url(#concLineGradient)')
      .attr('stroke-width', 3)
      .attr('d', line);

    const lineJsc = d3.line<ConcentrationPoint>()
      .x(d => x(d.cr))
      .y(d => yJsc(d.jsc))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#22d3ee')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '5,3')
      .attr('d', lineJsc);

    g.append('line')
      .attr('x1', x(optimumCR))
      .attr('x2', x(optimumCR))
      .attr('y1', 0)
      .attr('y2', y(maxEfficiency))
      .attr('stroke', '#10b981')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '4,4');

    g.append('line')
      .attr('x1', 0)
      .attr('x2', x(optimumCR))
      .attr('y1', y(maxEfficiency))
      .attr('y2', y(maxEfficiency))
      .attr('stroke', '#10b981')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '4,4');

    g.append('circle')
      .attr('cx', x(optimumCR))
      .attr('cy', y(maxEfficiency))
      .attr('r', 7)
      .attr('fill', '#10b981')
      .attr('stroke', 'white')
      .attr('stroke-width', 2);

    if (currentCR && currentCR !== optimumCR) {
      const currentEff = data.find(d => Math.abs(d.cr - currentCR) < 1)?.efficiency || 0;
      g.append('circle')
        .attr('cx', x(currentCR))
        .attr('cy', y(currentEff))
        .attr('r', 6)
        .attr('fill', '#f97316')
        .attr('stroke', 'white')
        .attr('stroke-width', 2);
    }

    const xAxis = d3.axisBottom(x)
      .tickValues([1, 10, 50, 100, 500, 1000])
      .tickFormat(d => d + '×');

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis)
      .attr('color', '#6b7280')
      .style('font-size', '11px');

    const yAxis = d3.axisLeft(y)
      .tickFormat(d => (d as number).toFixed(1) + '%');

    g.append('g')
      .call(yAxis)
      .attr('color', '#6b7280')
      .style('font-size', '11px');

    const yAxisJsc = d3.axisRight(yJsc)
      .tickFormat(d => (d as number).toFixed(1));

    g.append('g')
      .attr('transform', `translate(${innerWidth},0)`)
      .call(yAxisJsc)
      .attr('color', '#22d3ee')
      .style('font-size', '11px');

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 35)
      .attr('text-anchor', 'middle')
      .attr('fill', '#9ca3af')
      .attr('font-size', '12px')
      .text('聚光比');

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -40)
      .attr('text-anchor', 'middle')
      .attr('fill', '#fbbf24')
      .attr('font-size', '12px')
      .text('转换效率 (%)');

    g.append('text')
      .attr('transform', 'rotate(90)')
      .attr('x', innerHeight / 2)
      .attr('y', -innerWidth - 40)
      .attr('text-anchor', 'middle')
      .attr('fill', '#22d3ee')
      .attr('font-size', '12px')
      .text('短路电流 (A/cm²)');

    const legend = g.append('g').attr('transform', `translate(${innerWidth - 180}, 10)`);
    
    legend.append('line')
      .attr('x1', 0).attr('y1', 0).attr('x2', 25).attr('y2', 0)
      .attr('stroke', 'url(#concLineGradient)').attr('stroke-width', 3);
    legend.append('text').attr('x', 35).attr('y', 4).attr('fill', '#9ca3af').attr('font-size', '11px').text('效率');
    
    legend.append('line')
      .attr('x1', 0).attr('y1', 20).attr('x2', 25).attr('y2', 20)
      .attr('stroke', '#22d3ee').attr('stroke-width', 2).attr('stroke-dasharray', '5,3');
    legend.append('text').attr('x', 35).attr('y', 24).attr('fill', '#9ca3af').attr('font-size', '11px').text('Jsc');

    svg.selectAll('.data-point')
      .data(data)
      .enter().append('circle')
      .attr('class', 'data-point')
      .attr('cx', d => x(d.cr))
      .attr('cy', d => y(d.efficiency))
      .attr('r', 4)
      .attr('fill', '#facc15')
      .attr('opacity', 0)
      .on('mouseover', function(event, d) {
        d3.select(this).attr('opacity', 1).attr('r', 6);
        if (tooltipRef.current) {
          tooltipRef.current.style.display = 'block';
          tooltipRef.current.style.left = (event.pageX + 10) + 'px';
          tooltipRef.current.style.top = (event.pageY - 10) + 'px';
          tooltipRef.current.innerHTML = `
            <div class="font-mono text-xs">
              <div class="text-accent-400 font-bold">聚光比: ${d.cr}×</div>
              <div class="text-yellow-400">效率: ${d.efficiency.toFixed(2)}%</div>
              <div class="text-cyan-400">Jsc: ${d.jsc.toFixed(3)} A/cm²</div>
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

  }, [data, currentCR, optimumCR, maxEfficiency, width, height]);

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
