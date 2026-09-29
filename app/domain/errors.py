from typing import Any


class ErroDeDominio(Exception):

    def __init__(self, codigo: str, mensagem: str, detalhes: list[dict[str, Any]] | None = None):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes or []


class RegraDeNegocio(ErroDeDominio):
    pass


class NaoAutenticado(ErroDeDominio):
    pass


class AcessoNegado(ErroDeDominio):
    pass


class NaoEncontrado(ErroDeDominio):
    pass


class Conflito(ErroDeDominio):
    pass


class ServicoIndisponivel(ErroDeDominio):
    pass


class GatewayIndisponivel(ServicoIndisponivel):
    pass
