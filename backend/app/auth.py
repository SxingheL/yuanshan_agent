import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import User

try:
    from jose import JWTError, jwt  # type: ignore
except ImportError:
    class JWTError(Exception):
        pass

    class _SimpleJWT:
        @staticmethod
        def _b64encode(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

        @staticmethod
        def _b64decode(data: str) -> bytes:
            padding = "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode((data + padding).encode("utf-8"))

        def encode(self, payload: dict, secret: str, algorithm: str = "HS256") -> str:
            if algorithm != "HS256":
                raise JWTError("仅支持 HS256")
            header = {"alg": algorithm, "typ": "JWT"}
            header_part = self._b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
            payload_part = self._b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
            signing_input = f"{header_part}.{payload_part}".encode("utf-8")
            signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
            return f"{header_part}.{payload_part}.{self._b64encode(signature)}"

        def decode(self, token: str, secret: str, algorithms: List[str]) -> dict:
            if "HS256" not in algorithms:
                raise JWTError("仅支持 HS256")
            parts = token.split(".")
            if len(parts) != 3:
                raise JWTError("令牌格式错误")
            header_part, payload_part, signature_part = parts
            signing_input = f"{header_part}.{payload_part}".encode("utf-8")
            expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
            actual_signature = self._b64decode(signature_part)
            if not hmac.compare_digest(expected_signature, actual_signature):
                raise JWTError("签名无效")
            payload = json.loads(self._b64decode(payload_part).decode("utf-8"))
            exp = payload.get("exp")
            if exp is not None and int(exp) < int(datetime.now(timezone.utc).timestamp()):
                raise JWTError("令牌已过期")
            return payload

    jwt = _SimpleJWT()

try:
    from passlib.context import CryptContext  # type: ignore
except ImportError:
    CryptContext = None


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    if pwd_context:
        return pwd_context.hash(password)
    salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return "pbkdf2_sha256$100000$" + base64.b64encode(salt).decode("utf-8") + "$" + base64.b64encode(hashed).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    if pwd_context:
        try:
            return pwd_context.verify(plain_password, password_hash)
        except Exception:
            return False
    try:
        _, rounds, salt_b64, hash_b64 = password_hash.split("$", 3)
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected = base64.b64decode(hash_b64.encode("utf-8"))
        actual = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "school_id": user.school_id,
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已失效",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="身份令牌无效",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除",
        )
    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        return None

    return db.query(User).filter(User.id == user_id).first()


def require_role(*roles: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该资源",
            )
        return current_user

    return dependency
