import sys
from decimal import Decimal

from app.config import obter_settings
from app.container import Container, montar_container
from app.domain.entities import Estoque, Produto, Unidade, Usuario
from app.domain.enums import Perfil

SENHA_PADRAO = "Senha@123"

PRODUTOS = [
    ("Baião de Dois", "Arroz, feijão de corda, queijo coalho e carne de sol", "Pratos", "38.90"),
    ("Carne de Sol com Macaxeira", "Carne de sol na manteiga com macaxeira frita", "Pratos", "54.90"),
    ("Moqueca Baiana", "Peixe, leite de coco e azeite de dendê", "Pratos", "69.90"),
    ("Tapioca de Queijo Coalho", "Tapioca recheada com queijo coalho", "Lanches", "14.50"),
    ("Acarajé", "Bolinho de feijão-fradinho com vatapá e camarão", "Lanches", "18.00"),
    ("Cuscuz Nordestino", "Cuscuz com ovo e carne seca", "Lanches", "16.50"),
    ("Suco de Caju", "Suco natural 500ml", "Bebidas", "9.00"),
    ("Água de Coco", "Coco gelado", "Bebidas", "8.00"),
    ("Cartola", "Banana frita com queijo e canela", "Sobremesas", "15.00"),
]


def popular(container: Container) -> bool:
    with container.uow() as uow:
        if uow.usuarios.obter_por_email("admin@raizes.com"):
            return False

        recife = uow.unidades.adicionar(
            Unidade(nome="Raízes do Nordeste - Boa Viagem", cidade="Recife", endereco="Av. Boa Viagem, 1000")
        )
        salvador = uow.unidades.adicionar(
            Unidade(nome="Raízes do Nordeste - Pelourinho", cidade="Salvador", endereco="Largo do Pelourinho, 25")
        )
        fortaleza = uow.unidades.adicionar(
            Unidade(nome="Raízes do Nordeste - Iracema", cidade="Fortaleza", endereco="Av. Beira Mar, 500")
        )

        senha_hash = container.hasher.gerar(SENHA_PADRAO)

        def usuario(nome: str, email: str, perfil: Perfil, unidade: Unidade | None = None, consentiu=False):
            u = Usuario(
                nome=nome, email=email, senha_hash=senha_hash, perfil=perfil,
                unidade_id=unidade.id if unidade else None,
            )
            u.definir_consentimento(consentiu)
            uow.usuarios.adicionar(u)

        usuario("Admin Raízes", "admin@raizes.com", Perfil.ADMIN)
        usuario("Gerente Geral", "gerente@raizes.com", Perfil.GERENTE)
        usuario("Atendente Recife", "atendente@raizes.com", Perfil.ATENDENTE, recife)
        usuario("Cozinha Recife", "cozinha@raizes.com", Perfil.COZINHA, recife)
        usuario("Maria Cliente", "cliente@raizes.com", Perfil.CLIENTE, consentiu=True)
        usuario("João Cliente", "cliente2@raizes.com", Perfil.CLIENTE)

        for nome, descricao, categoria, preco in PRODUTOS:
            produto = uow.produtos.adicionar(
                Produto(nome=nome, descricao=descricao, categoria=categoria, preco=Decimal(preco))
            )
            for unidade in (recife, salvador, fortaleza):
                if unidade is fortaleza and nome == "Moqueca Baiana":
                    continue
                quantidade = 3 if (unidade is recife and nome == "Acarajé") else 50
                uow.estoques.adicionar(
                    Estoque(unidade_id=unidade.id, produto_id=produto.id, quantidade=quantidade)
                )
        uow.commit()
        return True


def main() -> int:
    container = montar_container(obter_settings())
    if popular(container):
        print("Seed aplicado. Usuários de teste (senha: Senha@123): admin, gerente, atendente, cozinha, cliente, cliente2 @raizes.com")
        return 0
    print("O banco já foi populado (admin@raizes.com existe). Nada foi alterado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
