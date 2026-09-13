"""Servidor MCP: expõe a documentação do projeto a agentes de IA via stdio."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from docserver import cli, extract, index

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


def _indice_ausente(caminho_indice: str) -> bool:
    return caminho_indice != ":memory:" and not Path(caminho_indice).exists()


def _mensagem_indice_ausente(caminho_indice: str) -> str:
    return (
        f"Índice não encontrado em {caminho_indice}. Rode 'docserver ingest' primeiro "
        "(ou confira o --indice passado para 'docserver serve')."
    )


def _listar_documentos_texto(caminho_indice: str) -> str:
    """Lista os documentos a partir do índice — nunca do disco. Um `.md` que ainda
    exista em docs-normalizado mas tenha ficado de fora da última ingestão não deve
    aparecer aqui nem ser servido por `ler_documento`: rodar `docserver ingest` (que
    remove órfãos de docs-normalizado) é o que mantém os dois em sincronia."""
    if _indice_ausente(caminho_indice):
        return _mensagem_indice_ausente(caminho_indice)

    conexao = index.criar_indice(caminho_indice)
    try:
        linhas_bd = conexao.execute(
            "SELECT caminho_origem, titulo_doc, secao FROM chunks ORDER BY caminho_origem, ordem"
        ).fetchall()
    finally:
        conexao.close()

    if not linhas_bd:
        return "Nenhum documento indexado ainda. Rode 'docserver ingest' primeiro."

    documentos: dict[str, dict] = {}
    for origem, titulo, secao in linhas_bd:
        doc = documentos.setdefault(origem, {"titulo": "", "secoes": []})
        if not doc["titulo"] and titulo:
            doc["titulo"] = titulo
        if secao and secao not in doc["secoes"]:
            doc["secoes"].append(secao)

    linhas = []
    for origem, doc in documentos.items():
        titulo = doc["titulo"] or Path(origem).stem
        linhas.append(f"{origem} — {titulo}")
        linhas.extend(f"  - {secao}" for secao in doc["secoes"])
    return "\n".join(linhas)


def _buscar_texto(caminho_indice: str, consulta: str, limite: int = 5, documento: str | None = None) -> str:
    if _indice_ausente(caminho_indice):
        return _mensagem_indice_ausente(caminho_indice)

    conexao = index.criar_indice(caminho_indice)
    try:
        origem = None
        if documento:
            candidatos = index.resolver_origem(conexao, documento)
            if not candidatos:
                return f"Documento não encontrado: {documento}. Use listar_documentos para ver o que existe."
            if len(candidatos) > 1:
                opcoes = "\n".join(f"- {c}" for c in candidatos)
                return f"Caminho ambíguo, mais de um documento corresponde a '{documento}':\n{opcoes}"
            origem = candidatos[0]
        resultados = index.buscar_hibrido(conexao, consulta, limite=limite, origem=origem)
    finally:
        conexao.close()
    return cli.formatar_resultados(resultados)


def _dentro_de(caminho: Path, base: Path) -> bool:
    try:
        caminho.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _todos_arquivos_normalizados(docs_normalizado: Path) -> list[Path]:
    if not docs_normalizado.exists():
        return []
    return sorted(p for p in docs_normalizado.rglob("*.md") if p.is_file())


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


def _caminhos_normalizados_no_indice(caminho_indice: str) -> set[str]:
    if _indice_ausente(caminho_indice):
        return set()
    conexao = index.criar_indice(caminho_indice)
    try:
        return {linha[0] for linha in conexao.execute("SELECT DISTINCT caminho_normalizado FROM chunks")}
    finally:
        conexao.close()


def _ler_documento_texto(caminho: str, docs_normalizado: Path, caminho_indice: str) -> str:
    if ".." in Path(caminho).parts:
        return f"Caminho inválido: {caminho}"

    indexados = _caminhos_normalizados_no_indice(caminho_indice)
    candidatos = [
        c
        for c in _resolver_documento(caminho, docs_normalizado)
        if _dentro_de(c, docs_normalizado) and str(c) in indexados
    ]

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
    return _listar_documentos_texto(_config["indice"])


@mcp.tool()
def buscar(consulta: str, limite: int = 5, documento: str | None = None) -> str:
    """Busca na documentação técnica deste projeto e retorna os trechos mais relevantes,
    cada um com o arquivo de origem e a seção. Use SEMPRE antes de responder qualquer
    pergunta sobre este projeto — arquitetura, endpoints, variáveis de ambiente, decisões
    de projeto, processos internos — em vez de responder de memória. A busca é híbrida:
    funciona tanto com termos técnicos exatos (nomes de função, tabela, variável) quanto
    com perguntas em linguagem natural. Se a primeira busca não trouxer o que você
    precisa, tente reformular com o outro estilo — uma pergunta natural se você buscou
    por termo exato, ou o termo técnico provável se você buscou por descrição. Se você já
    sabe (por `listar_documentos` ou por uma busca anterior) qual documento tem a resposta,
    passe `documento` (caminho completo, parcial ou só o nome do arquivo) para restringir
    a busca a ele — evita que trechos de outros documentos, ainda que pareçam relevantes
    pela forma, se misturem na resposta. Um resultado vazio significa que nada no índice
    passou no corte mínimo de relevância — não invente uma resposta nesse caso, avise que
    a documentação não cobre o assunto. Se o trecho retornado não for suficiente, chame
    `ler_documento` com o caminho indicado para ver o documento inteiro."""
    return _buscar_texto(_config["indice"], consulta, limite, documento=documento)


@mcp.tool()
def ler_documento(caminho: str) -> str:
    """Devolve o conteúdo completo de um documento da documentação do projeto. Use
    depois de `buscar` ou `listar_documentos`, quando o trecho retornado não trouxer
    contexto suficiente. Aceita tanto o caminho de origem quanto o normalizado."""
    return _ler_documento_texto(caminho, _config["docs_normalizado"], _config["indice"])


def main(
    docs_normalizado: Path = DOCS_NORMALIZADO_PADRAO,
    indice: str = INDICE_PADRAO,
    transporte: str = "stdio",
    host: str = "127.0.0.1",
    porta: int = 8765,
) -> None:
    configurar(docs_normalizado, indice)
    if transporte == "stdio":
        # stdio não aceita host/porta: o cliente sobe o processo diretamente e fala
        # pelos streams padrão, sem rede — por isso nunca há um link para esse modo.
        mcp.run(transport="stdio")
    else:
        # "http" (streamable-http) expõe um endpoint real em rede, com URL — é o que
        # permite conectar um cliente MCP remoto, ou testar com curl/MCP Inspector.
        mcp.run(transport=transporte, host=host, port=porta)
