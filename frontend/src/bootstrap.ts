const RUNTIME_CONFIG_EVENT = 'actidoo:runtime-config-ready';
const RUNTIME_CONFIG_TIMEOUT_MS = 2000;

const waitForRuntimeConfig = async (): Promise<void> => {
  if (typeof window === 'undefined') {
    return;
  }

  if (window.__ACTIDOO_RUNTIME_CONFIG__) {
    return;
  }

  await new Promise<void>((resolve) => {
    const cleanup = (timeoutId: number) => {
      window.removeEventListener(RUNTIME_CONFIG_EVENT, handleReady);
      window.clearTimeout(timeoutId);
    };

    const handleReady = () => {
      cleanup(timeoutId);
      resolve();
    };

    const handleTimeout = () => {
      cleanup(timeoutId);
      resolve();
    };

    const timeoutId = window.setTimeout(handleTimeout, RUNTIME_CONFIG_TIMEOUT_MS);
    window.addEventListener(RUNTIME_CONFIG_EVENT, handleReady, { once: true });
  });
};

const bootstrap = async (): Promise<void> => {
  await waitForRuntimeConfig();
  await import('./main');
};

void bootstrap();

export {};
