from app.application.autenticacao import normalizar_email
from app.application.comum import FabricaUoW, Pagina, registrar_auditoria
from app.domain.entities import Usuario
from app.domain.enums import Perfil
from app.domain.errors import AcessoNegado, Conflito, NaoEncontrado, RegraDeNegocio
from app.domain.ports import HasherSenha


class ServicoUsuarios:
    def __init__(self, uow: FabricaUoW, hasher: HasherSenha):
        self._uow = uow
        self._hasher = hasher

    def listar(self, *, page: int, limit: int) -> Pagina[Usuario]:
        with self._uow() as uow:
            itens, total = uow.usuarios.listar(page=page, limit=limit)
        return Pagina(itens, page, limit, total)

    def criar(
        self,
        ator: Usuario,
        *,
        nome: str,
        email: str,
        senha: str,
        perfil: Perfil,
        unidade_id: int | None,
        telefone: str | None,
    ) -> Usuario:
        email = normalizar_email(email)
        if perfil in (Perfil.ATENDENTE, Perfil.COZINHA) and unidade_id is None:
            raise RegraDeNegocio("UNIDADE_OBRIGATORIA", f"O perfil {perfil} precisa de uma unidade.")

        with self._uow() as uow:
            if unidade_id is not None and uow.unidades.obter(unidade_id) is None:
                raise NaoEncontrado("UNIDADE_NAO_ENCONTRADA", "Unidade informada não existe.")
            if uow.usuarios.obter_por_email(email):
                raise Conflito("EMAIL_JA_CADASTRADO", "Já existe um usuário com este e-mail.")

            usuario = uow.usuarios.adicionar(
                Usuario(
                    nome=nome.strip(),
                    email=email,
                    senha_hash=self._hasher.gerar(senha),
                    perfil=perfil,
                    unidade_id=unidade_id,
                    telefone=telefone,
                )
            )
            registrar_auditoria(
                uow,
                "USUARIO_CRIADO",
                entidade="Usuario",
                entidade_id=usuario.id,
                detalhes={"perfil": perfil, "unidadeId": unidade_id},
                usuario_id=ator.id,
            )
            uow.commit()
            return usuario

    def anonimizar(self, ator: Usuario, usuario_id: int) -> None:
        if ator.perfil != Perfil.ADMIN and ator.id != usuario_id:
            raise AcessoNegado("ACESSO_NEGADO", "Você só pode eliminar os seus próprios dados.")

        with self._uow() as uow:
            alvo = uow.usuarios.obter(usuario_id)
            if alvo is None:
                raise NaoEncontrado("USUARIO_NAO_ENCONTRADO", "Usuário não encontrado.")
            if alvo.anonimizado:
                raise Conflito("USUARIO_JA_ANONIMIZADO", "Os dados deste usuário já foram anonimizados.")

            alvo.anonimizar()
            uow.usuarios.salvar(alvo)
            registrar_auditoria(
                uow,
                "USUARIO_ANONIMIZADO",
                entidade="Usuario",
                entidade_id=alvo.id,
                detalhes={"solicitadoPor": ator.id},
                usuario_id=ator.id,
            )
            uow.commit()
