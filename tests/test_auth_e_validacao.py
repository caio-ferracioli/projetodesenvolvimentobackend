from datetime import UTC, datetime, timedelta

import jwt

from tests.conftest import assert_erro


def test_t01_login_valido_devolve_token(api):
    r = api.client.post("/auth/login", json={"email": "cliente@raizes.com", "senha": "Senha@123"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["tokenType"] == "Bearer" and corpo["expiresIn"] == 3600
    assert corpo["accessToken"].count(".") == 2


def test_login_senha_errada_e_email_inexistente_dao_o_mesmo_erro(api):
    errada = api.client.post("/auth/login", json={"email": "cliente@raizes.com", "senha": "errada123"})
    inexistente = api.client.post("/auth/login", json={"email": "ninguem@raizes.com", "senha": "Senha@123"})
    assert_erro(errada, 401, "CREDENCIAIS_INVALIDAS")
    assert_erro(inexistente, 401, "CREDENCIAIS_INVALIDAS")


def test_t02_sem_token_retorna_401(api):
    r = api.get("/pedidos")
    corpo = assert_erro(r, 401, "TOKEN_AUSENTE")
    assert corpo["caminho"] == "/pedidos"
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_token_invalido_e_expirado_retornam_401(api):
    assert_erro(api.get("/pedidos", headers={"Authorization": "Bearer lixo"}), 401, "TOKEN_INVALIDO")

    expirado = jwt.encode(
        {"sub": "1", "perfil": "ADMIN", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        api.settings.jwt_secret,
        algorithm="HS256",
    )
    assert_erro(api.get("/pedidos", headers={"Authorization": f"Bearer {expirado}"}), 401, "TOKEN_EXPIRADO")

    falso = jwt.encode(
        {"sub": "1", "perfil": "ADMIN", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "outro-segredo-qualquer-com-mais-de-32-caracteres",
        algorithm="HS256",
    )
    assert_erro(api.get("/pedidos", headers={"Authorization": f"Bearer {falso}"}), 401, "TOKEN_INVALIDO")


def test_t03_perfil_sem_permissao_retorna_403(api):
    corpo = {"nome": "Prato Novo", "categoria": "Pratos", "preco": 10}
    r = api.post("/produtos", "cliente@raizes.com", json=corpo)
    erro = assert_erro(r, 403, "PERFIL_SEM_PERMISSAO")
    assert erro["detalhes"][0]["perfisPermitidos"] == ["GERENTE", "ADMIN"]

    assert api.post("/produtos", "gerente@raizes.com", json=corpo).status_code == 201


def test_t04_campo_obrigatorio_ausente_retorna_422(api):
    r = api.post(
        "/pedidos",
        "cliente@raizes.com",
        json={"unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 1}]},
    )
    erro = assert_erro(r, 422, "VALIDACAO_FALHOU")
    assert {"campo": "canalPedido", "mensagem": "Campo obrigatório."} in erro["detalhes"]


def test_canal_pedido_invalido_retorna_422(api):
    r = api.criar_pedido(canal="DRONE")
    erro = assert_erro(r, 422, "VALIDACAO_FALHOU")
    assert erro["detalhes"][0]["campo"] == "canalPedido"
    assert "APP" in erro["detalhes"][0]["mensagem"]


def test_t05_formato_invalido_retorna_422(api):
    r = api.criar_pedido(itens=((1, -2),))
    erro = assert_erro(r, 422, "VALIDACAO_FALHOU")
    assert erro["detalhes"][0]["campo"] == "itens.0.quantidade"

    r = api.post("/auth/registro", json={"nome": "Ana", "email": "isto-nao-e-email", "senha": "Senha@123"})
    erro = assert_erro(r, 422, "VALIDACAO_FALHOU")
    assert erro["detalhes"][0] == {"campo": "email", "mensagem": "E-mail inválido."}

    r = api.post("/auth/registro", json={"nome": "Ana", "email": "ana@exemplo.com", "senha": "123"})
    assert_erro(r, 422, "VALIDACAO_FALHOU")
    assert_erro(api.get("/pedidos?limit=1000", "gerente@raizes.com"), 422, "VALIDACAO_FALHOU")
    assert_erro(api.post("/auth/login", content=b"{quebrado", headers={"Content-Type": "application/json"}), 422, "VALIDACAO_FALHOU")


def test_autenticacao_tem_precedencia_sobre_validacao(api):
    assert_erro(api.post("/pedidos", json={}), 401, "TOKEN_AUSENTE")


def test_rota_inexistente_e_metodo_errado_usam_o_padrao_de_erro(api):
    assert_erro(api.get("/nao-existe"), 404, "RECURSO_NAO_ENCONTRADO")
    assert_erro(api.delete("/auth/login"), 405, "METODO_NAO_PERMITIDO")


def test_registro_cria_cliente_e_bloqueia_email_duplicado(api):
    corpo = {"nome": "Ana Souza", "email": "Ana@Exemplo.com", "senha": "Senha@123", "consentimentoFidelidade": True}
    r = api.post("/auth/registro", json=corpo)
    assert r.status_code == 201
    usuario = r.json()
    assert usuario["perfil"] == "CLIENTE" and usuario["email"] == "ana@exemplo.com"
    assert usuario["consentimentoFidelidade"] is True and usuario["consentimentoEm"]
    assert "senha" not in usuario and "senhaHash" not in usuario

    assert_erro(api.post("/auth/registro", json=corpo), 409, "EMAIL_JA_CADASTRADO")

    login = api.client.post("/auth/login", json={"email": "ana@exemplo.com", "senha": "Senha@123"})
    assert login.status_code == 200


def test_me_e_refresh(api):
    me = api.get("/auth/me", "atendente@raizes.com").json()
    assert me["perfil"] == "ATENDENTE" and me["unidadeId"] == 1
    assert api.post("/auth/refresh", "atendente@raizes.com").json()["accessToken"]


def test_swagger_documenta_o_padrao_de_erro_e_a_seguranca_bearer(api):
    doc = api.client.get("/openapi.json").json()
    assert api.client.get("/docs").status_code == 200

    for caminho, operacoes in doc["paths"].items():
        for metodo, operacao in operacoes.items():
            r422 = operacao["responses"].get("422")
            if r422:
                assert r422["content"]["application/json"]["schema"]["$ref"].endswith("/ErroSaida"), (metodo, caminho)
    assert "HTTPValidationError" not in doc["components"]["schemas"]
    assert "HTTPBearer" in doc["components"]["securitySchemes"]

    for rota in ("/auth/login", "/produtos", "/estoque", "/pedidos", "/pagamentos", "/fidelidade", "/auditorias"):
        assert rota in doc["paths"]


def test_senha_fica_com_hash_no_banco(api):
    with api.container.uow() as uow:
        usuario = uow.usuarios.obter_por_email("cliente@raizes.com")
    assert usuario.senha_hash.startswith("$2b$") and "Senha@123" not in usuario.senha_hash
