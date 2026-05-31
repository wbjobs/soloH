import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface WasteHeatChartProps {
  tpvEfficiency: number;
  wasteHeatDensity: number;
  tegOutputPower: number;
  tegEfficiency: number;
  systemTotalEfficiency: number;
  carnotEfficiency: number;
  width?: number;
  height?: number;
}

export function WasteHeatChart({
  tpvEfficiency,
  wasteHeatDensity,
  tegOutputPower,
  tegEfficiency,
  systemTotalEfficiency,
  carnotEfficiency,
  width = 850,
  height = 350,
}: WasteHeatChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const margin = { top: 40, right: 40, bottom: 60, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const categories = ['输入辐射', 'TPV输出', '废热', 'TEG输出', '系统总输出'];
    const values = [
      100,
      tpvEfficiency,
      100 - tpvEfficiency,
      (100 - tpvEfficiency) * tegEfficiency / 100,
      systemTotalEfficiency
    ];

    const maxValue = 100;

    const x = d3.scaleBand()
      .domain(categories)
      .range([0, innerWidth])
      .padding(0.3);

    const y = d3.scaleLinear()
      .domain([0, maxValue * 1.1])
      .range([innerHeight, 0]);

    const colors = ['#6366f1', '#10b981', '#ef4444', '#f97316', '#8b5cf6'];

    g.selectAll('.bar')
      .data(values)
      .enter().append('rect')
      .attr('class', 'bar')
      .attr('x', (d, i) => x(categories[i])!)
      .attr('y', d => y(d))
      .attr('width', x.bandwidth())
      .attr('height', d => innerHeight - y(d))
      .attr('fill', (d, i) => colors[i])
      .attr('rx', 6)
      .style('opacity', 0)
      .transition()
      .duration(800)
      .style('opacity', 0.85);

    g.selectAll('.bar-label')
      .data(values)
      .enter().append('text')
      .attr('class', 'bar-label')
      .attr('x', (d, i) => x(categories[i])! + x.bandwidth() / 2)
      .attr('y', d => y(d) - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', (d, i) => colors[i])
      .attr('font-size', '13px')
      .attr('font-weight', 'bold')
      .attr('font-family', 'JetBrains Mono, monospace')
      .text(d => d.toFixed(1) + '%');

    const xAxis = d3.axisBottom(x);
    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis)
      .attr('color', '#6b7280')
      .style('font-size', '11px')
      .selectAll('text')
      .attr('transform', 'rotate(-15)')
      .style('text-anchor', 'end');

    const yAxis = d3.axisLeft(y)
      .tickFormat(d => d + '%');
    g.append('g')
      .call(yAxis)
      .attr('color', '#6b7280')
      .style('font-size', '11px');

    g.append('line')
      .attr('x1', 0)
      .attr('x2', innerWidth)
      .attr('y1', y(carnotEfficiency))
      .attr('y2', y(carnotEfficiency))
      .attr('stroke', '#ef4444')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '6,4')
      .attr('opacity', 0.6);

    g.append('text')
      .attr('x', innerWidth - 10)
      .attr('y', y(carnotEfficiency) - 5)
      .attr('text-anchor', 'end')
      .attr('fill', '#ef4444')
      .attr('font-size', '11px')
      .text(`卡诺极限: ${carnotEfficiency.toFixed(1)}%`);

    const flowGroup = g.append('g');
    
    const flowArrow1 = flowGroup.append('g').attr('transform', `translate(${x('TPV输出')! + x.bandwidth()/2 + 10}, ${y(tpvEfficiency) + 20})`);
    flowArrow1.append('text')
      .attr('text-anchor', 'start')
      .attr('fill', '#10b981')
      .attr('font-size', '11px')
      .text('→ 电能');

    const flowArrow2 = flowGroup.append('g').attr('transform', `translate(${x('废热')! + x.bandwidth()/2 + 10}, ${y(50)})`);
    flowArrow2.append('text')
      .attr('text-anchor', 'start')
      .attr('fill', '#f97316')
      .attr('font-size', '11px')
      .text(`→ TEG回收 ${tegEfficiency.toFixed(1)}%`);

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', innerHeight + 45)
      .attr('text-anchor', 'middle')
      .attr('fill', '#9ca3af')
      .attr('font-size', '12px')
      .text('能量分配');

    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -innerHeight / 2)
      .attr('y', -40)
      .attr('text-anchor', 'middle')
      .attr('fill', '#9ca3af')
      .attr('font-size', '12px')
      .text('能量占比 (%)');

  }, [tpvEfficiency, wasteHeatDensity, tegOutputPower, tegEfficiency, systemTotalEfficiency, carnotEfficiency, width, height]);

  return (
    <svg ref={svgRef} width={width} height={height} className="chart-container" />
  );
}
