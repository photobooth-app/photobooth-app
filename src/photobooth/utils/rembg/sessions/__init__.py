from .base import BaseSession
from .modnet import ModnetSession
from .u2netp import U2netpSession

# from .u2net import U2netSession

sessions: dict[str, type[BaseSession]] = {}

# sessions[U2netSession.name()] = U2netSession # not for now
sessions[U2netpSession.name()] = U2netpSession
sessions[ModnetSession.name()] = ModnetSession

sessions_names = list(sessions.keys())
sessions_class = list(sessions.values())
