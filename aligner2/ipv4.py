"""
IPv4 first for every connection of this process (imported by aligner2/remote.py before Modal connects).

Modal's client (grpclib) connects to the FIRST address the resolver returns and never falls back. On this network the
resolver lists a NAT64 IPv6 address (64:ff9b::...) first, and IPv6 to Modal hangs at times: on 2026-09-25 `curl -6
https://api.modal.com` timed out while `-4` answered in 0.4 s, and every Modal call from Python hung (the denoiser's 240 s
timeout in the app, the engine getting no container, `modal app list` stuck) while the same calls with IPv4 first
answered in seconds. curl / browsers fall back to IPv4 by themselves, so only Modal was affected. Only the ORDER of the
addresses changes: a host that has no IPv4 address is still reached over IPv6.
"""
import socket

if not getattr(socket.getaddrinfo, "_ipv4_first", False):
    _getaddrinfo = socket.getaddrinfo

    def getaddrinfo(*args, **kwargs):
        return sorted(_getaddrinfo(*args, **kwargs), key=lambda r: r[0] != socket.AF_INET)

    getaddrinfo._ipv4_first = True
    socket.getaddrinfo = getaddrinfo
