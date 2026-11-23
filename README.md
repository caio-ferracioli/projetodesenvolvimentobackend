# API Raízes do Nordeste

API REST desenvolvida em Python com FastAPI para o Projeto Multidisciplinar (Trilha Back-end - UNINTER), baseada no estudo de caso da rede de lanchonetes Raízes do Nordeste.

O sistema cobre autenticação JWT com controle de perfis, cardápio e estoque por unidade, pedidos multicanal ('canalPedido'), simulação de pagamento externo (mock) com webhook, programa de fidelidade com consentimento (LGPD) e registro de auditoria.

- Repositório: https://github.com/caio-ferracioli/projetodesenvolvimentobackend
- Swagger (local): http://localhost:8000/docs (JSON em '/openapi.json')
- Coleção Postman: 'docs/postman/raizes-do-nordeste.postman_collection.json'
- DER e diagramas: 'docs/DER.md' e 'docs/diagramas.md'

## Tecnologias utilizadas

- Python 3.13 e FastAPI
- SQLite com SQLAlchemy 2 e Alembic (migrations)
- PyJWT (autenticação JWT) e bcrypt (hash de senhas)
- Pydantic (validação de entrada e saída)
- Pytest (testes automatizados)

## Pré-requisitos

- Python 3.13 ou superior instalado
- 'pip'

Não é preciso instalar banco de dados externo, pois o projeto usa SQLite local ('raizes.db') por padrão.

## Como rodar o projeto

1. Clone o repositório e entre na pasta:

        git clone https://github.com/caio-ferracioli/projetodesenvolvimentobackend.git
        cd projetodesenvolvimentobackend

2. Crie e ative o ambiente virtual:

        python -m venv .venv
        .venv\Scripts\activate

3. Instale as dependências:

        pip install -r requirements.txt

4. Configure as variáveis de ambiente copiando o arquivo de exemplo:

        copy .env.example .env

   Edite o '.env' e preencha os segredos obrigatórios (o servidor não inicia sem eles):
   - 'DATABASE_URL': caminho do banco (padrão 'sqlite:///./raizes.db')
   - 'JWT_SECRET': chave para assinar os tokens JWT (mínimo 32 caracteres)
   - 'WEBHOOK_SECRET': chave HMAC para validar o webhook de pagamento (mínimo 16 caracteres)
   - 'JWT_EXPIRE_MINUTES': tempo de expiração do token em minutos (padrão '60')
   - 'BCRYPT_ROUNDS': custo do hash de senha (padrão '12')
   - 'PAGAMENTO_MOCK_CALLBACK_AUTOMATICO': 'true' para o mock disparar a confirmação automaticamente
   - 'PAGAMENTO_MOCK_ATRASO_SEGUNDOS': atraso opcional do callback em segundos (padrão '0')

5. Crie as tabelas com as migrations e popule o banco com os dados iniciais:

        alembic upgrade head
        python -m app.infrastructure.db.seed

6. Inicie a API:

        uvicorn app.main:criar_app --factory --reload

A aplicação fica disponível em 'http://localhost:8000' e a documentação Swagger em 'http://localhost:8000/docs'.

## Usuários de teste (seed)

Todos os usuários criados pelo seed usam a senha 'Senha@123':

- 'admin@raizes.com' (ADMIN)
- 'gerente@raizes.com' (GERENTE)
- 'atendente@raizes.com' (ATENDENTE - unidade 1 Recife)
- 'cozinha@raizes.com' (COZINHA - unidade 1 Recife)
- 'cliente@raizes.com' (CLIENTE - com consentimento de fidelidade)
- 'cliente2@raizes.com' (CLIENTE - sem consentimento)

O seed também cria 3 unidades (1 Recife, 2 Salvador e 3 Fortaleza). Fortaleza não vende Moqueca Baiana e o Acarajé em Recife começa com 3 unidades em estoque para facilitar o teste de estoque insuficiente (erro 409).

Para testar rotas autenticadas no Swagger, faça login em 'POST /auth/login', copie o 'accessToken' e informe no botão **Authorize**.

## Como rodar os testes

### Testes automatizados (pytest)

    pytest

Os testes rodam em um banco SQLite em memória com seed próprio, sem alterar o arquivo 'raizes.db'. Ao todo são 62 testes cobrindo autenticação, permissões, validações, pedidos, estoque, pagamento mock, webhook, fidelidade, LGPD, auditoria e migrations.

### Coleção Postman

1. Com o banco limpo, rode 'alembic upgrade head', 'python -m app.infrastructure.db.seed' e suba a API.
2. Importe o arquivo 'docs/postman/raizes-do-nordeste.postman_collection.json' no Postman ou Insomnia.
3. Nas variáveis da coleção, coloque em 'webhookSecret' o mesmo valor configurado no seu '.env'.
4. Execute as pastas na ordem: 'Auth', 'Produtos', 'Estoque', 'Pedidos', 'Pagamento', 'Fidelidade', 'Auditoria' e 'Erros'.

Também é possível executar o mesmo roteiro da coleção pelo terminal com a API rodando:

    python scripts\colecao.py executar --url http://localhost:8000

## Estrutura de pastas

    app/
      domain/          # Entidades, enums, exceções, políticas de acesso e interfaces
      application/     # Casos de uso / regras de negócio
      infrastructure/  # Banco de dados (SQLAlchemy, repositórios, seed), segurança e gateway mock
      api/             # Rotas FastAPI, schemas Pydantic, dependências e tratamento de erros
      config.py        # Leitura das variáveis de ambiente
      container.py     # Injeção de dependências
      main.py          # Inicialização do FastAPI
    alembic/           # Scripts de migração do banco
    docs/              # DER, diagramas Mermaid e coleção Postman
    scripts/           # Script auxiliar da coleção de testes
    tests/             # Suíte de testes com pytest

## Principais endpoints

- '/auth': 'POST /registro', 'POST /login', 'GET /me', 'POST /refresh'
- '/usuarios': 'GET', 'POST', 'DELETE /{id}' (anonimização LGPD)
- '/unidades': 'GET', 'GET /{id}', 'POST', 'PUT', 'GET /{id}/cardapio' (público)
- '/produtos': 'GET', 'GET /{id}', 'POST', 'PUT', 'DELETE /{id}'
- '/estoque': 'GET', 'GET /movimentacoes', 'POST /movimentacoes', 'PATCH /{id}/disponibilidade'
- '/pedidos': 'GET' (com filtros 'canalPedido', 'status', 'page', 'limit'), 'POST', 'GET /{id}', 'PATCH /{id}/status'
- '/pagamentos': 'POST', 'GET /{id}', 'POST /webhook'
- '/fidelidade': 'GET', 'PUT /consentimento', 'POST /resgates'
- '/auditorias': 'GET' (restrito a GERENTE e ADMIN)
- '/saude': 'GET' (health check)

Todas as respostas de erro seguem o mesmo padrão JSON:

    {
      "status": 422,
      "codigo": "VALIDACAO_FALHOU",
      "mensagem": "Os dados enviados são inválidos.",
      "detalhes": [{ "campo": "canalPedido", "mensagem": "Campo obrigatório." }],
      "caminho": "/pedidos",
      "timestamp": "2026-11-11T12:00:00+00:00"
    }

### Tokens do pagamento mock

No campo 'tokenPagamento' de 'POST /pagamentos', é possível simular diferentes retornos:
- vazio ou qualquer outro valor: pagamento aprovado
- 'tok_recusado': pagamento recusado
- 'tok_timeout': simula gateway fora do ar (retorna 503 e mantém o pedido aberto)
- 'tok_sem_retorno': mantém 'PENDENTE' para confirmação manual via 'POST /pagamentos/webhook'
- pedidos acima de R$ 5.000,00: recusados por limite

## Segurança e LGPD

- Senhas salvas apenas com hash bcrypt e nunca expostas nas respostas ou logs.
- Controle de acesso por perfil (JWT) e por unidade/dono do pedido.
- Consentimento explícito e revogável para participar do programa de fidelidade.
- Endpoint 'DELETE /usuarios/{id}' para anonimizar dados pessoais preservando o histórico fiscal dos pedidos.
- Tabela 'auditorias' registrando ações sensíveis (pedidos, pagamentos, mudanças de status, estoque e usuários).
