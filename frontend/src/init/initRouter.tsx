// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  createBrowserRouter,
  createRoutesFromElements,
  Navigate,
  Outlet,
  Route,
} from 'react-router-dom';

import React, { Suspense } from 'react';
import { PcErrorView, type PcNavigationLink, PcPageWrapper } from '@/ui5-components';
import { BusyIndicator } from '@ui5/webcomponents-react';
import { logout } from '@/services/AuthService';
import { environment } from '@/environment';
import { useSelector } from 'react-redux';
import { type State } from '@/store';
import { AuthWrapper } from '@/auth/AuthWrapper';
import { DialogStartWorkflow } from '@/utils/fragments/DialogStartWorkflow';
import { WorkflowState } from '@/models/models';
import { WeAdminRoute } from '@/utils/components/WeAdminRoute';
import Statistics from '@/pages/statistics/Statistics';
import AdminInfo from '@/pages/admin/info/AdminInfo';
import UserSettings from '@/pages/user-settings/UserSettings';
import { useTranslation } from '@/i18n';

//Actually lazy loading is not necessary, but it will help to keep the initial JS file(s) smaller and speed up the initial loading
//To omit lazy loading you'd have to use normal imports like `import { Tasks } from ...`

const Tasks = React.lazy(async () => await import('@/pages/tasks/Tasks'));
const OpenTasks = React.lazy(async () => await import('@/pages/tasks/open/OpenTasks'));
const CompletedTasks = React.lazy(
  async () => await import('@/pages/tasks/completed/CompletedTasks')
);
const TaskContent = React.lazy(async () => await import('@/pages/tasks/content/TaskContent'));
const SingleTask = React.lazy(
  async () => await import('@/pages/tasks/content/single-task/SingleTask')
);
const MyWorkflows = React.lazy(async () => await import('@/pages/my-workflows/MyWorkflows'));
const MyOpenWorkflows = React.lazy(
  async () => await import('@/pages/my-workflows/open/MyOpenWorkflows')
);
const MyCompletedWorkflows = React.lazy(
  async () => await import('@/pages/my-workflows/completed/MyCompletedWorkflows')
);
const AdminWorkflows = React.lazy(
  async () => await import('@/pages/admin/workflows/AdminWorkflows')
);
const AdminTasks = React.lazy(async () => await import('@/pages/admin/tasks/AdminTasks'));
const AdminTaskDetails = React.lazy(
  async () => await import('@/pages/admin/tasks/details/AdminTaskDetails')
);
const AdminWorkflowDetails = React.lazy(
  async () => await import('@/pages/admin/workflows/details/AdminWorkflowDetails')
);
const AdminUsers = React.lazy(async () => await import('@/pages/admin/users/AdminUsers'));
const AdminUserDetails = React.lazy(
  async () => await import('@/pages/admin/users/details/AdminUserDetails')
);
const WorkflowDiagram = React.lazy(
  async () => await import('@/pages/workflow-diagram/WorkflowDiagram')
);
const AdminWorkflowDiagram = React.lazy(
  async () => await import('@/pages/statistics/AdminWorkflowDiagram')
);
const StartWorkflowPreview = React.lazy(
  async () => await import('@/pages/start-workflow-preview/StartWorkflowPreview')
);
const About = React.lazy(async () => await import('@/pages/about/About'));
const Wrapper: React.FC = () => {
  const { t } = useTranslation();
  const appTitle = t('layout.appTitle');
  const loginState = useSelector((state: State) => state.auth.loginState.data);
  const user = useSelector((state: State) => state.data['wfe-user']?.data);
  const brandLogoUrl = `${import.meta.env.BASE_URL}branding/logo.svg`;

  const navigation: PcNavigationLink[] = [
    {
      title: t('navigation.tasks'),
      to: '/tasks/open',
      activeRoute: '/tasks',
    },
    {
      title: t('navigation.myWorkflows'),
      to: '/my-workflows',
      activeRoute: '/my-workflows',
    },
  ];

  if (loginState?.can_access_wf_admin || (user?.workflows_the_user_is_admin_for?.length ?? 0) > 0) {
    const subNav = [
      { title: t('navigation.adminWorkflows'), to: '/admin/all-workflows' },
      { title: t('navigation.adminTasks'), to: '/admin/all-tasks' },
      { title: t('navigation.adminUsers'), to: '/admin/all-users' },
    ];

    if (loginState?.can_access_wf_admin) {
      subNav.push({ title: t('navigation.statistics'), to: '/statistics' });
      subNav.push({ title: t('navigation.systemInformation'), to: '/admin/sysinfo' });
    }

    navigation.push({
      title: t('navigation.admin'),
      activeRoute: '/admin',
      sub: subNav,
    });
  }


  const busy: JSX.Element = (
    <div className="flex inset-0 absolute items-center justify-center">
      <BusyIndicator active delay={100} />
    </div>
  );

  return (
    <PcPageWrapper
      navigation={navigation}
      //appTitle={appTitle}
      brandLogoUrl={brandLogoUrl}
      onLogout={() => logout()}
      endHeaderActions={<DialogStartWorkflow />}
      user={loginState?.username}
      settingsRoute={'/user-settings'}
      helpRoute={'/about'}>
      <Suspense fallback={<>{busy}</>}>
        <Outlet />
      </Suspense>
    </PcPageWrapper>
  );
};

const NotFoundError: React.FC = () => {
  const { t } = useTranslation();
  return (
    <PcErrorView
      titleText={t('auth.notFoundTitle')}
      subtitleText={t('auth.notFoundSubtitle')}
      showReload={false}
      showHome={true}
    />
  );
};

const IndexRoute: React.FunctionComponent = () => {
  return <Navigate to="/tasks/open" replace={true} />;
};

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route
      // Add "AuthWrapper" to validate authorization on _every_ route, so user is immediately shown errors in case token is no longer valid
      // or if he is browsing route only valid for admins
      // (Real authorization check is done in the backend, of course)
      element={<AuthWrapper />}
      errorElement={<NotFoundError />}>
      <Route element={<Wrapper />}>
        <Route path="/" index element={<IndexRoute />} errorElement={<PcErrorView />} />
        <Route path="/tasks" element={<Tasks />} errorElement={<PcErrorView />}>
          <Route index element={<Navigate to="open" replace />} />

          {/*
          Outlet is used in route elements like `OpenTasks`, so that is will either render
          `TaskContent` or `SingleTask` as child component, based on the specific route
          */}

          <Route path="open" element={<OpenTasks />} errorElement={<PcErrorView />}>
            <Route
              path="start_workflow_preview"
              element={<StartWorkflowPreview />}
              errorElement={<PcErrorView />}
            />
            <Route
              path=":workflowId"
              element={<TaskContent state={WorkflowState.READY} />}
              errorElement={<PcErrorView />}
            />
            <Route
              path=":workflowId/:taskId"
              element={<SingleTask state={WorkflowState.READY} />}
              errorElement={<PcErrorView />}
            />
          </Route>
          <Route path="completed" element={<CompletedTasks />} errorElement={<PcErrorView />}>
            <Route
              path=":workflowId"
              element={<TaskContent state={WorkflowState.COMPLETED} />}
              errorElement={<PcErrorView />}
            />
            <Route
              path=":workflowId/:taskId"
              element={<SingleTask state={WorkflowState.COMPLETED} />}
              errorElement={<PcErrorView />}
            />
          </Route>
        </Route>

        <Route path="/my-workflows" element={<MyWorkflows />} errorElement={<PcErrorView />}>
          <Route index element={<Navigate to="progress" replace />} />
          <Route path="progress" element={<MyOpenWorkflows />} errorElement={<PcErrorView />} />
          <Route
            path="completed"
            element={<MyCompletedWorkflows />}
            errorElement={<PcErrorView />}
          />
        </Route>
        <Route
          path="/statistics"
          element={
            <Statistics />
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path='/statistics/overview/:name'
          element={<AdminWorkflowDiagram />}
          errorElement={<PcErrorView />}
        />
        <Route
          path="/user-settings"
          element={
            <UserSettings />
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path="/admin/all-tasks"
          element={
            <WeAdminRoute>
              <AdminTasks />
            </WeAdminRoute>
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path="/admin/all-tasks/:taskId"
          element={
            <WeAdminRoute>
              <AdminTaskDetails />
            </WeAdminRoute>
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path="/admin/all-workflows"
          element={
            <WeAdminRoute>
              <AdminWorkflows />
            </WeAdminRoute>
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path="/admin/all-users"
          element={
            <WeAdminRoute>
              <AdminUsers />
            </WeAdminRoute>
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path="/admin/all-users/:userId"
          element={
            <WeAdminRoute>
              <AdminUserDetails />
            </WeAdminRoute>
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path="/admin/all-workflows/:workflowId"
          element={
            <WeAdminRoute>
              <AdminWorkflowDetails />
            </WeAdminRoute>
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path="/admin/sysinfo"
          element={
            <AdminInfo />
          }
          errorElement={<PcErrorView />}
        />
        <Route
          path="/workflow-diagram/:name"
          element={<WorkflowDiagram />}
          errorElement={<PcErrorView />}
        />
        <Route
          path="/start_workflow_preview"
          element={<StartWorkflowPreview />}
          errorElement={<PcErrorView />}
        />
        <Route path="/about" element={<About />} errorElement={<PcErrorView />} />

      </Route>
    </Route>
  ),
  { basename: environment.urlPrefix }
);

export default router;
