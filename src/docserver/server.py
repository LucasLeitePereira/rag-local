"""Servidor MCP: expõe a documentação do projeto a agentes de IA via stdio."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from fastmcp import FastMCP

from docserver import cli, embed, extract, index

DOCS_NORMALIZADO_PADRAO = Path("docs-normalizado")
INDICE_PADRAO = "data/indice.db"

logger = logging.getLogger(__name__)

mcp = FastMCP("docserver")

# Caminhos usados pelas tools. O cliente MCP pode subir o processo em qualquer
# diretório (Claude Desktop, por exemplo, não usa a pasta do projeto), então
# `configurar` fixa caminhos absolutos a partir dos argumentos da CLI.
_config: dict = {"docs_normalizado": DOCS_NORMALIZADO_PADRAO, "indice": INDICE_PADRAO}

# Conexão única com o índice enquanto `main` está servindo: abrir uma conexão por
# tool call recriava o esquema e recarregava a extensão sqlite-vec a cada chamada.
# As tools síncronas podem rodar em threads diferentes, daí o lock.
_persistente: dict = {"ativa": False, "conexao": None}
_lock_conexao = threading.Lock()


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


def _mensagem_esquema(conexao) -> str | None:
    mensagem = index.verificar_esquema(conexao)
    return f"Índice indisponível: {mensagem}" if mensagem else None


def _fechar_conexao_persistente() -> None:
    conexao = _persistente["conexao"]
    _persistente["conexao"] = None
    if conexao is not None:
        conexao.close()


@contextmanager
def _conexao(caminho_indice: str):
    """Conexão com o índice: a persistente, se o servidor está ativo e o caminho é o
    configurado; senão uma conexão avulsa, fechada ao sair. Quem chama deve checar
    `_indice_ausente` antes — abrir um caminho inexistente criaria o arquivo."""
    if _persistente["ativa"] and caminho_indice == _config["indice"]:
        with _lock_conexao:
            if _persistente["conexao"] is None:
                _persistente["conexao"] = index.criar_indice(caminho_indice, compartilhada=True)
            yield _persistente["conexao"]
        return

    conexao = index.criar_indice(caminho_indice)
    try:
        yield conexao
    finally:
        conexao.close()


def _listar_documentos_texto(caminho_indice: str) -> str:
    """Lista os documentos a partir do índice — nunca do disco. Um `.md` que ainda
    exista em docs-normalizado mas tenha ficado de fora da última ingestão não deve
    aparecer aqui nem ser servido por `ler_documento`: rodar `docserver ingest` (que
    remove órfãos de docs-normalizado) é o que mantém os dois em sincronia."""
    if _indice_ausente(caminho_indice):
        return _mensagem_indice_ausente(caminho_indice)

    with _conexao(caminho_indice) as conexao:
        if mensagem := _mensagem_esquema(conexao):
            return mensagem
        linhas_bd = conexao.execute(
            "SELECT caminho_origem, titulo_doc, secao FROM chunks ORDER BY caminho_origem, ordem"
        ).fetchall()

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


def _formatar_resultados_mcp(resultados: list[dict]) -> str:
    """Formata os resultados para o agente com o chunk inteiro — o corte de 300
    caracteres da CLI deixava o agente com frases cortadas ao meio — e com os
    metadados que permitem citar e localizar o trecho."""
    if not resultados:
        return cli.MENSAGEM_SEM_RESULTADOS
    blocos = []
    for i, r in enumerate(resultados, 1):
        detalhes = [f"chunk {r['id']}", f"posição {r['ordem']} no documento"]
        if r.get("similaridade") is not None:
            detalhes.append(f"similaridade {r['similaridade']:.2f}")
        cabecalho = f"[{i}] {r['caminho_origem']} › {r['secao']}  ({' · '.join(detalhes)})"
        blocos.append(f"{cabecalho}\n{r['texto']}")
    return "\n\n".join(blocos)


def _buscar_texto(caminho_indice: str, consulta: str, limite: int = 5, documento: str | None = None) -> str:
    if _indice_ausente(caminho_indice):
        return _mensagem_indice_ausente(caminho_indice)

    with _conexao(caminho_indice) as conexao:
        if mensagem := _mensagem_esquema(conexao):
            return mensagem
        origem = None
        if documento:
            candidatos = index.resolver_origem(conexao, documento)
            if not candidatos:
                return f"Documento não encontrado: {documento}. Use listar_documentos para ver o que existe."
            if len(candidatos) > 1:
                opcoes = "\n".join(f"- {c}" for c in candidatos)
                return f"Caminho ambíguo, mais de um documento corresponde a '{documento}':\n{opcoes}"
            origem = candidatos[0]
        avisos: list[str] = []
        resultados = index.buscar_hibrido(conexao, consulta, limite=limite, origem=origem, avisos=avisos)
    texto = _formatar_resultados_mcp(resultados)
    if avisos:
        texto = "\n".join(f"Aviso: {aviso}" for aviso in avisos) + "\n\n" + texto
    return texto


def _dentro_de(caminho: Path, base: Path) -> bool:
    try:
        caminho.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _ler_documento_texto(caminho: str, docs_normalizado: Path, caminho_indice: str) -> str:
    """Resolve o documento pelo índice (origem ou normalizado, completo, parcial ou só
    o nome) e lê o arquivo relativo a `docs_normalizado` — o índice guarda o caminho
    normalizado relativo a essa pasta, então funciona de qualquer cwd."""
    if ".." in Path(caminho.replace("\\", "/")).parts:
        return f"Caminho inválido: {caminho}"
    if _indice_ausente(caminho_indice):
        return _mensagem_indice_ausente(caminho_indice)

    with _conexao(caminho_indice) as conexao:
        if mensagem := _mensagem_esquema(conexao):
            return mensagem
        candidatos = index.resolver_documento(conexao, caminho)

    if not candidatos:
        return f"Documento não encontrado: {caminho}. Use listar_documentos para ver o que existe."

    if len(candidatos) > 1:
        opcoes = "\n".join(f"- {origem}" for origem, _ in candidatos)
        return f"Caminho ambíguo, mais de um documento corresponde a '{caminho}':\n{opcoes}"

    origem, normalizado = candidatos[0]
    arquivo = Path(docs_normalizado) / normalizado
    if not _dentro_de(arquivo, Path(docs_normalizado)) or not arquivo.is_file():
        return (
            f"Documento {origem} está no índice, mas o arquivo normalizado não foi encontrado "
            f"em {docs_normalizado}. Rode 'docserver ingest' novamente (ou confira o "
            "--docs-normalizado passado para 'docserver serve')."
        )

    _, corpo = extract.ler_front_matter(arquivo.read_text(encoding="utf-8"))
    return corpo


def _aquecer(caminho_indice: str) -> None:
    """Carrega o modelo de embeddings antes de aceitar requisições. Carregá-lo na
    primeira busca (import de torch + pesos) levava mais de 120 s e segurava as
    chamadas seguintes na fila. Sem índice vetorial não há o que aquecer; qualquer
    falha aqui só é registrada — o servidor sobe mesmo assim."""
    if _indice_ausente(caminho_indice):
        return
    with _conexao(caminho_indice) as conexao:
        tem_vetores = index._tabela_vetorial_existe(conexao)
    if not tem_vetores:
        return

    inicio = time.perf_counter()
    try:
        embed.embeddar_consulta("aquecimento")
    except Exception as erro:
        logger.warning("não foi possível pré-carregar o modelo de embeddings: %s", erro)
        return
    logger.info("modelo de embeddings carregado em %.1fs", time.perf_counter() - inicio)


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
    cada um completo, com o arquivo de origem, a seção e a posição no documento. Use
    SEMPRE antes de responder qualquer
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
    aquecer: bool = True,
) -> None:
    # logs vão para stderr: no modo stdio o stdout é o canal do protocolo MCP
    logging.basicConfig(level=logging.INFO, format="docserver: %(message)s")
    configurar(docs_normalizado, indice)
    _persistente["ativa"] = True
    try:
        if aquecer:
            _aquecer(_config["indice"])
        if transporte == "stdio":
            # stdio não aceita host/porta: o cliente sobe o processo diretamente e fala
            # pelos streams padrão, sem rede — por isso nunca há um link para esse modo.
            mcp.run(transport="stdio")
        else:
            # "http" (streamable-http) expõe um endpoint real em rede, com URL — é o que
            # permite conectar um cliente MCP remoto, ou testar com curl/MCP Inspector.
            mcp.run(transport=transporte, host=host, port=porta)
    finally:
        _persistente["ativa"] = False
        with _lock_conexao:
            _fechar_conexao_persistente()
