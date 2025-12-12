import logging
from typing import Type, TypeVar

from fastapi.testclient import TestClient
from pydantic import BaseModel

from actidoo_wfe.fastapi import app as root_app

log: logging.Logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class Client:
    def __init__(self):
        """Creates a webserver client, which accesses our fastapi webserver. Provides CRUD functions"""
        self.root_client: TestClient = TestClient(root_app, base_url="https://testserver")

    def post(self, name: str, json, cls: None|Type[T]=None) -> tuple[int, T]:
        response = self.root_client.post(url=root_app.url_path_for(name), json=json)
        json_resp = response.json()
        if cls is not None:
            parsed: T = cls.model_validate(json_resp)
        else:
            parsed = json_resp
        return response.status_code, parsed

    def get(self, name: str, cls: None|Type[T]=None, params={}) -> tuple[int, T]:
        response = self.root_client.get(url=root_app.url_path_for(name), params=params)
        json_resp = response.json()
        if cls is not None:
            parsed: T = cls.model_validate(json_resp)
        else:
            parsed = json_resp
        return response.status_code, parsed

