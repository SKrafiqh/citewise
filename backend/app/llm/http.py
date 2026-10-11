"""HTTP transport shared by the LLM clients.

Forces IPv4: on networks where IPv6 to the provider is silently dropped, Python's resolver tries every
IPv6 address (each waiting for the OS timeout) before falling back, which looks like a hang.
"""
import httpx

TIMEOUT_S = 120


def ipv4_transport() -> httpx.HTTPTransport:
    return httpx.HTTPTransport(local_address="0.0.0.0", retries=2)
