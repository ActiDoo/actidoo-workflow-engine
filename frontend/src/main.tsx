import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';

import { Provider } from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';
import { ThemeProvider } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-react/dist/Assets';

import { setTheme } from '@ui5/webcomponents-base/dist/config/Theme';
import { persistor, store } from '@/init/initStore'; // -> will set up the Redux Store
import router from '@/init/initRouter'; // -> will do the main work of setting up everything
import '@/styles/index.scss';
import { QueryClient, QueryClientProvider } from 'react-query';
import { WeDialog } from '@/utils/components/WeDialog';
import { WeToast } from '@/utils/components/WeToast';

// set theme of ui5 webcomponents
void setTheme('sap_horizon').then(); // no effect?

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);
const queryClient = new QueryClient();

root.render(
  <Provider store={store}>
    {/* PersistGate is a layer to persist the Store in the LocalStorage. Currently not used by the application. */}
    {/* A use case in the future might be to persist the ui Store, so a Refresh will not empty all input fields. */}
    {/* You can add your own config for each store (i.e. ui/generic-data/auth) */}
    <PersistGate loading={null} persistor={persistor}>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
          <WeToast />
          <WeDialog />
        </QueryClientProvider>
      </ThemeProvider>
    </PersistGate>
  </Provider>
);
