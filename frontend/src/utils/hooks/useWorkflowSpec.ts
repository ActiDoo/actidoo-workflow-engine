import { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest } from '@/store/generic-data/actions';
import { useSelectUiLoading } from '@/store/ui/selectors';

const useWorkflowSpec = (name: string | undefined) => {
    const dispatch = useDispatch();

    const dataWorkflowSpec = useSelector(
        (state: State) => state.data[WeDataKey.REFRESH_GET_WORKFLOW_SPEC]
    )?.data;

    const dataWorkflowSpecItem = name
        ? dataWorkflowSpec?.files.find(w => w.file_bpmn_process_id.startsWith(name))
        : undefined;
    
    const dataTaskStates = useSelector(
        (state: State) => state.data[WeDataKey.ADMIN_GET_TASK_STATES_PER_WORKFLOW]
    );

    const loadStateWorkflowSpec = useSelectUiLoading(WeDataKey.REFRESH_GET_WORKFLOW_SPEC);
    const loadTaskStates = useSelectUiLoading(WeDataKey.ADMIN_GET_TASK_STATES_PER_WORKFLOW);

    useEffect(() => {
        if (name) {
            dispatch(postRequest(WeDataKey.REFRESH_GET_WORKFLOW_SPEC, { name }));
            dispatch(getRequest(WeDataKey.ADMIN_GET_TASK_STATES_PER_WORKFLOW, { params: { wf_name: name } }));
        }
    }, [name]);

    return { dataWorkflowSpec, dataWorkflowSpecItem, loadStateWorkflowSpec, loadTaskStates, taskStates: dataTaskStates?.data?.tasks }
}

export default useWorkflowSpec;