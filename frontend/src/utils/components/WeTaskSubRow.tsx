import { TaskItem } from '@/models/models';
import { Button, Text, Title, TitleLevel } from '@ui5/webcomponents-react';
import { Link } from 'react-router-dom';
import React from 'react';

export const WeTaskSubRow: React.FC<{
  title: string;
  tasks: TaskItem[];
  userId: string | undefined;
  workflowId: string;
}> = props => {
  return (
    <div className="bg-white border-t border-t-solid border-t-neutral-100 p-3 pb-6">
      <Title className="mb-2" level={TitleLevel.H5}>
        {props.title}
      </Title>

      <table className="text-left w-full  border-t border-t-solid border-t-neutral-100 ">
        <thead>
          <tr>
            <th className="px-2 py-1">Name</th>
            <th className="px-2 py-1">Assigned to</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {props.tasks?.map((task: any, index: number) => (
            <tr key={task.id} className={index % 2 === 0 ? 'bg-neutral-50' : ''}>
              <td className="p-2 py-1">
                <Text>{task.name}</Text>
              </td>
              <td className="p-2 py-1">
                <Text>{task.assigned_user?.full_name}</Text>
              </td>
              <td className="p-2 py-1 text-right">
                {task.assigned_user?.id === props.userId ? (
                  <Link to={`/tasks/completed/${props.workflowId}/${task.id}`}>
                    <Button icon="show" />
                  </Link>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
