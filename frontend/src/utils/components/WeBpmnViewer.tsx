import React, { useEffect, useState } from 'react';
import BpmnViewer from 'bpmn-js/lib/NavigatedViewer';
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn.css';
import { Canvas } from 'bpmn-js/lib/features/context-pad/ContextPadProvider';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { BpmnElement } from '@/models/models';

export interface WeBpmnViewerProps {
  diagramXML: string;
  isAdmin: boolean;
  workflowName?: string;
  tasksData?: any;
}

export const WeBpmnViewer: React.FC<WeBpmnViewerProps> = props => {
  let viewer: BpmnViewer | undefined;

  const [isErrorState, setIsErrorState] = useState<boolean>(false);

  useEffect(() => {
    const container = document.getElementById('js-canvas') ?? undefined;

    viewer = new BpmnViewer({
      container,
      width: '100%',
    });

    // @ts-expect-error
    viewer.get('canvas')?.zoom('fit-viewport');

    async function importXML(xml: string, Viewer: BpmnViewer): Promise<void> {
      await Viewer.importXML(xml);
    }

    importXML(props.diagramXML, viewer)
      .then(() => {
        // @ts-expect-error
        centerAndFitViewport(viewer);
        setIsErrorState(false);
        if (props.isAdmin) {
          // @ts-expect-error
          renderStateCircles(viewer, props.tasksData);
        }
      })
      .catch(e => {
        console.log(e);
        setIsErrorState(true);
      });
  }, [props.tasksData, viewer, props.isAdmin, props.diagramXML]);

  function centerAndFitViewport(viewer: BpmnViewer): void {
    const canvas: Canvas = viewer.get('canvas');

    const center = getAllElementsCenter(canvas);
    canvas.zoom('fit-viewport', center);
  }

  function getAllElementsCenter(canvas: Canvas): { x: number; y: number } {
    const { inner } = canvas.viewbox();

    const center = {
      x: Number(inner.x) + inner.width / 2,
      y: Number(inner.y) + inner.height / 2,
    };

    return center;
  }

  function createCircle(gElement: Element, id: string, x: number, y: number, width: number, height: number, rx: number, ry: number, color: string, text: string): void {
    const groupElement = document.createElementNS("http://www.w3.org/2000/svg", 'g');

    groupElement.setAttribute('id', id);

    const rectElement = document.createElementNS("http://www.w3.org/2000/svg", 'rect');
    rectElement.setAttribute('x', x.toString());
    rectElement.setAttribute('y', y.toString());
    rectElement.setAttribute('width', width.toString());
    rectElement.setAttribute('height', height.toString());
    rectElement.setAttribute('rx', rx.toString());
    rectElement.setAttribute('ry', ry.toString());
    rectElement.setAttribute('fill', color);

    groupElement.appendChild(rectElement);

    // Text erstellen
    const textElement = document.createElementNS("http://www.w3.org/2000/svg", 'text');
    textElement.textContent = text;
    textElement.setAttribute('x', (x + width / 2).toString());
    textElement.setAttribute('y', (y + height / 1.3).toString());
    textElement.setAttribute('fill', 'white');
    textElement.setAttribute('text-anchor', 'middle');

    groupElement.appendChild(textElement);
    gElement.appendChild(groupElement);
  }

  function renderStateCircles(viewer: BpmnViewer, tasksData: any): void {
    const elementRegistry = viewer.get('elementRegistry') as BpmnElement[];
    const tasks = elementRegistry.filter(e =>
      e.businessObject &&
      e.businessObject.$type === 'bpmn:UserTask' || e.businessObject.$type === 'bpmn:ServiceTask'
    );

    tasks.forEach(task => {
      const gElement = document.querySelector(`[data-element-id="${task.businessObject.id}"]`);
      {/*assign_optional1 -> das ist die data-element-id -> müste der task_name aus der getRequest sein*/ } 7

      const taskStatus = tasksData ? tasksData[task.businessObject.id] : null;
      if (gElement) {
        if (taskStatus && taskStatus.ready_counter > 0) {
          createCircle(gElement, `ready-${task.businessObject.id}`, -10, 70, 35, 20, 10, 10, '#09AE3B', taskStatus.ready_counter.toString());
        }

        if (taskStatus && taskStatus.error_counter > 0) {
          createCircle(gElement, `error-${task.businessObject.id}`, 75, 70, 35, 20, 10, 10, '#ED0A19', taskStatus.error_counter.toString());
        }
      }
    });

  }

  return (
    <>
      {isErrorState ? (
        <WeEmptySection
          icon={'org-chart'}
          title={'workflow diagram could not be visualized'}
          text={'the workflow diagram could not be visualized'}
        />
      ) : (
        <div style={{ height: '100%' }}>
          <div id="js-canvas" style={{ height: '100%' }} />
        </div>
      )}
    </>
  );
};
