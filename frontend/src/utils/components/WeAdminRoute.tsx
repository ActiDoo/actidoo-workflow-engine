import React from 'react';
import { useSelector } from 'react-redux';
import { State } from '@/store';
import { Navigate } from 'react-router-dom';

export const WeAdminRoute: React.FC<{ children: any }> = ({ children }) => {
  const loginState = useSelector((state: State) => state.auth.loginState.data);
  const user = useSelector((state: State) => state.data['wfe-user']?.data);

  if (!loginState?.can_access_wf_admin && (user?.workflows_the_user_is_admin_for?.length ?? 0) == 0) {
    return <Navigate to="/" replace />;
  }

  return children;
};
