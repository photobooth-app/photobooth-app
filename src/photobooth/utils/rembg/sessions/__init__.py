from .base import BaseSession
from .modnet import ModnetSession
from .modnetfp16 import ModnetFp16Session
from .modnetquantized import ModnetQuantizedSession
from .u2net import U2netSession
from .u2netp import U2netpSession

sessions: dict[str, type[BaseSession]] = {}

sessions[U2netSession.name()] = U2netSession
sessions[U2netpSession.name()] = U2netpSession
sessions[ModnetSession.name()] = ModnetSession
sessions[ModnetFp16Session.name()] = ModnetFp16Session
sessions[ModnetQuantizedSession.name()] = ModnetQuantizedSession

sessions_names = list(sessions.keys())
sessions_class = list(sessions.values())
