import pytest


def _escrever_normalizado(tmp_path, corpo, origem="docs-fonte/exemplo.md", nome="exemplo.md"):
    caminho = tmp_path / nome
    front_matter = (
        "---\n"
        f"origem: {origem}\n"
        "extrator: _extrair_texto_puro\n"
        "ingerido_em: 2026-09-12T10:00:00\n"
        "---\n\n"
    )
    caminho.write_text(front_matter + corpo, encoding="utf-8")
    return caminho


@pytest.fixture
def criar_normalizado(tmp_path):
    def _criar(corpo, origem="docs-fonte/exemplo.md", nome="exemplo.md"):
        return _escrever_normalizado(tmp_path, corpo, origem=origem, nome=nome)

    return _criar


@pytest.fixture
def com_cabecalhos_md(criar_normalizado):
    corpo = (
        "# Manual do Sistema\n\n"
        "## Instalação\n\n"
        "Para instalar, rode o comando de setup e aguarde a conclusão do processo completo.\n\n"
        "## Configuração\n\n"
        "As variáveis de ambiente controlam o comportamento do sistema em produção.\n\n"
        "## Solução de problemas\n\n"
        "Se algo falhar, consulte os logs em /var/log/sistema para mais detalhes.\n"
    )
    return criar_normalizado(corpo, origem="docs-fonte/manual.md", nome="manual.md")


@pytest.fixture
def sem_cabecalhos_md(criar_normalizado):
    paragrafo = (
        "Este é um parágrafo de exemplo com bastante conteúdo textual repetido "
        "para simular um documento longo sem nenhum cabeçalho de seção. "
    )
    corpo = "# Documento Sem Secoes\n\n" + (paragrafo * 80)
    return criar_normalizado(corpo, origem="docs-fonte/corrido.md", nome="corrido.md")


@pytest.fixture
def secao_gigante_md(criar_normalizado):
    paragrafo = (
        "Texto repetido para forçar a subdivisão da seção gigante em múltiplos blocos menores. "
    )
    corpo = (
        "# Documento Com Secao Gigante\n\n"
        "## Introdução\n\nTexto curto de introdução.\n\n"
        "## Referência completa\n\n" + (paragrafo * 120) + "\n\n"
        "## Conclusão\n\nTexto curto de conclusão.\n"
    )
    return criar_normalizado(corpo, origem="docs-fonte/referencia.md", nome="referencia.md")


@pytest.fixture
def docs_fonte(tmp_path):
    caminho = tmp_path / "docs-fonte"
    caminho.mkdir()
    return caminho


@pytest.fixture
def docs_normalizado(tmp_path):
    caminho = tmp_path / "docs-normalizado"
    caminho.mkdir()
    return caminho
