# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

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
            List[Union[IPv4Network, IPv6Network, str]], Union[IPv4Network, IPv6Network, str]
        ] = "127.0.0.1/32",
    ) -> None:
        self.app = app
        
        # Normalize trusted_networks to a list of network objects
        if not isinstance(trusted_networks, list):
            trusted_networks = [trusted_networks]
        
        self.trusted_networks = []
        for net in trusted_networks:
            if isinstance(net, str):
                self.trusted_networks.append(ip_network(net, strict=False))
            else:
                self.trusted_networks.append(net)

    def get_trusted_client_host(
        self, x_forwarded_for_hosts: List[str]
    ) -> Optional[str]:
        """
        Traverse the list of IPs from right (most recent) to left.
        The first IP found that is NOT in our trusted networks is the real client.
        """
        for host in reversed(x_forwarded_for_hosts):
            try:
                addr = ip_address(host)
            except ValueError:
                # If we can't parse the IP (e.g. "unknown"), skip or return it depending on policy.
                # Usually safest to return it as the client if it's the edge.
                return host
            
            is_trusted = any(addr in net for net in self.trusted_networks)
            if not is_trusted:
                return host
        return None

    async def __call__(
        self, scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable"
    ) -> None:
        if scope["type"] in ("http", "websocket"):
            scope = cast(Union["HTTPScope", "WebSocketScope"], scope)
            
            # 1. Check if the direct connection is from a Trusted Proxy
            client_addr: Optional[Tuple[str, int]] = scope.get("client")
            client_host = client_addr[0] if client_addr else None
            
            is_proxied = False
            if client_host:
                try:
                    client_host_ip = ip_address(client_host)
                    if any(client_host_ip in net for net in self.trusted_networks):
                        is_proxied = True
                except ValueError:
                    pass

            if is_proxied:
                headers = dict(scope["headers"])

                # 2. Handle Protocol (Scheme)
                # ---------------------------------------------------------
                if b"x-forwarded-proto" in headers:
                    x_forwarded_proto = headers[b"x-forwarded-proto"].decode("latin1").strip()
                    scope["scheme"] = x_forwarded_proto

                # 3. Handle Client IP (X-Forwarded-For)
                # ---------------------------------------------------------
                if b"x-forwarded-for" in headers:
                    x_forwarded_for = headers[b"x-forwarded-for"].decode("latin1")
                    x_forwarded_for_hosts = [
                        item.strip() for item in x_forwarded_for.split(",")
                    ]
                    real_host = self.get_trusted_client_host(x_forwarded_for_hosts)
                    if real_host:
                        # We set port to 0 because we don't know the client's actual source port
                        # after it passed through a proxy.
                        scope["client"] = (real_host, 0)

                # 4. Handle Server Host & Port (The Hybrid Logic)
                # ---------------------------------------------------------
                final_host = None
                final_port = None

                # A. Try X-Forwarded-Host
                if b"x-forwarded-host" in headers:
                    header_host = headers[b"x-forwarded-host"].decode("latin1").strip()
                    host_part, sep, port_part = header_host.partition(":")
                    final_host = host_part
                    if sep and port_part.isdigit():
                        final_port = int(port_part)

                # B. Try X-Forwarded-Port (If we didn't find a port in Host header)
                if final_port is None and b"x-forwarded-port" in headers:
                    try:
                        port_str = headers[b"x-forwarded-port"].decode("latin1").strip()
                        final_port = int(port_str)
                    except ValueError:
                        pass

                # C. Fallback to Scheme defaults if still no port
                if final_port is None:
                    if scope.get("scheme") == "https":
                        final_port = 443
                    else:
                        final_port = 80

                # Apply updates to scope if we found a forwarded host
                if final_host:
                    scope["server"] = (final_host, final_port)

        return await self.app(scope, receive, send)