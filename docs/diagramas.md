# Diagramas — Raízes do Nordeste

Todos em Mermaid (renderizam no GitHub). Para a entrega em imagem/PDF, abra em <https://mermaid.live>.

## 1. Casos de uso

```mermaid
flowchart LR
    Cliente([Cliente<br/>App / Web / Totem])
    Atendente([Atendente<br/>Balcão])
    Cozinha([Cozinha])
    Gerente([Gerente / Administrador])
    Gateway([Gateway de pagamento<br/>sistema externo])

    subgraph API["API Raízes do Nordeste"]
        UC1(Cadastrar-se / Login)
        UC2(Consultar cardápio da unidade)
        UC3(Criar pedido)
        UC4(Pagar pedido)
        UC5(Acompanhar / cancelar pedido)
        UC6(Marcar pedido PRONTO)
        UC7(Marcar pedido ENTREGUE)
        UC8(Registrar pedido no balcão)
        UC9(Gerir produtos e unidades)
        UC10(Movimentar estoque)
        UC11(Consentir e resgatar pontos)
        UC12(Consultar auditoria)
        UC13(Eliminar dados pessoais - LGPD)
        UC14(Confirmar pagamento - webhook)
    end

    Cliente --- UC1 & UC2 & UC3 & UC4 & UC5 & UC11 & UC13
    Atendente --- UC8 & UC4 & UC7 & UC5
    Cozinha --- UC6
    Gerente --- UC9 & UC10 & UC12 & UC5
    UC4 -. "cobrança" .-> Gateway
    Gateway --- UC14
```

## 2. Arquitetura em camadas

```mermaid
flowchart TB
    subgraph API["API  (app/api)"]
        R[Routers] --- S[Schemas Pydantic] --- D[Dependências: JWT e perfil] --- E[Erro padronizado]
    end
    subgraph APP["Application  (app/application)"]
        SV[Serviços / casos de uso<br/>Pedidos · Pagamentos · Estoque · Fidelidade · ...]
    end
    subgraph DOM["Domain  (app/domain)"]
        EN[Entidades e regras] --- EV[Enums e máquina de estados] --- PO[Portas: Protocols] --- PL[Políticas de acesso]
    end
    subgraph INF["Infrastructure  (app/infrastructure)"]
        ORM[SQLAlchemy + Repositórios + Unit of Work] --- GW[Gateway mock] --- SEG[bcrypt / JWT / HMAC]
    end
    DB[(SQLite)]

    API --> APP --> DOM
    INF -. "implementa as portas" .-> DOM
    API -. "composition root (app/container.py)" .-> INF
    ORM --> DB
```

Regra de dependência: **Domain não importa nada**; Application só conhece Domain; Infrastructure implementa as
portas definidas no Domain; a API chama a Application. Só o `container.py` conhece as implementações concretas.

## 3. Diagrama de classes (domínio)

```mermaid
classDiagram
    class Usuario {
        +int id
        +str nome
        +str email
        +str senha_hash
        +Perfil perfil
        +int unidade_id
        +bool consentimento_fidelidade
        +definir_consentimento(bool)
        +anonimizar()
    }
    class Unidade {
        +int id
        +str nome
        +str cidade
        +bool ativa
    }
    class Produto {
        +int id
        +str nome
        +Decimal preco
        +bool ativo
        +vendavel() bool
    }
    class Estoque {
        +int unidade_id
        +int produto_id
        +int quantidade
        +bool disponivel
        +pode_atender(int) bool
    }
    class MovimentacaoEstoque {
        +TipoMovimentacaoEstoque tipo
        +int variacao
        +int saldo_apos
    }
    class Pedido {
        +int id
        +CanalPedido canal_pedido
        +StatusPedido status
        +Decimal valor_total
        +str chave_idempotencia
        +recalcular_total()
        +transicionar(StatusPedido)
        +aceita_pagamento() bool
    }
    class ItemPedido {
        +int quantidade
        +Decimal preco_unitario
        +Decimal subtotal
    }
    class Pagamento {
        +MetodoPagamento metodo
        +Decimal valor
        +StatusPagamento status
        +str transacao_externa
    }
    class MovimentacaoFidelidade {
        +TipoMovimentacaoFidelidade tipo
        +int pontos
    }
    class Auditoria {
        +str acao
        +str entidade
        +dict detalhes
        +str ip
    }
    class GatewayPagamento {
        <<interface>>
        +iniciar_cobranca()
        +estornar()
    }
    class MockGatewayPagamento

    Unidade "1" --> "*" Estoque
    Produto "1" --> "*" Estoque
    Estoque "1" --> "*" MovimentacaoEstoque
    Unidade "1" --> "*" Pedido
    Usuario "0..1" --> "*" Pedido : cliente
    Pedido "1" *-- "1..*" ItemPedido
    Produto "1" --> "*" ItemPedido
    Pedido "1" --> "*" Pagamento : tentativas
    Usuario "1" --> "*" MovimentacaoFidelidade
    Usuario "0..1" --> "*" Auditoria : autor
    Unidade "0..1" --> "*" Usuario : equipe
    GatewayPagamento <|.. MockGatewayPagamento
```

## 4. Máquina de estados do pedido

```mermaid
stateDiagram-v2
    [*] --> AGUARDANDO_PAGAMENTO : POST /pedidos (valida estoque, não reserva)
    AGUARDANDO_PAGAMENTO --> EM_PREPARO : callback APROVADO (baixa o estoque)
    AGUARDANDO_PAGAMENTO --> PAGAMENTO_RECUSADO : callback RECUSADO
    PAGAMENTO_RECUSADO --> EM_PREPARO : nova tentativa aprovada
    AGUARDANDO_PAGAMENTO --> CANCELADO : cliente / equipe
    PAGAMENTO_RECUSADO --> CANCELADO : cliente / equipe
    AGUARDANDO_PAGAMENTO --> CANCELADO : aprovado, mas estoque esgotou (estorno automático)
    EM_PREPARO --> PRONTO : cozinha
    EM_PREPARO --> CANCELADO : equipe (estorna pagamento, estoque e pontos)
    PRONTO --> ENTREGUE : atendente
    ENTREGUE --> [*]
    CANCELADO --> [*]
```

## 5. Sequência do fluxo crítico: pedido → pagamento externo assíncrono → status

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant API as API (routers)
    participant PS as ServicoPedidos
    participant PG as ServicoPagamentos
    participant DB as Banco
    participant GW as Gateway (mock)

    C->>API: POST /pedidos (canalPedido, itens) + JWT
    API->>PS: criar()
    PS->>DB: valida produtos e estoque (SEM reservar)
    PS->>DB: grava pedido AGUARDANDO_PAGAMENTO + auditoria
    API-->>C: 201 Created

    C->>API: POST /pagamentos (pedidoId, metodo, token)
    API->>PG: iniciar()
    PG->>DB: [tx 1] valida pedido e grava pagamento PENDENTE
    PG->>GW: iniciar_cobranca() (fora de transação)
    alt gateway fora do ar
        GW--xPG: timeout
        PG->>DB: pagamento FALHA (pedido segue AGUARDANDO_PAGAMENTO)
        API-->>C: 503 GATEWAY_INDISPONIVEL
    else cobrança aceita
        GW-->>PG: transacao_id
        PG->>DB: [tx 2] guarda transacao_id + auditoria
        API-->>C: 201 pagamento PENDENTE
    end

    Note over GW,API: depois que a resposta HTTP saiu...
    GW->>API: POST /pagamentos/webhook (X-Signature HMAC)
    API->>PG: processar_callback() — idempotente
    alt APROVADO
        PG->>DB: baixa estoque (UPDATE condicional atômico)
        alt estoque acabou nesse meio tempo
            PG->>DB: rollback, pagamento ESTORNADO, pedido CANCELADO
        else baixou tudo
            PG->>DB: pagamento APROVADO, pedido EM_PREPARO, pontos, auditoria
        end
    else RECUSADO
        PG->>DB: pagamento RECUSADO, pedido PAGAMENTO_RECUSADO
    end
    C->>API: GET /pedidos/{id}
    API-->>C: 200 status atualizado
```
