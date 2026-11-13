from tests.conftest import (
    ACARAJE,
    BAIAO,
    FORTALEZA,
    MOQUECA,
    RECIFE,
    SALVADOR,
    TAPIOCA,
    assert_erro,
)


def test_t06_pedido_valido_retorna_201(api):
    r = api.criar_pedido(itens=((BAIAO, 2), (TAPIOCA, 1)), observacao="sem pimenta")
    assert r.status_code == 201
    pedido = r.json()
    assert pedido["status"] == "AGUARDANDO_PAGAMENTO"
    assert pedido["canalPedido"] == "APP" and pedido["unidadeId"] == RECIFE
    assert pedido["valorTotal"] == 92.3
    assert {i["nomeProduto"]: i["subtotal"] for i in pedido["itens"]} == {
        "Baião de Dois": 77.8,
        "Tapioca de Queijo Coalho": 14.5,
    }
    assert pedido["pagamento"] is None


def test_itens_repetidos_viram_uma_linha(api):
    pedido = api.criar_pedido(itens=((BAIAO, 1), (BAIAO, 2))).json()
    assert len(pedido["itens"]) == 1 and pedido["itens"][0]["quantidade"] == 3


def test_criar_pedido_nao_reserva_estoque(api):
    antes = api.saldo_estoque(BAIAO)
    assert api.criar_pedido(itens=((BAIAO, 5),)).status_code == 201
    assert api.saldo_estoque(BAIAO) == antes


def test_t07_produto_ou_unidade_inexistente_retorna_404(api):
    erro = assert_erro(api.criar_pedido(itens=((9999, 1),)), 404, "PRODUTO_NAO_ENCONTRADO")
    assert erro["detalhes"] == [{"produtoId": 9999}]
    assert_erro(api.criar_pedido(unidade=999), 404, "UNIDADE_NAO_ENCONTRADA")
    assert_erro(api.get("/pedidos/9999", "gerente@raizes.com"), 404, "PEDIDO_NAO_ENCONTRADO")


def test_t08_estoque_insuficiente_retorna_409(api):
    r = api.criar_pedido(itens=((ACARAJE, 4),))
    erro = assert_erro(r, 409, "ESTOQUE_INSUFICIENTE")
    assert erro["detalhes"] == [{"produtoId": ACARAJE, "solicitado": 4, "disponivel": 3}]


def test_produto_que_a_unidade_nao_vende_retorna_409(api):
    assert_erro(api.criar_pedido(unidade=FORTALEZA, itens=((MOQUECA, 1),)), 409, "ESTOQUE_INSUFICIENTE")
    assert api.criar_pedido(unidade=SALVADOR, itens=((MOQUECA, 1),)).status_code == 201


def test_item_bloqueado_por_indisponibilidade_nao_pode_ser_pedido(api):
    estoque_id = api.get(f"/estoque?unidadeId={RECIFE}&produtoId={BAIAO}", "gerente@raizes.com").json()["items"][0]["id"]
    r = api.patch(f"/estoque/{estoque_id}/disponibilidade", "gerente@raizes.com", json={"disponivel": False})
    assert r.status_code == 200 and r.json()["disponivel"] is False

    assert_erro(api.criar_pedido(itens=((BAIAO, 1),)), 409, "ESTOQUE_INSUFICIENTE")
    cardapio = api.client.get(f"/unidades/{RECIFE}/cardapio").json()
    assert BAIAO not in [i["produtoId"] for i in cardapio["itens"]]


def test_unidade_inativa_retorna_422(api):
    api.put(
        f"/unidades/{RECIFE}",
        "admin@raizes.com",
        json={"nome": "Recife", "cidade": "Recife", "ativa": False},
    )
    assert_erro(api.criar_pedido(), 422, "UNIDADE_INATIVA")


def test_filtro_por_canal_pedido(api):
    api.criar_pedido(canal="APP")
    api.criar_pedido(canal="TOTEM")
    api.criar_pedido(canal="TOTEM")

    todos = api.get("/pedidos", "gerente@raizes.com").json()
    assert todos["total"] == 3

    totem = api.get("/pedidos?canalPedido=TOTEM", "gerente@raizes.com").json()
    assert totem["total"] == 2 and {p["canalPedido"] for p in totem["items"]} == {"TOTEM"}

    assert_erro(api.get("/pedidos?canalPedido=DRONE", "gerente@raizes.com"), 422, "VALIDACAO_FALHOU")


def test_paginacao(api):
    for _ in range(5):
        api.criar_pedido()
    pagina = api.get("/pedidos?page=2&limit=2", "gerente@raizes.com").json()
    assert (pagina["page"], pagina["limit"], pagina["total"], pagina["pages"]) == (2, 2, 5, 3)
    assert len(pagina["items"]) == 2
    ultima = api.get("/pedidos?page=3&limit=2", "gerente@raizes.com").json()
    assert len(ultima["items"]) == 1


def test_cliente_so_ve_os_proprios_pedidos(api):
    pedido = api.criar_pedido(como="cliente@raizes.com").json()
    assert api.get("/pedidos", "cliente2@raizes.com").json()["total"] == 0
    assert_erro(api.get(f"/pedidos/{pedido['id']}", "cliente2@raizes.com"), 403, "ACESSO_NEGADO")
    assert api.get(f"/pedidos/{pedido['id']}", "cliente@raizes.com").status_code == 200


def test_equipe_so_ve_a_propria_unidade(api):
    api.criar_pedido(unidade=SALVADOR, como="gerente@raizes.com")
    recife = api.criar_pedido(unidade=RECIFE).json()

    lista = api.get("/pedidos?unidadeId=2", "atendente@raizes.com").json()
    assert [p["id"] for p in lista["items"]] == [recife["id"]]


def test_cozinha_nao_cria_pedido_e_atendente_so_da_propria_unidade(api):
    assert_erro(api.criar_pedido(como="cozinha@raizes.com"), 403, "PERFIL_SEM_PERMISSAO")
    assert_erro(api.criar_pedido(como="atendente@raizes.com", unidade=SALVADOR), 403, "ACESSO_NEGADO")


def test_balcao_registra_pedido_para_um_cliente(api):
    cliente_id = api.get("/auth/me", "cliente@raizes.com").json()["id"]
    r = api.criar_pedido(como="atendente@raizes.com", canal="BALCAO", clienteId=cliente_id)
    assert r.status_code == 201 and r.json()["clienteId"] == cliente_id
    assert api.get("/pedidos", "cliente@raizes.com").json()["total"] == 1

    anonimo = api.criar_pedido(como="atendente@raizes.com", canal="BALCAO")
    assert anonimo.status_code == 201 and anonimo.json()["clienteId"] is None
    assert_erro(
        api.criar_pedido(como="atendente@raizes.com", canal="BALCAO", clienteId=999), 404, "CLIENTE_NAO_ENCONTRADO"
    )


def test_idempotencia_mesma_chave_devolve_o_mesmo_pedido(api):
    cabecalho = {"Idempotency-Key": "abc-123"}
    corpo = {"unidadeId": RECIFE, "canalPedido": "APP", "itens": [{"produtoId": BAIAO, "quantidade": 1}]}

    primeira = api.post("/pedidos", "cliente@raizes.com", json=corpo, headers=cabecalho)
    segunda = api.post("/pedidos", "cliente@raizes.com", json=corpo, headers=cabecalho)

    assert primeira.status_code == 201
    assert segunda.status_code == 200 and segunda.headers["Idempotency-Replayed"] == "true"
    assert segunda.json()["id"] == primeira.json()["id"]
    assert api.get("/pedidos", "cliente@raizes.com").json()["total"] == 1

    outro = api.post("/pedidos", "cliente2@raizes.com", json=corpo, headers=cabecalho)
    assert outro.status_code == 201 and outro.json()["id"] != primeira.json()["id"]
