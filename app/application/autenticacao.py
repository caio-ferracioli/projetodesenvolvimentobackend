from app.application.comum import FabricaUoW, registrar_auditoria
from app.domain.entities import Usuario
from app.domain.enums import Perfil
from app.domain.errors import Conflito, NaoAutenticado
from app.domain.ports import HasherSenha, ServicoToken, TokenEmitido


def normalizar_email(email: str) -> str:
    return email.strip().lower()


class ServicoAutenticacao:
    def __init__(self, uow: FabricaUoW, hasher: HasherSenha, tokens: ServicoToken):
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._hash_falso = hasher.gerar("senha-descartavel")

    def registrar_cliente(
        self,
        *,
        nome: str,
        email: str,
        senha: str,
        telefone: str | None,
        consentimento_fidelidade: bool,
    ) -> Usuario:
        email = normalizar_email(email)
        with self._uow() as uow:
            if uow.usuarios.obter_por_email(email):
                raise Conflito("EMAIL_JA_CADASTRADO", "Já existe um usuário com este e-mail.")

            usuario = Usuario(
                nome=nome.strip(),
                email=email,
                senha_hash=self._hasher.gerar(senha),
                perfil=Perfil.CLIENTE,
                telefone=telefone,
            )
            usuario.definir_consentimento(consentimento_fidelidade)
            usuario = uow.usuarios.adicionar(usuario)
            registrar_auditoria(
                uow,
                "USUARIO_REGISTRADO",
                entidade="Usuario",
                entidade_id=usuario.id,
                detalhes={"perfil": usuario.perfil, "consentimentoFidelidade": consentimento_fidelidade},
                usuario_id=usuario.id,
            )
            uow.commit()
            return usuario

    def login(self, email: str, senha: str) -> TokenEmitido:
        with self._uow() as uow:
            usuario = uow.usuarios.obter_por_email(normalizar_email(email))

        senha_hash = usuario.senha_hash if usuario else self._hash_falso
        confere = self._hasher.verificar(senha, senha_hash)
        if not usuario or usuario.anonimizado or not confere:
            raise NaoAutenticado("CREDENCIAIS_INVALIDAS", "E-mail ou senha inválidos.")
        return self._tokens.emitir(usuario.id, usuario.perfil)

    def renovar(self, usuario: Usuario) -> TokenEmitido:
        return self._tokens.emitir(usuario.id, usuario.perfil)

    def autenticar(self, token: str) -> Usuario:
        dados = self._tokens.ler(token)
        with self._uow() as uow:
            usuario = uow.usuarios.obter(dados.usuario_id)
        if usuario is None or usuario.anonimizado:
            raise NaoAutenticado("TOKEN_INVALIDO", "O usuário do token não existe mais.")
        return usuario
