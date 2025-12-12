import React, { useEffect } from 'react';

import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest } from '@/store/generic-data/actions';
import {
  PcPage,
} from '@/ui5-components';
import { environment } from '@/environment';
import { AnalyticalTable } from '@ui5/webcomponents-react';

const AdminInfo: React.FC = () => {
  const dispatch = useDispatch();

  const data = useSelector((state: State) => state.data[WeDataKey.ADMIN_GET_SYSTEM_INFORMATION]);
   
  useEffect(() => {
    dispatch(
      getRequest(WeDataKey.ADMIN_GET_SYSTEM_INFORMATION, {})
    );
  }, []);

  return (
    <PcPage
        header={{
        title: 'System Information'
        }}
    >

    <AnalyticalTable
        className='mb-4'
        columns={[
            {
            Header: 'Title',
            accessor: 'title'
            },
            {
            Header: 'Value',
            accessor: 'value'
            },
        ]}
        minRows={1}
        data={[{
            "title": 'Frontend Build Commit',
            "value": environment.buildNumber || "dev"
        },{
            "title": 'Backend Build Commit',
            "value": data ? (data?.data?.build_number ||"") : ""
        }]}
    />
      
    </PcPage>
  );
};

export default AdminInfo;
