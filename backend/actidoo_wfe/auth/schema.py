from pydantic import BaseModel


class LoginStateResponseSchema(BaseModel):
    first_name: str|None
    last_name: str|None
    username: str|None
    email: str|None
    
    is_logged_in: bool
    can_access_wf: bool
    can_access_wf_admin: bool


class LoginStateSchema(BaseModel):
    first_name: str|None
    last_name: str|None
    username: str|None
    email: str|None

    is_logged_in: bool
    can_access_wf: bool
    can_access_wf_admin: bool

    idp_user_id: str|None
    roles: list[str]|None
