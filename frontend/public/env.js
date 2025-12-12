/* Default runtime configuration; overridden in production from FRONTEND_BASE_URL by docker/start.sh */
window.__ACTIDOO_RUNTIME_CONFIG__ = {
  FRONTEND_BASE_URL: "",
  API_BASE_URL: "",
  ENVIRONMENT_LABEL: "",
};
window.dispatchEvent(new Event("actidoo:runtime-config-ready"));
