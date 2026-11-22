#!/usr/bin/env python3
"""Relay selected IPv6 UDP listeners to local IPv4 UDP services.

This is intentionally dependency-free. Each IPv6 client gets a connected
IPv4 socket so replies remain associated with the original client and source
port. It is suitable for short request/reply protocols such as A2S and the
server ping endpoint; it does not relay gameplay traffic.
"""

from __future__ import annotations

import argparse
import logging
import selectors
import socket
import time
from dataclasses import dataclass


IDLE_TIMEOUT = 120.0


@dataclass
class Flow:
    socket: socket.socket
    listener: socket.socket
    client: tuple[str, int, int, int]
    listen_port: int
    last_seen: float


def parse_mapping(value: str) -> tuple[int, int]:
    try:
        listen, target = (int(part) for part in value.split(":", 1))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("mapping must be LISTEN:TARGET") from exc
    if not (1 <= listen <= 65535 and 1 <= target <= 65535):
        raise argparse.ArgumentTypeError("ports must be between 1 and 65535")
    return listen, target


def make_listener(address: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    sock.bind((address, port))
    sock.setblocking(False)
    return sock


def run(mappings: list[tuple[int, int]], target_address: str, listen_address: str) -> None:
    selector = selectors.DefaultSelector()
    listeners: dict[socket.socket, tuple[int, int]] = {}
    flows: dict[socket.socket, Flow] = {}

    for listen_port, target_port in mappings:
        listener = make_listener(listen_address, listen_port)
        selector.register(listener, selectors.EVENT_READ, ("v6", listener))
        listeners[listener] = (listen_port, target_port)
        logging.info("IPv6 UDP [%s]:%d -> %s:%d", listen_address, listen_port, target_address, target_port)

    try:
        while True:
            now = time.monotonic()
            for flow_socket, flow in list(flows.items()):
                if now - flow.last_seen > IDLE_TIMEOUT:
                    selector.unregister(flow_socket)
                    flow_socket.close()
                    del flows[flow_socket]

            for key, _ in selector.select(timeout=1.0):
                family, source_socket = key.data
                if family == "v6":
                    data, client = source_socket.recvfrom(65535)
                    listen_port, target_port = listeners[source_socket]
                    flow_socket = next(
                        (sock for sock, flow in flows.items()
                         if flow.client == client and flow.listen_port == listen_port),
                        None,
                    )
                    if flow_socket is None:
                        flow_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        flow_socket.setblocking(False)
                        flow_socket.connect((target_address, target_port))
                        flows[flow_socket] = Flow(flow_socket, source_socket, client, listen_port, now)
                        selector.register(flow_socket, selectors.EVENT_READ, ("v4", flow_socket))
                    flows[flow_socket].last_seen = now
                    flow_socket.send(data)
                else:
                    flow = flows[source_socket]
                    data = source_socket.recv(65535)
                    flow.last_seen = now
                    flow.listener.sendto(data, flow.client)
    finally:
        for sock in list(listeners) + list(flows):
            try:
                selector.unregister(sock)
            except Exception:
                pass
            sock.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="mappings", action="append", required=True, type=parse_mapping)
    parser.add_argument("--target-address", default="127.0.0.1")
    parser.add_argument("--listen-address", default="::")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(message)s")
    run(args.mappings, args.target_address, args.listen_address)


if __name__ == "__main__":
    main()
