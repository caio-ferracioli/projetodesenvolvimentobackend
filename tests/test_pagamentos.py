from tests.conftest import ACARAJE, BAIAO, CARNE_DE_SOL, MOQUECA, assert_erro


def test_t09_pagamento_aprovado_atualiza_o_pedido_e_baixa_o_estoque(api):
    pedido = api.criar_pedido(itens=((BAIAO, 2),)).json()
    antes = api.saldo_estoque(BAIAO)

    r = api.pagar(pedido["id"])
    assert r.status_code == 201
    assert r.json()["status"] == "PENDENTE" and r.json()["transacaoExterna"].startswith("MOCK-")

    atual = api.pedido(pedido["id"])
    assert atual["status"] == "EM_PREPARO"
    assert atual["pagamento"]["status"] == "APROVADO"
    assert atual["pagamento"]["mensagem"] == "Pagamento aprovado (mock)."
    assert api.saldo_estoque(BAIAO) == antes - 2

    consulta = api.get(f"/pagamentos/{r.json()['id']}", "cliente@raizes.com").json()
    assert consulta["status"] == "APROVADO" and consulta["valor"] == 77.8


def test_t10_pagamento_recusado_mantem_o_estoque_e_permite_nova_tentativa(api):
    pedido = api.criar_pedido(itens=((BAIAO, 1),)).json()
    antes = api.saldo_estoque(BAIAO)

    assert api.pagar(pedido["id"], token="tok_recusado").status_code == 201
    atual = api.pedido(pedido["id"])
    assert atual["status"] == "PAGAMENTO_RECUSADO"
    assert atual["pagamento"]["status"] == "RECUSADO"
    assert "recusado" in atual["pagamento"]["mensagem"].lower()
    assert api.saldo_estoque(BAIAO) == antes

    assert api.pagar(pedido["id"]).status_code == 201
    final = api.pedido(pedido["id"])
    assert final["status"] == "EM_PREPARO" and final["pagamento"]["status"] == "APROVADO"
    assert api.saldo_estoque(BAIAO) == antes - 1


def test_valor_acima_do_limite_do_gateway_e_recusado(api):
    pedido = api.criar_pedido(itens=((BAIAO, 50), (CARNE_DE_SOL, 50), (MOQUECA, 50))).json()
    assert pedido["valorTotal"] > 5000
    api.pagar(pedido["id"])
    atual = api.pedido(pedido["id"])
    assert atual["status"] == "PAGAMENTO_RECUSADO" and "limite" in atual["pagamento"]["mensagem"]


def test_gateway_fora_do_ar_retorna_503_e_mantem_o_pedido(api):
    pedido = api.criar_pedido().json()
    r = api.pagar(pedido["id"], token="tok_timeout")
    erro = assert_erro(r, 503, "GATEWAY_INDISPONIVEL")
    assert erro["detalhes"][0]["pedidoId"] == pedido["id"]

    atual = api.pedido(pedido["id"])
    assert atual["status"] == "AGUARDANDO_PAGAMENTO"
    assert atual["pagamento"]["status"] == "FALHA"

    assert api.pagar(pedido["id"]).status_code == 201
    assert api.pedido(pedido["id"])["status"] == "EM_PREPARO"


def test_pagamento_sem_retorno_fica_pendente_e_bloqueia_segunda_tentativa(api):
    pedido = api.criar_pedido().json()
    primeiro = api.pagar(pedido["id"], token="tok_sem_retorno").json()
    assert api.pedido(pedido["id"])["pagamento"]["status"] == "PENDENTE"
    assert_erro(api.pagar(pedido["id"]), 409, "PAGAMENTO_EM_ANDAMENTO")

    r = api.webhook(primeiro["transacaoExterna"], "APROVADO")
    assert r.status_code == 200
    assert r.json() == {
        "pagamentoId": primeiro["id"],
        "statusPagamento": "APROVADO",
        "statusPedido": "EM_PREPARO",
        "processado": True,
    }


def test_webhook_e_idempotente(api):
    pedido = api.criar_pedido(itens=((BAIAO, 1),)).json()
    antes = api.saldo_estoque(BAIAO)
    transacao = api.pagar(pedido["id"], token="tok_sem_retorno").json()["transacaoExterna"]

    assert api.webhook(transacao, "APROVADO").json()["processado"] is True
    repetido = api.webhook(transacao, "APROVADO")
    assert repetido.status_code == 200 and repetido.json()["processado"] is False

    assert api.saldo_estoque(BAIAO) == antes - 1
    contra_ordem = api.webhook(transacao, "RECUSADO")
    assert contra_ordem.json()["processado"] is False
    assert api.pedido(pedido["id"])["status"] == "EM_PREPARO"


def test_webhook_exige_assinatura_valida(api):
    pedido = api.criar_pedido().json()
    transacao = api.pagar(pedido["id"], token="tok_sem_retorno").json()["transacaoExterna"]

    assert_erro(api.webhook(transacao, "APROVADO", assinatura=None), 401, "ASSINATURA_INVALIDA")
    assert_erro(api.webhook(transacao, "APROVADO", assinatura="0" * 64), 401, "ASSINATURA_INVALIDA")
    assert api.pedido(pedido["id"])["pagamento"]["status"] == "PENDENTE"

    assert_erro(api.webhook("MOCK-INEXISTENTE", "APROVADO"), 404, "PAGAMENTO_NAO_ENCONTRADO")


def test_webhook_com_corpo_invalido_retorna_422(api):
    import json

    from app.infrastructure.seguranca import assinar_payload

    corpo = json.dumps({"transacaoId": "X", "status": "TALVEZ"}).encode()
    assinatura = assinar_payload(api.settings.webhook_secret, corpo)
    r = api.client.post(
        "/pagamentos/webhook", content=corpo, headers={"X-Signature": assinatura, "Content-Type": "application/json"}
    )
    erro = assert_erro(r, 422, "VALIDACAO_FALHOU")
    assert erro["detalhes"][0]["campo"] == "status"


def test_estoque_esgotado_entre_o_pedido_e_o_pagamento_cancela_e_estorna(api):
    a = api.criar_pedido(itens=((ACARAJE, 2),)).json()
    b = api.criar_pedido(itens=((ACARAJE, 2),), como="cliente2@raizes.com").json()

    api.pagar(a["id"])
    api.pagar(b["id"], como="cliente2@raizes.com")

    assert api.pedido(a["id"])["status"] == "EM_PREPARO"
    final_b = api.pedido(b["id"])
    assert final_b["status"] == "CANCELADO"
    assert final_b["motivoCancelamento"] == "ESTOQUE_ESGOTADO_APOS_PAGAMENTO"
    assert final_b["pagamento"]["status"] == "ESTORNADO"
    assert api.saldo_estoque(ACARAJE) == 1

    auditoria = api.get("/auditorias?acao=PEDIDO_CANCELADO_SEM_ESTOQUE", "gerente@raizes.com").json()
    assert auditoria["total"] == 1


def test_pedido_pago_e_cancelado_estorna_tudo(api):
    pedido = api.criar_pedido(itens=((BAIAO, 3),)).json()
    antes = api.saldo_estoque(BAIAO)
    api.pagar(pedido["id"])
    assert api.saldo_estoque(BAIAO) == antes - 3
    assert api.get("/fidelidade", "cliente@raizes.com").json()["saldo"] == 116

    r = api.patch(f"/pedidos/{pedido['id']}/status", "cliente@raizes.com", json={"status": "CANCELADO"})
    assert_erro(r, 403, "CANCELAMENTO_SOMENTE_EQUIPE")

    r = api.patch(
        f"/pedidos/{pedido['id']}/status",
        "atendente@raizes.com",
        json={"status": "CANCELADO", "motivo": "Cliente desistiu"},
    )
    assert r.status_code == 200
    cancelado = r.json()
    assert cancelado["status"] == "CANCELADO" and cancelado["motivoCancelamento"] == "Cliente desistiu"
    assert cancelado["pagamento"]["status"] == "ESTORNADO"
    assert api.saldo_estoque(BAIAO) == antes
    assert api.get("/fidelidade", "cliente@raizes.com").json()["saldo"] == 0
    assert api.container.gateway.estornos


def test_cliente_cancela_pedido_ainda_nao_pago(api):
    pedido = api.criar_pedido().json()
    r = api.patch(f"/pedidos/{pedido['id']}/status", "cliente@raizes.com", json={"status": "CANCELADO"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELADO"
    assert_erro(api.pagar(pedido["id"]), 409, "PEDIDO_NAO_PAGAVEL")


def test_callback_aprovado_de_pedido_cancelado_e_estornado(api):
    pedido = api.criar_pedido(itens=((BAIAO, 1),)).json()
    antes = api.saldo_estoque(BAIAO)
    transacao = api.pagar(pedido["id"], token="tok_sem_retorno").json()["transacaoExterna"]
    api.patch(f"/pedidos/{pedido['id']}/status", "cliente@raizes.com", json={"status": "CANCELADO"})

    r = api.webhook(transacao, "APROVADO")
    assert r.json()["statusPagamento"] == "ESTORNADO" and r.json()["statusPedido"] == "CANCELADO"
    assert api.saldo_estoque(BAIAO) == antes


def test_ciclo_completo_cozinha_e_atendente(api):
    pedido = api.criar_pedido().json()
    caminho = f"/pedidos/{pedido['id']}/status"

    assert_erro(api.patch(caminho, "cozinha@raizes.com", json={"status": "PRONTO"}), 409, "TRANSICAO_STATUS_INVALIDA")

    api.pagar(pedido["id"])
    assert_erro(api.patch(caminho, "atendente@raizes.com", json={"status": "PRONTO"}), 403, "ACESSO_NEGADO")
    assert api.patch(caminho, "cozinha@raizes.com", json={"status": "PRONTO"}).json()["status"] == "PRONTO"
    assert_erro(api.patch(caminho, "cozinha@raizes.com", json={"status": "ENTREGUE"}), 403, "ACESSO_NEGADO")
    assert api.patch(caminho, "atendente@raizes.com", json={"status": "ENTREGUE"}).json()["status"] == "ENTREGUE"

    assert_erro(api.patch(caminho, "gerente@raizes.com", json={"status": "CANCELADO"}), 409, "TRANSICAO_STATUS_INVALIDA")
    assert_erro(api.patch(caminho, "gerente@raizes.com", json={"status": "EM_PREPARO"}), 422, "STATUS_NAO_PERMITIDO")


def test_pagamento_so_pelo_dono_ou_equipe_da_unidade(api):
    pedido = api.criar_pedido().json()
    assert_erro(api.pagar(pedido["id"], como="cliente2@raizes.com"), 403, "ACESSO_NEGADO")
    assert_erro(api.pagar(pedido["id"], como="cozinha@raizes.com"), 403, "ACESSO_NEGADO")
    assert_erro(api.pagar(999), 404, "PEDIDO_NAO_ENCONTRADO")
    assert api.pagar(pedido["id"], como="atendente@raizes.com").status_code == 201
    assert_erro(api.get("/pagamentos/999", "cliente@raizes.com"), 404, "PAGAMENTO_NAO_ENCONTRADO")
