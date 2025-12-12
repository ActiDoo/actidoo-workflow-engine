"""
This is a fork of uvicorns ProxyHeadersMiddleware: https://github.com/encode/uvicorn/blob/master/uvicorn/middleware/proxy_headers.py

- Supports networks instead of just IPs (needed for docker/kubernetes deployment with unknown reverse proxy IP)
- Support X-Forwarded-Host header for correctly building absolute URLs

"""
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from typing import TYPE_CHECKING, List, Optional, Tuple, Union, cast

if TYPE_CHECKING:
    from asgiref.typing import (
        ASGI3Application,
        ASGIReceiveCallable,
        ASGISendCallable,
        HTTPScope,
        Scope,
        WebSocketScope,
    )


class ProxyHeadersNetworkMiddleware:
    def __init__(
        self,
        app: "ASGI3Application",
        trusted_networks: Union[
            List[Union[IPv4Network, IPv6Network]], Union[IPv4Network, IPv6Network]
        ] = ip_network("127.0.0.1/32"),
    ) -> None:
        self.app = app
        if isinstance(trusted_networks, list):
            self.trusted_networks = set(trusted_networks)
        else:
            self.trusted_networks = [
                self.trusted_networks,
            ]

    def get_trusted_client_host(
        self, x_forwarded_for_hosts: List[str]
    ) -> Optional[str]:
        for host in reversed(x_forwarded_for_hosts):
            for network in self.trusted_networks:
                if ip_address(host) not in network:
                    return host

        return None

    async def __call__(
        self, scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable"
    ) -> None:
        if scope["type"] in ("http", "websocket"):
            scope = cast(Union["HTTPScope", "WebSocketScope"], scope)
            client_addr: Optional[Tuple[str, int]] = scope.get("client")
            client_host = client_addr[0] if client_addr else None

            if client_host is not None and client_host != "testclient":
                client_host_ip = ip_address(client_host)
                if any(client_host_ip in net for net in self.trusted_networks):
                    headers = dict(scope["headers"])

                    if b"x-forwarded-proto" in headers:
                        # Determine if the incoming request was http or https based on
                        # the X-Forwarded-Proto header.
                        x_forwarded_proto = headers[b"x-forwarded-proto"].decode(
                            "latin1"
                        )
                        scope["scheme"] = x_forwarded_proto.strip()  # type: ignore[index]

                    if b"x-forwarded-for" in headers:
                        # Determine the client address from the last trusted IP in the
                        # X-Forwarded-For header. We've lost the connecting client's port
                        # information by now, so only include the host.
                        x_forwarded_for = headers[b"x-forwarded-for"].decode("latin1")
                        x_forwarded_for_hosts = [
                            item.strip() for item in x_forwarded_for.split(",")
                        ]
                        host = self.get_trusted_client_host(x_forwarded_for_hosts)
                        port = 0
                        scope["client"] = (host, port)  # type: ignore[arg-type]

                    if b"x-forwarded-host" in headers:
                        x_forwarded_host = headers[b"x-forwarded-host"].decode("latin1")
                        (host, sep, port) = x_forwarded_host.partition(":")
                        if not sep:
                            scope["server"] = (host, 0)
                        else:
                            scope["server"] = (host, int(port))

        return await self.app(scope, receive, send)
