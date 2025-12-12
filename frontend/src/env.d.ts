// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_FRONTEND_BASE_URL?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_TABLE_COUNT: number;
  readonly VITE_BUILD_NUMBER: string;
  readonly VITE_ENVIRONMENT_LABEL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
