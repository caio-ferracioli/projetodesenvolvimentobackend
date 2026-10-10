from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('produtos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.Column('categoria', sa.String(length=60), nullable=False),
    sa.Column('preco', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('removido_em', sa.DateTime(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), nullable=False),
    sa.CheckConstraint('preco >= 0', name=op.f('ck_produtos_preco_nao_negativo')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_produtos'))
    )
    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_produtos_categoria'), ['categoria'], unique=False)

    op.create_table('unidades',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('cidade', sa.String(length=80), nullable=False),
    sa.Column('endereco', sa.String(length=200), nullable=True),
    sa.Column('ativa', sa.Boolean(), nullable=False),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_unidades'))
    )
    op.create_table('estoques',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('unidade_id', sa.Integer(), nullable=False),
    sa.Column('produto_id', sa.Integer(), nullable=False),
    sa.Column('quantidade', sa.Integer(), nullable=False),
    sa.Column('disponivel', sa.Boolean(), nullable=False),
    sa.CheckConstraint('quantidade >= 0', name=op.f('ck_estoques_quantidade_nao_negativa')),
    sa.ForeignKeyConstraint(['produto_id'], ['produtos.id'], name=op.f('fk_estoques_produto_id_produtos')),
    sa.ForeignKeyConstraint(['unidade_id'], ['unidades.id'], name=op.f('fk_estoques_unidade_id_unidades')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_estoques')),
    sa.UniqueConstraint('unidade_id', 'produto_id', name='uq_estoques_unidade_produto')
    )
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=160), nullable=False),
    sa.Column('senha_hash', sa.String(length=255), nullable=False),
    sa.Column('perfil', sa.Enum('CLIENTE', 'ATENDENTE', 'COZINHA', 'GERENTE', 'ADMIN', name='perfil', native_enum=False, length=20), nullable=False),
    sa.Column('telefone', sa.String(length=30), nullable=True),
    sa.Column('unidade_id', sa.Integer(), nullable=True),
    sa.Column('consentimento_fidelidade', sa.Boolean(), nullable=False),
    sa.Column('consentimento_em', sa.DateTime(), nullable=True),
    sa.Column('anonimizado_em', sa.DateTime(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['unidade_id'], ['unidades.id'], name=op.f('fk_usuarios_unidade_id_unidades'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usuarios')),
    sa.UniqueConstraint('email', name=op.f('uq_usuarios_email'))
    )
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuarios_perfil'), ['perfil'], unique=False)

    op.create_table('auditorias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('acao', sa.String(length=60), nullable=False),
    sa.Column('entidade', sa.String(length=60), nullable=True),
    sa.Column('entidade_id', sa.Integer(), nullable=True),
    sa.Column('detalhes', sa.JSON(), nullable=False),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_auditorias_usuario_id_usuarios'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auditorias'))
    )
    with op.batch_alter_table('auditorias', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_auditorias_acao'), ['acao'], unique=False)
        batch_op.create_index(batch_op.f('ix_auditorias_criado_em'), ['criado_em'], unique=False)
        batch_op.create_index(batch_op.f('ix_auditorias_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('pedidos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cliente_id', sa.Integer(), nullable=True),
    sa.Column('criado_por_id', sa.Integer(), nullable=True),
    sa.Column('unidade_id', sa.Integer(), nullable=False),
    sa.Column('canal_pedido', sa.Enum('APP', 'TOTEM', 'BALCAO', 'PICKUP', 'WEB', name='canalpedido', native_enum=False, length=20), nullable=False),
    sa.Column('status', sa.Enum('AGUARDANDO_PAGAMENTO', 'PAGAMENTO_RECUSADO', 'EM_PREPARO', 'PRONTO', 'ENTREGUE', 'CANCELADO', name='statuspedido', native_enum=False, length=30), nullable=False),
    sa.Column('valor_total', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('observacao', sa.String(length=255), nullable=True),
    sa.Column('motivo_cancelamento', sa.String(length=255), nullable=True),
    sa.Column('chave_idempotencia', sa.String(length=80), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['cliente_id'], ['usuarios.id'], name=op.f('fk_pedidos_cliente_id_usuarios'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuarios.id'], name=op.f('fk_pedidos_criado_por_id_usuarios'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['unidade_id'], ['unidades.id'], name=op.f('fk_pedidos_unidade_id_unidades')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pedidos')),
    sa.UniqueConstraint('criado_por_id', 'chave_idempotencia', name='uq_pedidos_chave_idempotencia')
    )
    with op.batch_alter_table('pedidos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pedidos_canal_pedido'), ['canal_pedido'], unique=False)
        batch_op.create_index(batch_op.f('ix_pedidos_cliente_id'), ['cliente_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_pedidos_status'), ['status'], unique=False)
        batch_op.create_index('ix_pedidos_unidade_status', ['unidade_id', 'status'], unique=False)

    op.create_table('itens_pedido',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pedido_id', sa.Integer(), nullable=False),
    sa.Column('produto_id', sa.Integer(), nullable=False),
    sa.Column('nome_produto', sa.String(length=120), nullable=False),
    sa.Column('quantidade', sa.Integer(), nullable=False),
    sa.Column('preco_unitario', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.CheckConstraint('quantidade > 0', name=op.f('ck_itens_pedido_quantidade_positiva')),
    sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id'], name=op.f('fk_itens_pedido_pedido_id_pedidos'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['produto_id'], ['produtos.id'], name=op.f('fk_itens_pedido_produto_id_produtos')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_itens_pedido'))
    )
    with op.batch_alter_table('itens_pedido', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_itens_pedido_pedido_id'), ['pedido_id'], unique=False)

    op.create_table('movimentacoes_estoque',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('estoque_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('ENTRADA', 'SAIDA', 'AJUSTE', 'BAIXA_PEDIDO', 'ESTORNO_PEDIDO', name='tipomovimentacaoestoque', native_enum=False, length=30), nullable=False),
    sa.Column('variacao', sa.Integer(), nullable=False),
    sa.Column('saldo_apos', sa.Integer(), nullable=False),
    sa.Column('motivo', sa.String(length=255), nullable=True),
    sa.Column('pedido_id', sa.Integer(), nullable=True),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['estoque_id'], ['estoques.id'], name=op.f('fk_movimentacoes_estoque_estoque_id_estoques')),
    sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id'], name=op.f('fk_movimentacoes_estoque_pedido_id_pedidos'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_movimentacoes_estoque_usuario_id_usuarios'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_movimentacoes_estoque'))
    )
    with op.batch_alter_table('movimentacoes_estoque', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_movimentacoes_estoque_estoque_id'), ['estoque_id'], unique=False)

    op.create_table('movimentacoes_fidelidade',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('pedido_id', sa.Integer(), nullable=True),
    sa.Column('tipo', sa.Enum('ACUMULO', 'RESGATE', 'ESTORNO', name='tipomovimentacaofidelidade', native_enum=False, length=30), nullable=False),
    sa.Column('pontos', sa.Integer(), nullable=False),
    sa.Column('descricao', sa.String(length=255), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id'], name=op.f('fk_movimentacoes_fidelidade_pedido_id_pedidos'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_movimentacoes_fidelidade_usuario_id_usuarios')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_movimentacoes_fidelidade')),
    sa.UniqueConstraint('pedido_id', 'tipo', name='uq_movimentacoes_fidelidade_pedido_tipo')
    )
    with op.batch_alter_table('movimentacoes_fidelidade', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_movimentacoes_fidelidade_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('pagamentos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pedido_id', sa.Integer(), nullable=False),
    sa.Column('metodo', sa.Enum('PIX', 'CARTAO_CREDITO', 'CARTAO_DEBITO', name='metodopagamento', native_enum=False, length=30), nullable=False),
    sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('status', sa.Enum('PENDENTE', 'APROVADO', 'RECUSADO', 'FALHA', 'ESTORNADO', name='statuspagamento', native_enum=False, length=30), nullable=False),
    sa.Column('transacao_externa', sa.String(length=80), nullable=True),
    sa.Column('mensagem', sa.String(length=255), nullable=True),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id'], name=op.f('fk_pagamentos_pedido_id_pedidos')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pagamentos')),
    sa.UniqueConstraint('transacao_externa', name=op.f('uq_pagamentos_transacao_externa'))
    )
    with op.batch_alter_table('pagamentos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pagamentos_pedido_id'), ['pedido_id'], unique=False)
        batch_op.create_index('uq_pagamentos_pendente_por_pedido', ['pedido_id'], unique=True, sqlite_where=sa.text("status = 'PENDENTE'"), postgresql_where=sa.text("status = 'PENDENTE'"))


def downgrade() -> None:
    with op.batch_alter_table('pagamentos', schema=None) as batch_op:
        batch_op.drop_index('uq_pagamentos_pendente_por_pedido', sqlite_where=sa.text("status = 'PENDENTE'"), postgresql_where=sa.text("status = 'PENDENTE'"))
        batch_op.drop_index(batch_op.f('ix_pagamentos_pedido_id'))

    op.drop_table('pagamentos')
    with op.batch_alter_table('movimentacoes_fidelidade', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_movimentacoes_fidelidade_usuario_id'))

    op.drop_table('movimentacoes_fidelidade')
    with op.batch_alter_table('movimentacoes_estoque', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_movimentacoes_estoque_estoque_id'))

    op.drop_table('movimentacoes_estoque')
    with op.batch_alter_table('itens_pedido', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_itens_pedido_pedido_id'))

    op.drop_table('itens_pedido')
    with op.batch_alter_table('pedidos', schema=None) as batch_op:
        batch_op.drop_index('ix_pedidos_unidade_status')
        batch_op.drop_index(batch_op.f('ix_pedidos_status'))
        batch_op.drop_index(batch_op.f('ix_pedidos_cliente_id'))
        batch_op.drop_index(batch_op.f('ix_pedidos_canal_pedido'))

    op.drop_table('pedidos')
    with op.batch_alter_table('auditorias', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_auditorias_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_auditorias_criado_em'))
        batch_op.drop_index(batch_op.f('ix_auditorias_acao'))

    op.drop_table('auditorias')
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuarios_perfil'))

    op.drop_table('usuarios')
    op.drop_table('estoques')
    op.drop_table('unidades')
    with op.batch_alter_table('produtos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_produtos_categoria'))

    op.drop_table('produtos')
