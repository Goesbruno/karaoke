import hashlib, hmac
from fastapi import Header, HTTPException

def _h(t: str) -> str: return hashlib.sha256(t.encode()).hexdigest()

class Authenticator:
    def __init__(self, tokens: dict[str, str], roles: dict[str, list[str]]):
        self._by_hash = {_h(t): r for t, r in tokens.items() if t}
        self.roles = roles

    def role_of(self, token: str | None) -> str | None:
        if not token: return None
        th = _h(token)
        for h, r in self._by_hash.items():
            if hmac.compare_digest(h, th): return r
        return None

    def require(self, permission: str):
        def dep(authorization: str | None = Header(default=None)):
            token = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None
            role = self.role_of(token)
            if role is None: raise HTTPException(401, "token ausente ou invalido")
            if permission not in self.roles.get(role, []): raise HTTPException(403, "permissao insuficiente")
            return role
        return dep
