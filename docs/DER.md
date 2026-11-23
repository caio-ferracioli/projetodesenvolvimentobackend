# DER — Raízes do Nordeste

Idêntico ao banco criado pela migration `alembic/versions/0001_esquema_inicial.py`. O teste
`tests/test_migrations.py` compara o banco migrado com os modelos (`app/infrastructure/db/models.py`) e
falha se houver qualquer divergência. O diagrama é Mermaid: renderiza direto no GitHub; para a entrega em
imagem/PDF, abra em <https://mermaid.live> e exporte como PNG ou SVG.

```mermaid
erDiagram
    UNIDADES ||--o{ USUARIOS : "equipe (unidade_id, opcional)"
    UNIDADES ||--o{ ESTOQUES : "possui"
    PRODUTOS ||--o{ ESTOQUES : "vendido_em"
    ESTOQUES ||--o{ MOVIMENTACOES_ESTOQUE : "historico"
    UNIDADES ||--o{ PEDIDOS : "recebe"
    USUARIOS ||--o{ PEDIDOS : "cliente (cliente_id, opcional)"
    USUARIOS ||--o{ PEDIDOS : "criado_por_id"
    PEDIDOS ||--|{ ITENS_PEDIDO : "contem"
    PRODUTOS ||--o{ ITENS_PEDIDO : "referenciado"
    PEDIDOS ||--o{ PAGAMENTOS : "tentativas"
    PEDIDOS ||--o{ MOVIMENTACOES_ESTOQUE : "origem (opcional)"
    USUARIOS ||--o{ MOVIMENTACOES_ESTOQUE : "executor (opcional)"
    USUARIOS ||--o{ MOVIMENTACOES_FIDELIDADE : "pontos"
    PEDIDOS ||--o{ MOVIMENTACOES_FIDELIDADE : "origem (opcional)"
    USUARIOS ||--o{ AUDITORIAS : "autor (opcional)"

    UNIDADES {
        int id PK
        string nome
        string cidade
        string endereco "nullable"
        bool ativa
        datetime criado_em
        datetime atualizado_em
    }
    USUARIOS {
        int id PK
        string nome
        string email UK
        string senha_hash "bcrypt"
        string perfil "CLIENTE|ATENDENTE|COZINHA|GERENTE|ADMIN"
        string telefone "nullable"
        int unidade_id FK "nullable"
        bool consentimento_fidelidade
        datetime consentimento_em "nullable"
        datetime anonimizado_em "nullable"
        datetime criado_em
        datetime atualizado_em
    }
    PRODUTOS {
        int id PK
        string nome
        text descricao "nullable"
        string categoria
        decimal preco "10,2 e >= 0"
        bool ativo
        datetime removido_em "exclusao logica"
        datetime criado_em
        datetime atualizado_em
    }
    ESTOQUES {
        int id PK
        int unidade_id FK
        int produto_id FK
        int quantidade ">= 0"
        bool disponivel
    }
    MOVIMENTACOES_ESTOQUE {
        int id PK
        int estoque_id FK
        string tipo "ENTRADA|SAIDA|AJUSTE|BAIXA_PEDIDO|ESTORNO_PEDIDO"
        int variacao "com sinal"
        int saldo_apos
        string motivo "nullable"
        int pedido_id FK "nullable"
        int usuario_id FK "nullable"
        datetime criado_em
    }
    PEDIDOS {
        int id PK
        int cliente_id FK "nullable (balcao)"
        int criado_por_id FK "nullable"
        int unidade_id FK
        string canal_pedido "APP|TOTEM|BALCAO|PICKUP|WEB"
        string status "AGUARDANDO_PAGAMENTO|PAGAMENTO_RECUSADO|EM_PREPARO|PRONTO|ENTREGUE|CANCELADO"
        decimal valor_total "10,2"
        string observacao "nullable"
        string motivo_cancelamento "nullable"
        string chave_idempotencia "nullable"
        datetime criado_em
        datetime atualizado_em
    }
    ITENS_PEDIDO {
        int id PK
        int pedido_id FK
        int produto_id FK
        string nome_produto "congelado"
        int quantidade "> 0"
        decimal preco_unitario "congelado"
        decimal subtotal
    }
    PAGAMENTOS {
        int id PK
        int pedido_id FK
        string metodo "PIX|CARTAO_CREDITO|CARTAO_DEBITO"
        decimal valor
        string status "PENDENTE|APROVADO|RECUSADO|FALHA|ESTORNADO"
        string transacao_externa UK "nullable"
        string mensagem "nullable"
        datetime criado_em
        datetime atualizado_em
    }
    MOVIMENTACOES_FIDELIDADE {
        int id PK
        int usuario_id FK
        int pedido_id FK "nullable"
        string tipo "ACUMULO|RESGATE|ESTORNO"
        int pontos "com sinal"
        string descricao "nullable"
        datetime criado_em
    }
    AUDITORIAS {
        int id PK
        int usuario_id FK "nullable"
        string acao
        string entidade "nullable"
        int entidade_id "nullable"
        json detalhes
        string ip "nullable"
        datetime criado_em
    }
```

## Restrições relevantes (garantidas pelo banco, não só pela aplicação)

| Tabela | Restrição | Para quê |
|---|---|---|
| `usuarios` | `email` único; índice em `perfil` | um cadastro por e-mail |
| `estoques` | **único (`unidade_id`, `produto_id`)**; `CHECK quantidade >= 0` | cardápio por unidade; estoque nunca fica negativo |
| `pedidos` | **único (`criado_por_id`, `chave_idempotencia`)**; índices em `status`, `canal_pedido`, (`unidade_id`,`status`) | idempotência; listagens rápidas no pico |
| `itens_pedido` | `CHECK quantidade > 0`; preço e nome **copiados** do produto | histórico não muda se o preço mudar |
| `pagamentos` | **índice único parcial** (`pedido_id`) `WHERE status = 'PENDENTE'`; `transacao_externa` único | no máximo UM pagamento aguardando o gateway por pedido, mesmo com requisições simultâneas; o callback localiza a tentativa pela transação |
| `movimentacoes_fidelidade` | **único (`pedido_id`, `tipo`)** | no máximo um ACÚMULO e um ESTORNO por pedido |
| `produtos` | `CHECK preco >= 0`; exclusão lógica (`removido_em`) | pedidos antigos continuam resolvendo o produto |
| FKs de auditoria/movimentação/cliente | `ON DELETE SET NULL` | o histórico sobrevive à remoção do usuário |

O saldo de fidelidade é `SUM(pontos)` de `movimentacoes_fidelidade` do usuário (não existe coluna de saldo,
então ele nunca diverge do extrato).

## Como o estoque é protegido (decisão de projeto)

A baixa **não** é feita lendo o saldo e gravando o novo. É um único `UPDATE` condicional:

```sql
UPDATE estoques SET quantidade = quantidade - :q WHERE id = :id AND quantidade - :q >= 0;
-- linhas afetadas = 0  ->  estoque insuficiente (nada foi alterado)
```

Duas vendas simultâneas do último item não passam as duas: o banco serializa o `UPDATE` e a segunda afeta 0 linhas.
