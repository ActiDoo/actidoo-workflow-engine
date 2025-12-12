"""
Global Application Settings
"""

import os
import pathlib
from typing import List, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

env_file = os.environ.get("ENV_FILE", ".env")

class Settings(BaseSettings):
    """Settings Definitions and Defaults"""

    ### General settings

    # frontend base url; e.g. for sending mails
    frontend_base_url: str = "http://localhost:3000"

    # Path prefix for backend API routes (env: API_PATH)
    api_path: str = "/api"

    # Set default log level
    log_level: str = "INFO"

    # Disable Login and ALLOW ALL REQUESTS? (Only for DEV!!!!)
    disable_login_check: bool = False

    # Allow CORS request to our APIs?
    cors_origins: List[str] = []

    # Networks trusted to forward proxy headers (CIDR notation)
    proxy_trusted_networks: List[str] = [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ]

    ### OIDC Settings (Authentication & Authorization)
    oidc_discovery_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_url: str = ""
    #oidc_scopes: str = "openid profile email groups roles"
    oidc_scopes: str = "openid roles"
    oidc_roles_claim_paths: str = (
        "realm_access.roles,resource_access.{client_id}.roles,resource_access.*.roles,roles,groups,app_roles,appRoles"
    )
    oidc_username_claims: str = "preferred_username,name,email,upn"
    oidc_email_claims: str = "email,upn"
    oidc_first_name_claims: str = "given_name,first_name"
    oidc_last_name_claims: str = "family_name,last_name"
    oidc_full_name_claims: str = "name"
    oidc_user_id_claims: str = "sub"
    oidc_token_refresh_skew_seconds: int = 60
    oidc_verify_ssl: str = "/etc/ssl/certs/ca-certificates.crt"

    ### OAuth Bearer Settings (Authentication & Authorization) for M2M
    oauth_bearer_token_endpoint: str = ""
    oauth_bearer_introspection_endpoint: str = ""
    oauth_bearer_client_id: str = ""
    oauth_bearer_client_secret: str = ""
    oauth_bearer_role_claim_paths: List[str] = ["resource_access.{client_id}.roles", "realm_access.roles", "roles", "groups", "scp", "scope"]

    # Output Token Introspection in Auth Fallback View?
    auth_debug_token_introspection: bool = False

    # Output Token Introspection in Auth Fallback View?
    auth_fallback_redirect: str|None = None

    ### Session settings

    # Allow session cookies only for https?
    session_https_only: bool = False

    # Session Cookie SameSite attribute
    #
    # None = Cookies will be sent in all contexts, i.e. in responses to both first-party and cross-site requests
    # Lax = Cookies are not sent on normal cross-site subrequests (for example to load images or frames into a third party site), but are sent when a user is navigating to the origin site
    # Strict = Cookies will only be sent in a first-party context and not be sent along with requests initiated by third party websites.
    #
    # Recommended value is lax
    session_same_site: str = "lax"

    ### Database Settings. Default settings apply to the mysql devcontainer, except the password, which remains in .env and does not get into the code
    db_driver: str = "mysql+pymysql"
    db_host: str = "mysql"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "app"
    db_query: str = ""
    db_echo: bool = False
    db_ssl_ca: str = ""

    ### Attachment Storage
    storage_mode: Literal['LOCAL','AZURE_BLOB','AZURE_BLOB_TENANT'] = "LOCAL"
    storage_local_upload_path: str = str((pathlib.Path(__file__).parent.parent / "upload_dir").absolute())
    storage_azure_account_name: str|None = None
    storage_azure_account_key: str|None = None # base64 encoded in case of local development for azureit; not base64 encoded for deployed Azure Tenant version (Client Secret of Service Principal)
    
    # Azure-Blob Settings for development
    storage_azure_override_host: str|None = None
    storage_azure_override_port: str|None = None
    storage_azure_override_endpoint: str|None = None
    storage_azure_override_secure: bool = True

    # Azure-Blob-Tenant settings for deployed versions
    storage_azure_tenant_id: str|None = None
    storage_azure_client_id: str|None = None

    ### Email Settings (Microsoft Graph API)
    email_client_id: str = ""
    email_client_secret: str = ""
    email_subscription_key: str = ""
    email_token_endpoint: str = ""
    email_send_endpoint: str = ""
    email_subject_suffix: str = ""
    email_subject_prefix: str="Workflow Engine:"
    email_override_recipients_enable: bool = False
    email_override_recipients_list: list[str] = []
    email_receivers_erroneous_tasks: list[str] = []
    email_signature: str="""
Best regards,

Workflow Engine
"""

    default_locale: str = "en-US"

    ## Sentry settings

    # sentry dsn (sentry provides this after creating a project)
    sentry_dsn: str = ""

    # percentage of requests which should be traced for performance monitoring
    sentry_traces_sample_rate: float = 1.0

    # The workflows to be return by the Rest API (dir names). We use an empty default,
    # because if an env variable is missing by accident in a deployment, users could see all workflows.
    # ["__ALL__"] can be taken to configure all at once. The order in this list does not matter.
    workflows: list[str] = [""]

    #ext: ExtConfig|None = None

    model_config = SettingsConfigDict(
        env_file=(env_file, ".env.local"), secrets_dir="/run/secrets", env_nested_delimiter='__'
    )
        
    @field_validator("api_path", mode="before")
    @classmethod
    def _validate_api_path(cls, value: str | None) -> str:
        clean = (value or "").strip().strip("/")
        return f"/{clean}"


settings = Settings()  # type: ignore
