import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs" / "postman"
NOME_COLECAO = "Raízes do Nordeste — API Python"
BASE_URL_PADRAO = "http://localhost:8000"

JSON_H = {"Content-Type": "application/json"}


def R(nome, metodo, caminho, *, auth=None, corpo=None, headers=None, status, checks=(), salvar=None,
      espera=0.0, pre=None, webhook=None, descricao=""):
    return dict(nome=nome, metodo=metodo, caminho=caminho, auth=auth, corpo=corpo,
                headers=headers or {}, status=status, checks=list(checks), salvar=salvar or {},
                espera=espera, pre=pre or {}, webhook=webhook, descricao=descricao)


def pedido(canal="APP", itens='[{"produtoId": 1, "quantidade": 2}]', unidade=1, extra=""):
    return f'{{"unidadeId": {unidade}, "canalPedido": "{canal}", "itens": {itens}{extra}}}'


ERRO = lambda codigo: [("codigo", "eq", codigo), ("caminho", "existe", None), ("timestamp", "existe", None)]

ESPEC = [
    ("Auth", [
        R("T01 Login válido (cliente) → 200 + token", "POST", "/auth/login", corpo='{"email": "cliente@raizes.com", "senha": "Senha@123"}',
          headers=JSON_H, status=200, checks=[("accessToken", "existe", None), ("tokenType", "eq", "Bearer")],
          salvar={"tokenCliente": "accessToken"}),
        R("Login (cliente 2, sem consentimento)", "POST", "/auth/login", corpo='{"email": "cliente2@raizes.com", "senha": "Senha@123"}',
          headers=JSON_H, status=200, salvar={"tokenCliente2": "accessToken"}),
        R("Login (atendente)", "POST", "/auth/login", corpo='{"email": "atendente@raizes.com", "senha": "Senha@123"}',
          headers=JSON_H, status=200, salvar={"tokenAtendente": "accessToken"}),
        R("Login (cozinha)", "POST", "/auth/login", corpo='{"email": "cozinha@raizes.com", "senha": "Senha@123"}',
          headers=JSON_H, status=200, salvar={"tokenCozinha": "accessToken"}),
        R("Login (gerente)", "POST", "/auth/login", corpo='{"email": "gerente@raizes.com", "senha": "Senha@123"}',
          headers=JSON_H, status=200, salvar={"tokenGerente": "accessToken"}),
        R("Login (admin)", "POST", "/auth/login", corpo='{"email": "admin@raizes.com", "senha": "Senha@123"}',
          headers=JSON_H, status=200, salvar={"tokenAdmin": "accessToken"}),
        R("Registro de novo cliente → 201", "POST", "/auth/registro",
          corpo='{"nome": "Cliente Teste", "email": "teste{{$timestamp}}@exemplo.com", "senha": "Senha@123", "consentimentoFidelidade": true}',
          headers=JSON_H, status=201, checks=[("perfil", "eq", "CLIENTE"), ("consentimentoFidelidade", "eq", True)]),
        R("Quem sou eu (token do cliente)", "GET", "/auth/me", auth="tokenCliente", status=200,
          checks=[("perfil", "eq", "CLIENTE"), ("email", "eq", "cliente@raizes.com")], salvar={"clienteId": "id"}),
    ]),
    ("Produtos", [
        R("Cardápio da unidade Recife (público, sem token)", "GET", "/unidades/1/cardapio", status=200,
          checks=[("itens[0].nome", "existe", None)]),
        R("Listar produtos (paginado)", "GET", "/produtos?page=1&limit=5", auth="tokenCliente", status=200,
          checks=[("page", "eq", 1), ("limit", "eq", 5), ("total", "gt", 0)]),
        R("Detalhar produto 1", "GET", "/produtos/1", auth="tokenCliente", status=200, checks=[("id", "eq", 1)]),
        R("Gerente cadastra produto → 201", "POST", "/produtos", auth="tokenGerente", headers=JSON_H,
          corpo='{"nome": "Bolo de Rolo {{$timestamp}}", "descricao": "Sobremesa", "categoria": "Sobremesas", "preco": 12.5}',
          status=201, checks=[("preco", "eq", 12.5)], salvar={"produtoNovoId": "id"}),
        R("Gerente atualiza o preço do produto", "PUT", "/produtos/{{produtoNovoId}}", auth="tokenGerente", headers=JSON_H,
          corpo='{"nome": "Bolo de Rolo", "categoria": "Sobremesas", "preco": 13.9, "ativo": true}',
          status=200, checks=[("preco", "eq", 13.9)]),
        R("Gerente remove o produto (exclusão lógica) → 204", "DELETE", "/produtos/{{produtoNovoId}}", auth="tokenGerente", status=204),
    ]),
    ("Estoque", [
        R("Saldo do Baião de Dois em Recife", "GET", "/estoque?unidadeId=1&produtoId=1", auth="tokenGerente", status=200,
          checks=[("items[0].quantidade", "gt", 0)], salvar={"estoqueBaiaoId": "items[0].id"}),
        R("Entrada de estoque (+10) → 201", "POST", "/estoque/movimentacoes", auth="tokenGerente", headers=JSON_H,
          corpo='{"unidadeId": 1, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 10, "motivo": "Reposição"}',
          status=201, checks=[("variacao", "eq", 10), ("tipo", "eq", "ENTRADA")]),
        R("Histórico de movimentações", "GET", "/estoque/movimentacoes?unidadeId=1&produtoId=1", auth="tokenGerente", status=200,
          checks=[("total", "gt", 0)]),
    ]),
    ("Pedidos", [
        R("T06 Criar pedido válido (APP) → 201", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H, corpo=pedido("APP"),
          status=201, checks=[("status", "eq", "AGUARDANDO_PAGAMENTO"), ("canalPedido", "eq", "APP"), ("valorTotal", "eq", 77.8)],
          salvar={"pedidoId": "id"}),
        R("Criar pedido pelo TOTEM → 201", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H,
          corpo=pedido("TOTEM", '[{"produtoId": 4, "quantidade": 1}]'), status=201, checks=[("canalPedido", "eq", "TOTEM")]),
        R("Filtrar pedidos por canalPedido=TOTEM", "GET", "/pedidos?canalPedido=TOTEM&page=1&limit=10", auth="tokenGerente",
          status=200, checks=[("total", "gt", 0), ("items", "todos_iguais", ("canalPedido", "TOTEM"))]),
        R("Detalhar o pedido", "GET", "/pedidos/{{pedidoId}}", auth="tokenCliente", status=200, checks=[("id", "existe", None)]),
        R("Idempotência — 1ª chamada com Idempotency-Key → 201", "POST", "/pedidos", auth="tokenCliente",
          headers={**JSON_H, "Idempotency-Key": "{{chaveIdem}}"}, pre={"chaveIdem": "idem-{{$timestamp}}"},
          corpo=pedido("WEB", '[{"produtoId": 6, "quantidade": 1}]'), status=201, salvar={"pedidoIdemId": "id"}),
        R("Idempotência — 2ª chamada (mesma chave) → 200, mesmo pedido", "POST", "/pedidos", auth="tokenCliente",
          headers={**JSON_H, "Idempotency-Key": "{{chaveIdem}}"},
          corpo=pedido("WEB", '[{"produtoId": 6, "quantidade": 1}]'), status=200),
        R("Balcão: atendente registra pedido para o cliente → 201", "POST", "/pedidos", auth="tokenAtendente", headers=JSON_H,
          corpo=pedido("BALCAO", '[{"produtoId": 7, "quantidade": 2}]', extra=', "clienteId": {{clienteId}}'),
          status=201, checks=[("canalPedido", "eq", "BALCAO")]),
    ]),
    ("Pagamento", [
        R("T09 Pagar pedido (mock aprovado) → 201 PENDENTE", "POST", "/pagamentos", auth="tokenCliente", headers=JSON_H,
          corpo='{"pedidoId": {{pedidoId}}, "metodo": "PIX"}', status=201,
          checks=[("status", "eq", "PENDENTE"), ("transacaoExterna", "existe", None)], salvar={"pagamentoId": "id"},
          descricao="A resposta é imediata e PENDENTE; o gateway confirma por callback logo em seguida."),
        R("T09 Pedido virou EM_PREPARO e o pagamento APROVADO", "GET", "/pedidos/{{pedidoId}}", auth="tokenCliente", espera=0.5,
          status=200, checks=[("status", "eq", "EM_PREPARO"), ("pagamento.status", "eq", "APROVADO")]),
        R("Consultar o pagamento", "GET", "/pagamentos/{{pagamentoId}}", auth="tokenCliente", status=200,
          checks=[("status", "eq", "APROVADO")]),
        R("Cozinha marca PRONTO", "PATCH", "/pedidos/{{pedidoId}}/status", auth="tokenCozinha", headers=JSON_H,
          corpo='{"status": "PRONTO"}', status=200, checks=[("status", "eq", "PRONTO")]),
        R("Atendente marca ENTREGUE", "PATCH", "/pedidos/{{pedidoId}}/status", auth="tokenAtendente", headers=JSON_H,
          corpo='{"status": "ENTREGUE"}', status=200, checks=[("status", "eq", "ENTREGUE")]),

        R("T10 Criar pedido para o pagamento recusado", "POST", "/pedidos", auth="tokenCliente2", headers=JSON_H,
          corpo=pedido("APP", '[{"produtoId": 2, "quantidade": 1}]'), status=201, salvar={"pedidoRecusadoId": "id"}),
        R("T10 Pagar com cartão recusado (tok_recusado)", "POST", "/pagamentos", auth="tokenCliente2", headers=JSON_H,
          corpo='{"pedidoId": {{pedidoRecusadoId}}, "metodo": "CARTAO_CREDITO", "tokenPagamento": "tok_recusado"}', status=201,
          checks=[("status", "eq", "PENDENTE")]),
        R("T10 Pedido ficou PAGAMENTO_RECUSADO (com mensagem)", "GET", "/pedidos/{{pedidoRecusadoId}}", auth="tokenCliente2",
          espera=0.5, status=200,
          checks=[("status", "eq", "PAGAMENTO_RECUSADO"), ("pagamento.status", "eq", "RECUSADO"), ("pagamento.mensagem", "existe", None)]),
        R("Nova tentativa do mesmo pedido (aprovada) → 201", "POST", "/pagamentos", auth="tokenCliente2", headers=JSON_H,
          corpo='{"pedidoId": {{pedidoRecusadoId}}, "metodo": "PIX"}', status=201),

        R("Criar pedido para os testes de falha do gateway", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H,
          corpo=pedido("APP", '[{"produtoId": 4, "quantidade": 1}]'), status=201, salvar={"pedidoTimeoutId": "id"}),
        R("Gateway fora do ar (tok_timeout) → 503 e pedido mantido", "POST", "/pagamentos", auth="tokenCliente", headers=JSON_H,
          corpo='{"pedidoId": {{pedidoTimeoutId}}, "metodo": "PIX", "tokenPagamento": "tok_timeout"}', status=503,
          checks=ERRO("GATEWAY_INDISPONIVEL")),
        R("Pedido segue AGUARDANDO_PAGAMENTO (tolerância a falha)", "GET", "/pedidos/{{pedidoTimeoutId}}", auth="tokenCliente",
          status=200, checks=[("status", "eq", "AGUARDANDO_PAGAMENTO"), ("pagamento.status", "eq", "FALHA")]),

        R("Pagamento sem retorno do gateway (tok_sem_retorno) → PENDENTE", "POST", "/pagamentos", auth="tokenCliente",
          headers=JSON_H, corpo='{"pedidoId": {{pedidoTimeoutId}}, "metodo": "PIX", "tokenPagamento": "tok_sem_retorno"}',
          status=201, checks=[("status", "eq", "PENDENTE")], salvar={"transacaoId": "transacaoExterna"}),
        R("Segunda tentativa enquanto há pagamento pendente → 409", "POST", "/pagamentos", auth="tokenCliente", headers=JSON_H,
          corpo='{"pedidoId": {{pedidoTimeoutId}}, "metodo": "PIX"}', status=409, checks=ERRO("PAGAMENTO_EM_ANDAMENTO")),
        R("Webhook do gateway (assinado com HMAC-SHA256) → 200", "POST", "/pagamentos/webhook", status=200,
          webhook=("transacaoId", "APROVADO"),
          checks=[("statusPagamento", "eq", "APROVADO"), ("statusPedido", "eq", "EM_PREPARO"), ("processado", "eq", True)]),
        R("Webhook repetido é idempotente → 200 processado=false", "POST", "/pagamentos/webhook", status=200,
          webhook=("transacaoId", "APROVADO"), checks=[("processado", "eq", False)]),

        R("Atendente cancela o pedido pago (estorna pagamento, estoque e pontos)", "PATCH", "/pedidos/{{pedidoTimeoutId}}/status",
          auth="tokenAtendente", headers=JSON_H, corpo='{"status": "CANCELADO", "motivo": "Cliente desistiu"}', status=200,
          checks=[("status", "eq", "CANCELADO"), ("pagamento.status", "eq", "ESTORNADO")]),
    ]),
    ("Fidelidade", [
        R("Saldo, consentimento e extrato", "GET", "/fidelidade", auth="tokenCliente", status=200,
          checks=[("consentimento", "eq", True), ("saldo", "gt", 0)]),
        R("Cliente sem consentimento não resgata → 422", "POST", "/fidelidade/resgates", auth="tokenCliente2", headers=JSON_H,
          corpo='{"pontos": 1}', status=422, checks=ERRO("CONSENTIMENTO_NECESSARIO")),
        R("Resgate acima do saldo → 409", "POST", "/fidelidade/resgates", auth="tokenCliente", headers=JSON_H,
          corpo='{"pontos": 999999}', status=409, checks=ERRO("SALDO_INSUFICIENTE")),
        R("Resgatar 5 pontos → 201", "POST", "/fidelidade/resgates", auth="tokenCliente", headers=JSON_H,
          corpo='{"pontos": 5}', status=201, checks=[("pontos", "eq", -5)]),
    ]),
    ("Auditoria", [
        R("T11 Ação sensível gerou registro (PEDIDO_CRIADO)", "GET", "/auditorias?acao=PEDIDO_CRIADO&limit=5", auth="tokenGerente",
          status=200, checks=[("total", "gt", 0), ("items[0].acao", "eq", "PEDIDO_CRIADO"), ("items[0].usuarioId", "existe", None)]),
        R("Auditoria de pagamentos aprovados", "GET", "/auditorias?acao=PAGAMENTO_APROVADO&limit=5", auth="tokenGerente",
          status=200, checks=[("total", "gt", 0)]),
        R("Cliente não acessa a auditoria → 403", "GET", "/auditorias", auth="tokenCliente", status=403,
          checks=ERRO("PERFIL_SEM_PERMISSAO")),
    ]),
    ("Erros", [
        R("T02 Sem token → 401", "GET", "/pedidos", status=401, checks=ERRO("TOKEN_AUSENTE")),
        R("Credenciais inválidas → 401", "POST", "/auth/login", headers=JSON_H, corpo='{"email": "cliente@raizes.com", "senha": "errada123"}',
          status=401, checks=ERRO("CREDENCIAIS_INVALIDAS")),
        R("Token inválido → 401", "GET", "/pedidos", headers={"Authorization": "Bearer token.invalido.aqui"}, status=401,
          checks=ERRO("TOKEN_INVALIDO")),
        R("T03 Cliente tenta cadastrar produto → 403", "POST", "/produtos", auth="tokenCliente", headers=JSON_H,
          corpo='{"nome": "Prato", "categoria": "Pratos", "preco": 10}', status=403, checks=ERRO("PERFIL_SEM_PERMISSAO")),
        R("T04 Pedido sem canalPedido → 422", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H,
          corpo='{"unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 1}]}', status=422,
          checks=ERRO("VALIDACAO_FALHOU") + [("detalhes[0].campo", "eq", "canalPedido")]),
        R("T04 canalPedido inválido → 422", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H,
          corpo=pedido("DRONE"), status=422, checks=ERRO("VALIDACAO_FALHOU")),
        R("T05 Quantidade negativa → 422", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H,
          corpo=pedido("APP", '[{"produtoId": 1, "quantidade": -2}]'), status=422,
          checks=ERRO("VALIDACAO_FALHOU") + [("detalhes[0].campo", "eq", "itens.0.quantidade")]),
        R("T05 E-mail inválido → 422", "POST", "/auth/registro", headers=JSON_H,
          corpo='{"nome": "Ana", "email": "isto-nao-e-email", "senha": "Senha@123"}', status=422,
          checks=ERRO("VALIDACAO_FALHOU") + [("detalhes[0].campo", "eq", "email")]),
        R("T07 Produto inexistente → 404", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H,
          corpo=pedido("APP", '[{"produtoId": 9999, "quantidade": 1}]'), status=404, checks=ERRO("PRODUTO_NAO_ENCONTRADO")),
        R("T07 Unidade inexistente → 404", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H,
          corpo=pedido("APP", unidade=999), status=404, checks=ERRO("UNIDADE_NAO_ENCONTRADA")),
        R("T08 Estoque insuficiente (Acarajé, só 3 em Recife) → 409", "POST", "/pedidos", auth="tokenCliente", headers=JSON_H,
          corpo=pedido("APP", '[{"produtoId": 5, "quantidade": 4}]'), status=409,
          checks=ERRO("ESTOQUE_INSUFICIENTE") + [("detalhes[0].disponivel", "eq", 3)]),
        R("Pedido de outro cliente → 403", "GET", "/pedidos/{{pedidoId}}", auth="tokenCliente2", status=403, checks=ERRO("ACESSO_NEGADO")),
        R("Transição de status inválida → 409", "PATCH", "/pedidos/{{pedidoId}}/status", auth="tokenGerente", headers=JSON_H,
          corpo='{"status": "CANCELADO"}', status=409, checks=ERRO("TRANSICAO_STATUS_INVALIDA")),
        R("Webhook com assinatura inválida → 401", "POST", "/pagamentos/webhook", headers={**JSON_H, "X-Signature": "0000"},
          corpo='{"transacaoId": "X", "status": "APROVADO"}', status=401, checks=ERRO("ASSINATURA_INVALIDA")),
        R("Rota inexistente usa o mesmo padrão de erro → 404", "GET", "/nao-existe", status=404, checks=ERRO("RECURSO_NAO_ENCONTRADO")),
    ]),
]


def _js(caminho: str) -> str:
    return "json." + caminho if not caminho.startswith("[") else "json" + caminho


def _script_teste(req: dict) -> list[str]:
    linhas = [f'pm.test("Status {req["status"]}", function () {{ pm.response.to.have.status({req["status"]}); }});']
    corpo_json = bool(req["checks"] or req["salvar"])
    if corpo_json:
        linhas.append("const json = pm.response.json();")
    for caminho, op, valor in req["checks"]:
        expr = _js(caminho)
        if op == "eq":
            linhas.append(f'pm.test("{caminho} = {json.dumps(valor, ensure_ascii=False)}", function () {{ pm.expect({expr}).to.eql({json.dumps(valor)}); }});')
        elif op == "gt":
            linhas.append(f'pm.test("{caminho} > {valor}", function () {{ pm.expect({expr}).to.be.above({valor}); }});')
        elif op == "existe":
            linhas.append(f'pm.test("{caminho} presente", function () {{ pm.expect({expr}).to.not.be.undefined; }});')
        elif op == "todos_iguais":
            campo, esperado = valor
            linhas.append(
                f'pm.test("todos com {campo} = {esperado}", function () {{ pm.expect({expr}.every(function (i) {{ return i.{campo} === {json.dumps(esperado)}; }})).to.be.true; }});'
            )
    for variavel, caminho in req["salvar"].items():
        linhas.append(f'pm.collectionVariables.set("{variavel}", {_js(caminho)});')
    return linhas


def _script_pre(req: dict) -> list[str]:
    linhas = []
    for variavel, valor in req["pre"].items():
        expressao = json.dumps(valor.replace("{{$timestamp}}", "\x00")).replace("\\u0000", '" + Date.now() + "')
        linhas.append(f'pm.collectionVariables.set("{variavel}", {expressao});')
    if req["espera"]:
        linhas.append(f"setTimeout(function () {{}}, {int(req['espera'] * 1000)});")
    if req["webhook"]:
        var, status = req["webhook"]
        linhas += [
            f'var corpo = JSON.stringify({{ transacaoId: pm.collectionVariables.get("{var}"), status: "{status}" }});',
            "var assinatura = CryptoJS.HmacSHA256(corpo, pm.collectionVariables.get(\"webhookSecret\")).toString(CryptoJS.enc.Hex);",
            "pm.request.body.update({ mode: \"raw\", raw: corpo, options: { raw: { language: \"json\" } } });",
            'pm.request.headers.upsert({ key: "Content-Type", value: "application/json" });',
            'pm.request.headers.upsert({ key: "X-Signature", value: assinatura });',
        ]
    return linhas


def _item_postman(req: dict) -> dict:
    url = "{{baseUrl}}" + req["caminho"]
    caminho, _, consulta = req["caminho"].partition("?")
    item_req: dict = {
        "method": req["metodo"],
        "header": [{"key": k, "value": v} for k, v in req["headers"].items()],
        "url": {
            "raw": url,
            "host": ["{{baseUrl}}"],
            "path": [p for p in caminho.split("/") if p],
            **({"query": [{"key": p.split("=")[0], "value": p.split("=", 1)[1]} for p in consulta.split("&")]} if consulta else {}),
        },
        "description": req["descricao"],
    }
    if req["auth"]:
        item_req["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": "{{" + req["auth"] + "}}", "type": "string"}]}
    if req["corpo"]:
        item_req["body"] = {"mode": "raw", "raw": req["corpo"], "options": {"raw": {"language": "json"}}}
    elif req["webhook"]:
        item_req["body"] = {"mode": "raw", "raw": "{}", "options": {"raw": {"language": "json"}}}
    eventos = [{"listen": "test", "script": {"type": "text/javascript", "exec": _script_teste(req)}}]
    pre = _script_pre(req)
    if pre:
        eventos.insert(0, {"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre}})
    return {"name": req["nome"], "event": eventos, "request": item_req}


def gerar() -> None:
    colecao = {
        "info": {
            "name": NOME_COLECAO,
            "description": (
                "Rode as pastas NA ORDEM (Collection Runner), com o banco recém-populado "
                "(alembic upgrade head + seed). Variáveis da coleção: baseUrl e webhookSecret (copie do .env)."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [{"name": pasta, "item": [_item_postman(r) for r in reqs]} for pasta, reqs in ESPEC],
        "variable": [
            {"key": "baseUrl", "value": BASE_URL_PADRAO},
            {"key": "webhookSecret", "value": "COLE-AQUI-O-WEBHOOK_SECRET-DO-SEU-.env"},
        ],
    }
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / "raizes-do-nordeste.postman_collection.json"
    destino.write_text(json.dumps(colecao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(r) for _, r in ESPEC)
    print(f"Coleção gerada: {destino.relative_to(RAIZ)} ({len(ESPEC)} pastas, {total} requisições)")


def _extrair(dado, caminho: str):
    atual = dado
    for parte in re.findall(r"[^.\[\]]+", caminho):
        if isinstance(atual, list):
            atual = atual[int(parte)]
        else:
            atual = atual[parte]
    return atual


def _substituir(texto: str, variaveis: dict) -> str:
    texto = texto.replace("{{$timestamp}}", str(int(time.time())))
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(variaveis[m.group(1)]), texto)


def executar(url: str, segredo_webhook: str) -> int:
    import httpx

    variaveis: dict = {"baseUrl": url, "webhookSecret": segredo_webhook}
    falhas: list[str] = []
    total = 0
    with httpx.Client(timeout=30) as cliente:
        for pasta, reqs in ESPEC:
            print(f"\n== {pasta}")
            for req in reqs:
                total += 1
                for var, valor in req["pre"].items():
                    variaveis[var] = _substituir(valor, variaveis)
                if req["espera"]:
                    time.sleep(req["espera"])

                headers = {k: _substituir(v, variaveis) for k, v in req["headers"].items()}
                if req["auth"]:
                    headers["Authorization"] = f"Bearer {variaveis[req['auth']]}"
                conteudo = _substituir(req["corpo"], variaveis).encode() if req["corpo"] else None
                if req["webhook"]:
                    var, status = req["webhook"]
                    conteudo = json.dumps({"transacaoId": variaveis[var], "status": status}, separators=(",", ":")).encode()
                    headers["Content-Type"] = "application/json"
                    headers["X-Signature"] = hmac.new(segredo_webhook.encode(), conteudo, hashlib.sha256).hexdigest()

                r = cliente.request(req["metodo"], url + _substituir(req["caminho"], variaveis), headers=headers, content=conteudo)
                problemas = []
                if r.status_code != req["status"]:
                    problemas.append(f"status {r.status_code} (esperado {req['status']})")
                corpo = r.json() if r.content else None
                for caminho, op, valor in req["checks"]:
                    try:
                        real = _extrair(corpo, caminho)
                    except (KeyError, IndexError, TypeError):
                        problemas.append(f"{caminho} ausente")
                        continue
                    if op == "eq" and real != valor:
                        problemas.append(f"{caminho}={real!r} (esperado {valor!r})")
                    elif op == "gt" and not real > valor:
                        problemas.append(f"{caminho}={real!r} (esperado > {valor})")
                    elif op == "todos_iguais" and not all(i[valor[0]] == valor[1] for i in real):
                        problemas.append(f"nem todos {valor[0]} = {valor[1]}")
                if not problemas:
                    for var, caminho in req["salvar"].items():
                        variaveis[var] = _extrair(corpo, caminho)
                marca = "OK " if not problemas else "ERRO"
                print(f"  [{marca}] {req['nome']}" + ("" if not problemas else f"  -> {'; '.join(problemas)}  {r.text[:160]}"))
                if problemas:
                    falhas.append(req["nome"])
    print(f"\n{total - len(falhas)}/{total} requisições conforme o esperado.")
    return 1 if falhas else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("acao", choices=["gerar", "executar"])
    parser.add_argument("--url", default=BASE_URL_PADRAO)
    args = parser.parse_args()

    if args.acao == "gerar":
        gerar()
        return 0

    segredo = os.environ.get("WEBHOOK_SECRET")
    if not segredo:
        sys.path.insert(0, str(RAIZ))
        from app.config import obter_settings

        segredo = obter_settings().webhook_secret
    return executar(args.url.rstrip("/"), segredo)


if __name__ == "__main__":
    sys.exit(main())
