import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.domain.enums import Perfil
from app.domain.errors import NaoAutenticado
from app.domain.ports import DadosToken, TokenEmitido


class HasherBcrypt:

    def __init__(self, rounds: int = 12):
        self._rounds = rounds

    @staticmethod
    def _bytes(senha: str) -> bytes:
        return senha.encode("utf-8")[:72]

    def gerar(self, senha: str) -> str:
        return bcrypt.hashpw(self._bytes(senha), bcrypt.gensalt(rounds=self._rounds)).decode("ascii")

    def verificar(self, senha: str, senha_hash: str) -> bool:
        try:
            return bcrypt.checkpw(self._bytes(senha), senha_hash.encode("ascii"))
        except ValueError:
            return False


class ServicoTokenJwt:
    def __init__(self, segredo: str, algoritmo: str, validade_minutos: int):
        self._segredo = segredo
        self._algoritmo = algoritmo
        self._validade = timedelta(minutes=validade_minutos)

    def emitir(self, usuario_id: int, perfil: Perfil) -> TokenEmitido:
        agora = datetime.now(UTC)
        claims = {
            "sub": str(usuario_id),
            "perfil": str(perfil),
            "iat": agora,
            "exp": agora + self._validade,
        }
        token = jwt.encode(claims, self._segredo, algorithm=self._algoritmo)
        return TokenEmitido(token=token, expira_em_segundos=int(self._validade.total_seconds()))

    def ler(self, token: str) -> DadosToken:
        try:
            claims = jwt.decode(
                token, self._segredo, algorithms=[self._algoritmo], options={"require": ["exp", "sub"]}
            )
            return DadosToken(usuario_id=int(claims["sub"]), perfil=Perfil(claims["perfil"]))
        except jwt.ExpiredSignatureError:
            raise NaoAutenticado("TOKEN_EXPIRADO", "O token expirou. Faça login novamente.") from None
        except (jwt.InvalidTokenError, KeyError, ValueError):
            raise NaoAutenticado("TOKEN_INVALIDO", "Token de acesso inválido.") from None


def assinar_payload(segredo: str, corpo: bytes) -> str:
    return hmac.new(segredo.encode("utf-8"), corpo, hashlib.sha256).hexdigest()


def assinatura_valida(segredo: str, corpo: bytes, assinatura: str | None) -> bool:
    if not assinatura:
        return False
    return hmac.compare_digest(assinar_payload(segredo, corpo), assinatura.strip().lower())
