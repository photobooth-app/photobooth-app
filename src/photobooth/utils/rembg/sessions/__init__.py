from .base import BaseSession
from .modnet import ModnetSession
from .u2net import U2netSession
from .u2netp import U2netpSession

sessions: dict[str, type[BaseSession]] = {}

sessions[ModnetSession.name()] = ModnetSession
sessions[U2netSession.name()] = U2netSession
sessions[U2netpSession.name()] = U2netpSession

sessions_names = list(sessions.keys())
sessions_class = list(sessions.values())
