// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

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
import { useTranslation } from '@/i18n';

const AdminInfo: React.FC = () => {
  const { t } = useTranslation();
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
        title: t('navigation.systemInformation')
        }}
    >

    <AnalyticalTable
        className='mb-4'
        columns={[
            {
            Header: t('common.labels.title'),
            accessor: 'title'
            },
            {
            Header: t('common.labels.value'),
            accessor: 'value'
            },
        ]}
        minRows={1}
        data={[{
            "title": t('common.labels.frontendBuildCommit'),
            "value": environment.buildNumber || "dev"
        },{
            "title": t('common.labels.backendBuildCommit'),
            "value": data ? (data?.data?.build_number || "") : ""
        }]}
    />
      
    </PcPage>
  );
};

export default AdminInfo;
