import React, { useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';
import { DateSelection } from './Datepicker';
export interface DataPoint {
  date: Date;
  calls: number;
}
export interface Workflow {
  name: string;
  data: DataPoint[];
}
export interface Props {
  workflows: Workflow[];
  startSetter: React.Dispatch<React.SetStateAction<Date>>;
  endSetter: React.Dispatch<React.SetStateAction<Date>>;
  startDate: Date;
  endDate: Date;
}
const Graph: React.FC<Props> = ({ workflows, startSetter, endSetter, startDate, endDate }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({
    width: 1200,
    height: 600,
  });
  const [visibleWorkflows, setVisibleWorkflows] = useState<string[]>(() =>
    workflows.map(w => w.name)
  );
  const toggleWorkflowVisibility = (name: string) => {
    setVisibleWorkflows(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  };

  useEffect(() => setVisibleWorkflows(workflows.map(w => w.name)), [workflows]);

  useEffect(() => {
    if (!containerRef.current) return;
    const resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width, height });
      }
    });
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  const colorScale = d3
    .scaleOrdinal<string>()
    .domain(workflows.map(w => w.name))
    .range(d3.schemeCategory10);

  useEffect(() => {
    if (!svgRef.current) return;
    const margin = { top: 10, right: 40, bottom: 20, left: 50 };
    const innerWidth = dimensions.width - margin.left - margin.right;
    const innerHeight = dimensions.height - margin.top - margin.bottom;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.style('background-color', 'white');
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    const filteredWorkflows = workflows.filter(w => visibleWorkflows.includes(w.name));
    const allData = filteredWorkflows.flatMap(w => w.data);
    const [minDate, maxDate] = d3.extent(allData, d => d.date) as [Date, Date]; // if you want to change how date selection behaves
    const x = d3.scaleTime().domain([startDate, endDate]).range([0, innerWidth]);
    const y = d3

      .scaleLinear()
      .domain([0, d3.max(allData, d => d.calls)!])
      .nice()
      .range([innerHeight, 0]);

    g.append('g').attr('transform', `translate(0,${innerHeight})`).call(d3.axisBottom(x));
    g.append('g').call(d3.axisLeft(y));
    g.append('g')
      .call(
        d3
          .axisLeft(y)
          .tickSize(-innerWidth)
          .tickFormat(() => '')
      )
      .attr('stroke-opacity', 0.1);
    g.append('g')
      .call(
        d3
          .axisTop(x)
          .tickSize(-innerHeight)
          .tickFormat(() => '')
      )
      .attr('stroke-opacity', 0.1);
    filteredWorkflows.forEach((workflow, index) => {
      const line = d3
        .line<DataPoint>()
        .x(d => x(d.date))
        .y(d => y(d.calls))
        .curve(d3.curveMonotoneX);
      g.append('path')
        .datum(workflow.data)
        .attr('fill', 'none')
        .attr('stroke', colorScale(workflow.name))
        .attr('stroke-width', 2)
        .attr('d', line);
      g.selectAll(`circle.workflow-${index}`)
        .data(workflow.data.filter(d => d.calls > 0))
        .join('circle')
        .attr('class', `workflow-${index}`)
        .attr('cx', d => x(d.date))
        .attr('cy', d => y(d.calls))
        .attr('r', 5)
        .attr('fill', colorScale(workflow.name))
        .attr('stroke', '#fff')
        .attr('stroke-width', 1)
        .attr('opacity', 0)
        .on('mouseover', function (event, d) {
          const tooltip = d3.select('#tooltip');
          const offset = 10;

          tooltip
            .html(
              `Workflow: ${workflow.name}<br/>Total Instances: ${
                d.calls
              }<br/>${d.date.toLocaleDateString()}`
            )
            .style('opacity', 1)
            .style('visibility', 'visible');
        })
        .on('mousemove', function (event) {
          const tooltip = d3.select('#tooltip');
          const offset = 10;

          const containerRect = containerRef.current?.getBoundingClientRect();
          const mouseX = event.clientX - (containerRect?.left ?? 0);
          const mouseY = event.clientY - (containerRect?.top ?? 0);

          const tooltipNode = tooltip.node() as HTMLElement;
          const tooltipWidth = tooltipNode.getBoundingClientRect().width;
          const tooltipHeight = tooltipNode.getBoundingClientRect().height;

          const containerWidth = containerRect?.width ?? window.innerWidth;
          const containerHeight = containerRect?.height ?? window.innerHeight;

          let leftPos = mouseX + offset;
          let topPos = mouseY - tooltipHeight - offset;

          // Flip horizontally if near right edge
          if (mouseX + tooltipWidth + offset > containerWidth) {
            leftPos = mouseX - tooltipWidth - offset;
          }

          // Flip vertically if near top edge
          if (mouseY - tooltipHeight - offset < 0) {
            topPos = mouseY + offset;
          }

          tooltip.style('left', `${leftPos}px`).style('top', `${topPos}px`);
        })
        .on('mouseout', () => {
          d3.select('#tooltip').style('opacity', 0).style('visibility', 'hidden');
        });
    });
    const sortedWorkflows = [...workflows].sort((a, b) => a.name.localeCompare(b.name));
    const legendContainer = d3.select('#legend-container');
    legendContainer.html(''); // Clear previous content
    sortedWorkflows.forEach(workflow => {
      const color = colorScale(workflow.name);
      const isVisible = visibleWorkflows.includes(workflow.name);

      const legendItem = legendContainer
        .append('div')
        .attr('class', 'flex items-center mb-2 cursor-pointer')
        .style('text-decoration', isVisible ? 'none' : 'line-through')

        .on('click', () => toggleWorkflowVisibility(workflow.name));
      legendItem
        .append('div')
        .attr('class', 'w-3 h-3 mr-2 rounded')
        .style('background-color', color)
        .style('opacity', isVisible ? 1 : 0.3);

      legendItem.append('span').attr('class', 'text-sm').text(workflow.name);

    });
  }, [workflows, dimensions, visibleWorkflows]);
  return (
  <div className='bg-white'>
    <div
      ref={containerRef}
      className="w-full max-h-[600px] relative pt-[10px] pb-[30px] bg-white mb-[30px]">
      <DateSelection startSetter={startSetter} endSetter={endSetter} />
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        
      />{' '}
      <div
        id="tooltip"
        style={{
          position: 'absolute',
          opacity: 0,
          backgroundColor: 'white',
          padding: '6px 10px',
          border: '1px solid #aaa',
          borderRadius: '4px',
          pointerEvents: 'none',
          fontSize: '14px',
          transition: 'top 0.1s ease-out, left 0.1s ease-out, opacity 0.2s ease-in-out',
        }}
      />{' '}
    </div>
    <div
      id="legend-container"
      className="flex flex-wrap background-#fff pl-[50px] gap-x-4 mb-4 max-h-[100px] overflow-y-auto"
    />
  </div>
  );
};
export default Graph;
