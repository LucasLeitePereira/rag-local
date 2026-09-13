"""Servidor MCP: expõe a documentação do projeto a agentes de IA via stdio."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from docserver import chunk, cli, extract, index

DOCS_NORMALIZADO_PADRAO = Path("docs-normalizado")
INDICE_PADRAO = "data/indice.db"

mcp = FastMCP("docserver")

# Caminhos usados pelas tools. O cliente MCP pode subir o processo em qualquer
# diretório (Claude Desktop, por exemplo, não usa a pasta do projeto), então
# `configurar` fixa caminhos absolutos a partir dos argumentos da CLI.
_config: dict = {"docs_normalizado": DOCS_NORMALIZADO_PADRAO, "indice": INDICE_PADRAO}


def configurar(docs_normalizado: Path, indice: str) -> None:
    _config["docs_normalizado"] = Path(docs_normalizado).resolve()
    _config["indice"] = str(Path(indice).resolve())


def _todos_arquivos_normalizados(docs_normalizado: Path) -> list[Path]:
    if not docs_normalizado.exists():
        return []
    return sorted(p for p in docs_normalizado.rglob("*.md") if p.is_file())


def _listar_documentos_texto(docs_normalizado: Path) -> str:
    arquivos = _todos_arquivos_normalizados(docs_normalizado)
    if not arquivos:
        return "Nenhum documento indexado ainda. Rode 'docserver ingest' primeiro."

    linhas = []
    for arquivo in arquivos:
        chunks = chunk.chunkar_arquivo(arquivo)
        if not chunks:
            continue
        origem = chunks[0]["caminho_origem"]
        titulo = chunks[0]["titulo_doc"] or arquivo.stem
        secoes = list(dict.fromkeys(c["secao"] for c in chunks if c["secao"]))
        linhas.append(f"{origem} — {titulo}")
        linhas.extend(f"  - {secao}" for secao in secoes)
    return "\n".join(linhas)


def _buscar_texto(caminho_indice: str, consulta: str, limite: int = 5) -> str:
    if caminho_indice != ":memory:" and not Path(caminho_indice).exists():
        return (
            f"Índice não encontrado em {caminho_indice}. Rode 'docserver ingest' primeiro "
            "(ou confira o --indice passado para 'docserver serve')."
        )
    conexao = index.criar_indice(caminho_indice)
    try:
        resultados = index.buscar_hibrido(conexao, consulta, limite=limite)
    finally:
        conexao.close()
    return cli.formatar_resultados(resultados)


def _dentro_de(caminho: Path, base: Path) -> bool:
    try:
        caminho.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _resolver_documento(caminho: str, docs_normalizado: Path) -> list[Path]:
    alvo = caminho.strip()
    if alvo.startswith("docs-fonte/"):
        alvo = str(Path(alvo[len("docs-fonte/") :]).with_suffix(".md"))
    elif alvo.startswith("docs-normalizado/"):
        alvo = alvo[len("docs-normalizado/") :]

    candidatos = []
    for arquivo in _todos_arquivos_normalizados(docs_normalizado):
        relativo = arquivo.relative_to(docs_normalizado).as_posix()
        if relativo == alvo or relativo.endswith("/" + alvo) or arquivo.name == alvo:
            candidatos.append(arquivo)
    return candidatos


def _ler_documento_texto(caminho: str, docs_normalizado: Path) -> str:
    if ".." in Path(caminho).parts:
        return f"Caminho inválido: {caminho}"

    candidatos = [c for c in _resolver_documento(caminho, docs_normalizado) if _dentro_de(c, docs_normalizado)]

    if not candidatos:
        return f"Documento não encontrado: {caminho}. Use listar_documentos para ver o que existe."

    if len(candidatos) > 1:
        opcoes = "\n".join(f"- {c.relative_to(docs_normalizado).as_posix()}" for c in candidatos)
        return f"Caminho ambíguo, mais de um documento corresponde a '{caminho}':\n{opcoes}"

    conteudo = candidatos[0].read_text(encoding="utf-8")
    _, corpo = extract.ler_front_matter(conteudo)
    return corpo


@mcp.tool()
def listar_documentos() -> str:
    """Lista toda a documentação disponível deste projeto, em árvore, com o título e as
    seções de cada documento. Use esta ferramenta primeiro quando não souber o que existe
    na documentação, ou quando a busca por termos não retornar nada útil. Barata de
    chamar — prefira listar e ler o documento certo a fazer várias buscas às cegas."""
    return _listar_documentos_texto(_config["docs_normalizado"])


@mcp.tool()
def buscar(consulta: str, limite: int = 5) -> str:
    """Busca na documentação técnica deste projeto e retorna os trechos mais relevantes,
    cada um com o arquivo de origem e a seção. Use SEMPRE antes de responder qualquer
    pergunta sobre este projeto — arquitetura, endpoints, variáveis de ambiente, decisões
    de projeto, processos internos — em vez de responder de memória. A busca é híbrida:
    funciona tanto com termos técnicos exatos (nomes de função, tabela, variável) quanto
    com perguntas em linguagem natural. Se a primeira busca não trouxer o que você
    precisa, tente reformular com o outro estilo — uma pergunta natural se você buscou
    por termo exato, ou o termo técnico provável se você buscou por descrição. Se o
    trecho retornado não for suficiente, chame `ler_documento` com o caminho indicado
    para ver o documento inteiro."""
    return _buscar_texto(_config["indice"], consulta, limite)


@mcp.tool()
def ler_documento(caminho: str) -> str:
    """Devolve o conteúdo completo de um documento da documentação do projeto. Use
    depois de `buscar` ou `listar_documentos`, quando o trecho retornado não trouxer
    contexto suficiente. Aceita tanto o caminho de origem quanto o normalizado."""
    return _ler_documento_texto(caminho, _config["docs_normalizado"])


def main(docs_normalizado: Path = DOCS_NORMALIZADO_PADRAO, indice: str = INDICE_PADRAO) -> None:
    configurar(docs_normalizado, indice)
    mcp.run()
