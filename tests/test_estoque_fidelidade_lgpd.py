from tests.conftest import BAIAO, RECIFE, SALVADOR, assert_erro


def test_movimentacoes_manuais_de_estoque(api):
    base = {"unidadeId": RECIFE, "produtoId": BAIAO}
    antes = api.saldo_estoque(BAIAO)

    entrada = api.post("/estoque/movimentacoes", "gerente@raizes.com", json={**base, "tipo": "ENTRADA", "quantidade": 10})
    assert entrada.status_code == 201
    assert entrada.json()["variacao"] == 10 and entrada.json()["saldoApos"] == antes + 10

    saida = api.post("/estoque/movimentacoes", "gerente@raizes.com", json={**base, "tipo": "SAIDA", "quantidade": 4})
    assert saida.json()["saldoApos"] == antes + 6

    ajuste = api.post("/estoque/movimentacoes", "gerente@raizes.com", json={**base, "tipo": "AJUSTE", "quantidade": 20})
    assert ajuste.json()["saldoApos"] == 20 and ajuste.json()["variacao"] == 20 - (antes + 6)
    assert api.saldo_estoque(BAIAO) == 20

    historico = api.get(f"/estoque/movimentacoes?unidadeId={RECIFE}&produtoId={BAIAO}", "gerente@raizes.com").json()
    assert historico["total"] == 3 and historico["items"][0]["tipo"] == "AJUSTE"


def test_saida_maior_que_o_saldo_retorna_409_e_nao_altera_nada(api):
    antes = api.saldo_estoque(BAIAO)
    r = api.post(
        "/estoque/movimentacoes",
        "gerente@raizes.com",
        json={"unidadeId": RECIFE, "produtoId": BAIAO, "tipo": "SAIDA", "quantidade": antes + 1},
    )
    assert_erro(r, 409, "ESTOQUE_INSUFICIENTE")
    assert api.saldo_estoque(BAIAO) == antes


def test_estoque_validacoes_e_permissoes(api):
    base = {"unidadeId": RECIFE, "produtoId": BAIAO, "tipo": "ENTRADA", "quantidade": 1}
    assert_erro(api.post("/estoque/movimentacoes", "atendente@raizes.com", json=base), 403, "PERFIL_SEM_PERMISSAO")
    assert_erro(api.post("/estoque/movimentacoes", "gerente@raizes.com", json={**base, "produtoId": 999}), 404, "PRODUTO_NAO_ENCONTRADO")
    assert_erro(api.post("/estoque/movimentacoes", "gerente@raizes.com", json={**base, "unidadeId": 999}), 404, "UNIDADE_NAO_ENCONTRADA")
    assert_erro(api.post("/estoque/movimentacoes", "gerente@raizes.com", json={**base, "quantidade": -1}), 422, "VALIDACAO_FALHOU")
    assert_erro(api.post("/estoque/movimentacoes", "gerente@raizes.com", json={**base, "quantidade": 0}), 422, "QUANTIDADE_INVALIDA")
    assert_erro(api.post("/estoque/movimentacoes", "gerente@raizes.com", json={**base, "tipo": "BAIXA_PEDIDO"}), 422, "VALIDACAO_FALHOU")
    assert_erro(api.get("/estoque", "cliente@raizes.com"), 403, "PERFIL_SEM_PERMISSAO")


def test_entrada_cria_o_estoque_de_um_produto_novo_na_unidade(api):
    produto = api.post("/produtos", "gerente@raizes.com", json={"nome": "Bolo de Rolo", "categoria": "Sobremesas", "preco": 12.5})
    produto_id = produto.json()["id"]
    r = api.post(
        "/estoque/movimentacoes",
        "gerente@raizes.com",
        json={"unidadeId": SALVADOR, "produtoId": produto_id, "tipo": "ENTRADA", "quantidade": 7},
    )
    assert r.status_code == 201 and r.json()["saldoApos"] == 7
    itens = api.client.get(f"/unidades/{SALVADOR}/cardapio").json()["itens"]
    assert "Bolo de Rolo" in [i["nome"] for i in itens]


def test_atendente_so_enxerga_o_estoque_da_propria_unidade(api):
    itens = api.get("/estoque?unidadeId=2&limit=100", "atendente@raizes.com").json()["items"]
    assert itens and {i["unidadeId"] for i in itens} == {RECIFE}


def test_cardapio_e_publico_e_por_unidade(api):
    r = api.client.get("/unidades/3/cardapio")
    assert r.status_code == 200
    nomes = [i["nome"] for i in r.json()["itens"]]
    assert "Moqueca Baiana" not in nomes and "Baião de Dois" in nomes
    assert_erro(api.client.get("/unidades/999/cardapio"), 404, "UNIDADE_NAO_ENCONTRADA")


def test_produtos_crud_e_exclusao_logica(api):
    criado = api.post("/produtos", "gerente@raizes.com", json={"nome": "Queijadinha", "categoria": "Sobremesas", "preco": 6.5})
    assert criado.status_code == 201
    produto_id = criado.json()["id"]
    assert api.put(f"/produtos/{produto_id}", "gerente@raizes.com", json={"nome": "Queijadinha", "categoria": "Sobremesas", "preco": 7}).json()["preco"] == 7

    assert_erro(api.post("/produtos", "gerente@raizes.com", json={"nome": "X", "categoria": "Y", "preco": 0}), 422, "VALIDACAO_FALHOU")
    assert_erro(api.post("/produtos", "gerente@raizes.com", json={"nome": "Caro", "categoria": "Y", "preco": "10.999"}), 422, "VALIDACAO_FALHOU")

    assert api.delete(f"/produtos/{produto_id}", "gerente@raizes.com").status_code == 204
    assert_erro(api.get(f"/produtos/{produto_id}", "gerente@raizes.com"), 404, "PRODUTO_NAO_ENCONTRADO")
    assert produto_id not in [p["id"] for p in api.get("/produtos?limit=100", "gerente@raizes.com").json()["items"]]


def test_mudar_o_preco_nao_altera_pedidos_antigos(api):
    pedido = api.criar_pedido(itens=((BAIAO, 1),)).json()
    api.put(f"/produtos/{BAIAO}", "gerente@raizes.com", json={"nome": "Baião de Dois", "categoria": "Pratos", "preco": 99})
    assert api.pedido(pedido["id"])["valorTotal"] == 38.9


def test_pontos_so_sao_acumulados_com_consentimento(api):
    com = api.criar_pedido(como="cliente@raizes.com", itens=((BAIAO, 2),)).json()
    sem = api.criar_pedido(como="cliente2@raizes.com", itens=((BAIAO, 2),)).json()
    api.pagar(com["id"], como="cliente@raizes.com")
    api.pagar(sem["id"], como="cliente2@raizes.com")

    assert api.get("/fidelidade", "cliente@raizes.com").json()["saldo"] == 77
    assert api.get("/fidelidade", "cliente2@raizes.com").json()["saldo"] == 0


def test_consentimento_e_resgate(api):
    pedido = api.criar_pedido(itens=((BAIAO, 2),)).json()
    api.pagar(pedido["id"])

    assert_erro(api.post("/fidelidade/resgates", "cliente@raizes.com", json={"pontos": 1000}), 409, "SALDO_INSUFICIENTE")
    assert_erro(api.post("/fidelidade/resgates", "cliente@raizes.com", json={"pontos": 0}), 422, "VALIDACAO_FALHOU")
    assert api.post("/fidelidade/resgates", "cliente@raizes.com", json={"pontos": 10}).status_code == 201
    resumo = api.get("/fidelidade", "cliente@raizes.com").json()
    assert resumo["saldo"] == 67 and resumo["consentimento"] is True

    assert_erro(api.post("/fidelidade/resgates", "cliente2@raizes.com", json={"pontos": 1}), 422, "CONSENTIMENTO_NECESSARIO")

    dado = api.put("/fidelidade/consentimento", "cliente2@raizes.com", json={"consentimento": True}).json()
    assert dado["consentimento"] is True and dado["consentimentoEm"]
    revogado = api.put("/fidelidade/consentimento", "cliente@raizes.com", json={"consentimento": False}).json()
    assert revogado["consentimento"] is False and revogado["consentimentoEm"] is None and revogado["saldo"] == 67


def test_titular_pode_anonimizar_os_proprios_dados(api):
    pedido = api.criar_pedido().json()
    token_antigo = api.token("cliente@raizes.com")
    me = api.get("/auth/me", "cliente@raizes.com").json()

    assert api.delete(f"/usuarios/{me['id']}", "cliente@raizes.com").status_code == 204

    assert_erro(api.get("/auth/me", headers={"Authorization": f"Bearer {token_antigo}"}), 401, "TOKEN_INVALIDO")
    assert_erro(api.client.post("/auth/login", json={"email": "cliente@raizes.com", "senha": "Senha@123"}), 401, "CREDENCIAIS_INVALIDAS")

    usuarios = api.get("/usuarios?limit=100", "admin@raizes.com").json()["items"]
    anonimo = next(u for u in usuarios if u["id"] == me["id"])
    assert anonimo["nome"] == "Titular anonimizado" and anonimo["email"].endswith("@anonimo.invalid")
    assert api.pedido(pedido["id"])["clienteId"] == me["id"]

    assert_erro(api.delete(f"/usuarios/{me['id']}", "admin@raizes.com"), 409, "USUARIO_JA_ANONIMIZADO")


def test_so_admin_ou_o_proprio_titular_anonimiza(api):
    outro = api.get("/auth/me", "cliente2@raizes.com").json()["id"]
    assert_erro(api.delete(f"/usuarios/{outro}", "cliente@raizes.com"), 403, "ACESSO_NEGADO")
    assert_erro(api.delete("/usuarios/999", "admin@raizes.com"), 404, "USUARIO_NAO_ENCONTRADO")
    assert api.delete(f"/usuarios/{outro}", "admin@raizes.com").status_code == 204


def test_gestao_de_usuarios(api):
    assert_erro(api.get("/usuarios", "cliente@raizes.com"), 403, "PERFIL_SEM_PERMISSAO")
    assert api.get("/usuarios", "gerente@raizes.com").json()["total"] == 6

    novo = {"nome": "Nova Cozinheira", "email": "nova@raizes.com", "senha": "Senha@123", "perfil": "COZINHA", "unidadeId": SALVADOR}
    assert_erro(api.post("/usuarios", "gerente@raizes.com", json=novo), 403, "PERFIL_SEM_PERMISSAO")
    assert api.post("/usuarios", "admin@raizes.com", json=novo).status_code == 201
    assert_erro(api.post("/usuarios", "admin@raizes.com", json=novo), 409, "EMAIL_JA_CADASTRADO")
    assert_erro(api.post("/usuarios", "admin@raizes.com", json={**novo, "email": "x@raizes.com", "unidadeId": None}), 422, "UNIDADE_OBRIGATORIA")
    assert_erro(api.post("/usuarios", "admin@raizes.com", json={**novo, "email": "y@raizes.com", "unidadeId": 999}), 404, "UNIDADE_NAO_ENCONTRADA")


def test_t11_acoes_sensiveis_geram_auditoria(api):
    pedido = api.criar_pedido().json()
    api.pagar(pedido["id"])
    api.patch(f"/pedidos/{pedido['id']}/status", "cozinha@raizes.com", json={"status": "PRONTO"})
    cancelado = api.criar_pedido().json()
    api.patch(f"/pedidos/{cancelado['id']}/status", "cliente@raizes.com", json={"status": "CANCELADO", "motivo": "mudei de ideia"})

    r = api.get("/auditorias?limit=100", "gerente@raizes.com")
    assert r.status_code == 200
    acoes = [a["acao"] for a in r.json()["items"]]
    for esperada in (
        "PEDIDO_CRIADO",
        "PAGAMENTO_INICIADO",
        "PAGAMENTO_APROVADO",
        "PEDIDO_STATUS_ALTERADO",
        "PEDIDO_CANCELADO",
    ):
        assert esperada in acoes, f"faltou auditar {esperada}"

    criacao = api.get("/auditorias?acao=PEDIDO_CRIADO&entidade=Pedido", "gerente@raizes.com").json()["items"][-1]
    assert criacao["entidadeId"] == pedido["id"] and criacao["usuarioId"] is not None
    assert criacao["detalhes"]["canalPedido"] == "APP" and criacao["ip"] == "testclient"

    mudanca = api.get("/auditorias?acao=PEDIDO_STATUS_ALTERADO", "gerente@raizes.com").json()["items"][0]
    assert mudanca["detalhes"] == {"de": "EM_PREPARO", "para": "PRONTO"}


def test_t12_so_gerencia_consulta_a_auditoria(api):
    assert_erro(api.get("/auditorias", "cliente@raizes.com"), 403, "PERFIL_SEM_PERMISSAO")
    assert_erro(api.get("/auditorias", "atendente@raizes.com"), 403, "PERFIL_SEM_PERMISSAO")
    assert api.get("/auditorias", "admin@raizes.com").status_code == 200


def test_auditoria_nao_guarda_dados_sensiveis(api):
    api.post("/auth/registro", json={"nome": "Ana", "email": "ana@exemplo.com", "senha": "Senha@123"})
    texto = api.get("/auditorias?limit=100", "gerente@raizes.com").text
    assert "Senha@123" not in texto and "senhaHash" not in texto and "$2b$" not in texto


def test_saude(api):
    assert api.client.get("/saude").json() == {"status": "ok"}
