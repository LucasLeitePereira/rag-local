"""Ponto de entrada da CLI: ingest, watch, search, stats, serve."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from docserver import chunk, embed, extract, index

DOCS_FONTE_PADRAO = Path("docs-fonte")
DOCS_NORMALIZADO_PADRAO = Path("docs-normalizado")
INDICE_PADRAO = "data/indice.db"

# `server-mcp` não aceita caminhos: usa sempre os do próprio projeto, independente do
# diretório de onde o comando é executado (instalação editável, layout src/).
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
INDICE_FIXO = RAIZ_PROJETO / "data" / "indice.db"
DOCS_NORMALIZADO_FIXO = RAIZ_PROJETO / "docs-normalizado"
PORTA_SERVER_MCP = 8765

MIN_CARACTERES_SUSPEITO = 20

MENSAGEM_SEM_RESULTADOS = (
    "Nenhum trecho relevante encontrado. Tente reformular a consulta "
    "(termo técnico exato ou pergunta em linguagem natural), restrinja a um "
    "documento específico com o parâmetro documento, ou use listar_documentos "
    "para ver o que existe."
)


class ErroIngestao(Exception):
    """A ingestão foi abortada antes de alterar docs-normalizado ou o índice."""


def _deve_ignorar(caminho: Path) -> bool:
    return caminho.name.startswith(".") or caminho.name.startswith("~$")


def validar_docs_fonte(docs_fonte: Path) -> None:
    """Um `--docs-fonte` inexistente (erro de digitação, cwd errado) faria o `rglob`
    devolver nada e a ingestão apagar tudo como órfão — nunca seguir nesse caso."""
    if not docs_fonte.is_dir():
        raise ErroIngestao(
            f"pasta de documentos de origem não encontrada: {docs_fonte.resolve()}. "
            "Confira o --docs-fonte ou o diretório de onde o comando foi executado."
        )


def _remover_gerados(docs_normalizado: Path, manter: set[Path]) -> tuple[list[str], list[str]]:
    """Apaga de docs_normalizado os `.md` gerados pelo docserver que não estão em
    `manter`. Arquivos que não vieram do docserver são preservados. Devolve
    (removidos, preservados)."""
    removidos: list[str] = []
    preservados: list[str] = []
    if not docs_normalizado.exists():
        return removidos, preservados
    for arquivo in sorted(p for p in docs_normalizado.rglob("*.md") if p.is_file()):
        if arquivo.resolve() in manter:
            continue
        if extract.gerado_pelo_docserver(arquivo):
            arquivo.unlink()
            removidos.append(str(arquivo))
        else:
            preservados.append(str(arquivo))
    for pasta in sorted((p for p in docs_normalizado.rglob("*") if p.is_dir()), reverse=True):
        try:
            pasta.rmdir()
        except OSError:
            pass
    return removidos, preservados


def limpar_saidas(docs_normalizado: Path, caminho_indice: str) -> list[str]:
    """`ingest --limpar`: remove só o que o docserver gerou e esvazia o índice."""
    removidos, _ = _remover_gerados(docs_normalizado, manter=set())
    if Path(caminho_indice).exists():
        conexao = index.criar_indice(caminho_indice)
        try:
            index.limpar_indice(conexao)
        finally:
            conexao.close()
    return removidos


def executar_ingestao(
    docs_fonte: Path,
    docs_normalizado: Path,
    caminho_indice: str,
    sem_embeddings: bool = False,
    embeddar_passagem_fn=None,
    nome_modelo: str | None = None,
    forcar: bool = False,
) -> dict:
    """Pipeline completo. Levanta `ErroIngestao` — sem tocar em docs-normalizado nem
    no índice — se `docs_fonte` não existe, ou (a menos que `forcar`) se não há nenhum
    arquivo suportado ou se o resultado esvaziaria um índice que tinha conteúdo."""
    validar_docs_fonte(docs_fonte)
    inicio = time.perf_counter()
    relatorio = {
        "processados": 0,
        "chunks": 0,
        "ignorados": [],
        "falhas": [],
        "suspeitos": [],
        "removidos": [],
        "preservados": [],
    }

    suportados: list[Path] = []
    for caminho in sorted(p for p in docs_fonte.rglob("*") if p.is_file()):
        if _deve_ignorar(caminho):
            continue
        if caminho.suffix.lower() not in extract.EXTRATORES:
            relatorio["ignorados"].append(str(caminho))
            continue
        suportados.append(caminho)

    if not suportados and not forcar:
        raise ErroIngestao(
            f"nenhum arquivo em formato suportado em {docs_fonte.resolve()}. "
            "Nada foi alterado; use --forcar se a intenção é mesmo esvaziar o índice."
        )

    todos_chunks: list[dict] = []
    gerados: set[Path] = set()
    destinos: dict[str, Path] = {}
    for caminho in suportados:
        destino = extract.caminho_normalizado_para(caminho, docs_fonte, docs_normalizado)
        # em sistemas de arquivos que ignoram maiúsculas, `Guia.md` e `guia.md` de
        # pastas espelhadas cairiam no mesmo arquivo — o segundo sobrescreveria o primeiro.
        chave = str(destino.resolve()).casefold()
        if chave in destinos:
            relatorio["falhas"].append(
                (str(caminho), f"colide com {destinos[chave]} no mesmo arquivo normalizado ({destino})")
            )
            continue
        try:
            caminho_normalizado_arquivo = extract.normalizar(caminho, docs_fonte, docs_normalizado)
        except Exception as erro:
            relatorio["falhas"].append((str(caminho), str(erro)))
            continue

        destinos[chave] = caminho
        gerados.add(caminho_normalizado_arquivo.resolve())
        relatorio["processados"] += 1
        conteudo = caminho_normalizado_arquivo.read_text(encoding="utf-8")
        _, corpo = extract.ler_front_matter(conteudo)
        if len(corpo.strip()) < MIN_CARACTERES_SUSPEITO:
            relatorio["suspeitos"].append(str(caminho))

        todos_chunks.extend(chunk.chunkar_arquivo(caminho_normalizado_arquivo, docs_normalizado))

    if not todos_chunks and not forcar and index.contar_chunks(caminho_indice) > 0:
        raise ErroIngestao(
            "a ingestão não gerou nenhum chunk e substituiria um índice que tem conteúdo. "
            "Índice e docs-normalizado foram mantidos; use --forcar se a intenção é mesmo esvaziá-lo."
        )

    # arquivos normalizados cuja fonte original sumiu (foi apagada, renomeada, ou
    # passou a falhar na extração) não devem continuar servíveis nem aparecer na
    # listagem — é exatamente o que causava respostas misturando documentos.
    relatorio["removidos"], relatorio["preservados"] = _remover_gerados(docs_normalizado, gerados)

    embeddings = None
    if not sem_embeddings and todos_chunks:
        if embeddar_passagem_fn is not None:
            embeddings = [embeddar_passagem_fn(c) for c in todos_chunks]
        else:
            embeddings = embed.embeddar_passagens(todos_chunks)

    conexao = index.criar_indice(caminho_indice)
    relatorio["camada_vetorial_removida"] = index.reindexar(
        conexao, todos_chunks, embeddings=embeddings, nome_modelo=nome_modelo
    )
    conexao.close()

    relatorio["chunks"] = len(todos_chunks)
    relatorio["tempo"] = time.perf_counter() - inicio
    return relatorio


def formatar_relatorio(relatorio: dict) -> str:
    linhas = [
        f"Ingestão concluída em {relatorio['tempo']:.1f}s",
        "",
        f"  Arquivos processados:   {relatorio['processados']}",
        f"  Chunks indexados:      {relatorio['chunks']}",
        f"  Ignorados (formato):     {len(relatorio['ignorados'])}",
        f"  Falhas de extração:      {len(relatorio['falhas'])}",
        f"  Suspeitos (texto vazio): {len(relatorio['suspeitos'])}",
        f"  Removidos (órfãos):      {len(relatorio['removidos'])}",
    ]
    if relatorio.get("camada_vetorial_removida"):
        linhas.append("")
        linhas.append(
            "Camada vetorial removida: ingestão sem embeddings — a busca passa a ser só léxica "
            "até uma ingestão com embeddings."
        )
    if relatorio["falhas"]:
        linhas.append("")
        linhas.append("Falhas:")
        for caminho, erro in relatorio["falhas"]:
            linhas.append(f"  ✗ {caminho} — {erro}")
    if relatorio["suspeitos"]:
        linhas.append("")
        linhas.append("Suspeitos (provável PDF escaneado, sem texto extraível):")
        for caminho in relatorio["suspeitos"]:
            linhas.append(f"  ? {caminho}")
    if relatorio["removidos"]:
        linhas.append("")
        linhas.append("Removidos (fonte original não existe mais):")
        for caminho in relatorio["removidos"]:
            linhas.append(f"  - {caminho}")
    if relatorio.get("preservados"):
        linhas.append("")
        linhas.append("Preservados (.md em docs-normalizado que não foram gerados pelo docserver):")
        for caminho in relatorio["preservados"]:
            linhas.append(f"  · {caminho}")
    return "\n".join(linhas)


def executar_busca(
    caminho_indice: str,
    consulta: str,
    limite: int = 5,
    modo: str = "hibrido",
    origem: str | None = None,
    avisos: list[str] | None = None,
) -> list[dict]:
    conexao = index.criar_indice(caminho_indice)
    try:
        if modo == "lexico":
            return index.buscar(conexao, consulta, limite, origem=origem)
        if modo == "vetorial":
            return index.buscar_vetorial(conexao, consulta, limite, origem=origem)
        return index.buscar_hibrido(conexao, consulta, limite, origem=origem, avisos=avisos)
    finally:
        conexao.close()


def formatar_resultados(resultados: list[dict]) -> str:
    if not resultados:
        return MENSAGEM_SEM_RESULTADOS
    blocos = []
    for i, r in enumerate(resultados, 1):
        blocos.append(f"[{i}] {r['caminho_origem']} › {r['secao']}\n{r['texto'][:300]}")
    return "\n\n".join(blocos)


def _carregar_perguntas(caminho_perguntas: Path) -> list[dict]:
    import yaml

    conteudo = Path(caminho_perguntas).read_text(encoding="utf-8")
    return yaml.safe_load(conteudo) or []


def _buscar_no_modo(
    conexao,
    modo: str,
    pergunta: str,
    embeddar_consulta_fn=None,
    nome_modelo: str | None = None,
    dimensao: int | None = None,
) -> list[dict]:
    if modo == "lexico":
        return index.buscar(conexao, pergunta, limite=5)
    if modo == "vetorial":
        return index.buscar_vetorial(
            conexao,
            pergunta,
            limite=5,
            embeddar_consulta_fn=embeddar_consulta_fn,
            nome_modelo=nome_modelo,
            dimensao=dimensao,
        )
    if modo == "hibrido":
        return index.buscar_hibrido(
            conexao,
            pergunta,
            limite=5,
            embeddar_consulta_fn=embeddar_consulta_fn,
            nome_modelo=nome_modelo,
            dimensao=dimensao,
        )
    raise ValueError(f"modo de busca desconhecido: {modo}")


def executar_avaliacao(
    caminho_perguntas: Path,
    caminho_indice: str,
    modos: tuple[str, ...] = ("lexico",),
    embeddar_consulta_fn=None,
    nome_modelo: str | None = None,
    dimensao: int | None = None,
) -> dict:
    """Roda cada pergunta do conjunto de avaliação e mede se o doc esperado aparece no top-5."""
    perguntas = _carregar_perguntas(caminho_perguntas)
    contagem: dict[str, dict[str, list[int]]] = {modo: {} for modo in modos}

    conexao = index.criar_indice(caminho_indice)
    try:
        for item in perguntas:
            perfil = item["perfil"]
            esperado = item["esperado"]
            for modo in modos:
                marcador = contagem[modo].setdefault(perfil, [0, 0])
                topo = _buscar_no_modo(
                    conexao,
                    modo,
                    item["pergunta"],
                    embeddar_consulta_fn=embeddar_consulta_fn,
                    nome_modelo=nome_modelo,
                    dimensao=dimensao,
                )
                acertou = any(r["caminho_origem"] == esperado for r in topo)
                marcador[1] += 1
                if acertou:
                    marcador[0] += 1
    finally:
        conexao.close()

    return contagem


def formatar_tabela_avaliacao(contagem: dict) -> str:
    modos = list(contagem.keys())
    perfis = sorted({perfil for dados in contagem.values() for perfil in dados})

    def _somar(perfil: str) -> list[int]:
        acerto = sum(contagem[modo].get(perfil, [0, 0])[0] for modo in modos)
        total = sum(contagem[modo].get(perfil, [0, 0])[1] for modo in modos)
        return [acerto, total]

    largura_perfil = max(len(p) for p in [*perfis, "geral"]) + 2
    cabecalho = " " * largura_perfil + "".join(f"{modo:>10}" for modo in modos)
    linhas = [cabecalho]
    for perfil in perfis:
        celulas = "".join(f"{contagem[modo][perfil][0]}/{contagem[modo][perfil][1]:<8}".rjust(10) for modo in modos)
        linhas.append(f"{perfil:<{largura_perfil}}{celulas}")
    return "\n".join(linhas)


def _comando_avaliar(args: argparse.Namespace) -> None:
    resultado = executar_avaliacao(
        Path(args.perguntas), args.indice, modos=("lexico", "vetorial", "hibrido")
    )
    print(formatar_tabela_avaliacao(resultado))


def executar_stats(caminho_indice: str) -> dict:
    conexao = index.criar_indice(caminho_indice)
    try:
        total_chunks = conexao.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        total_docs = conexao.execute(
            "SELECT COUNT(DISTINCT caminho_origem) FROM chunks"
        ).fetchone()[0]
        modelo = None
        tem_metadados = conexao.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metadados_indice'"
        ).fetchone()
        if tem_metadados:
            linha = conexao.execute(
                "SELECT valor FROM metadados_indice WHERE chave = 'modelo'"
            ).fetchone()
            modelo = linha[0] if linha else None
    finally:
        conexao.close()
    return {"documentos": total_docs, "chunks": total_chunks, "modelo": modelo}


def formatar_stats(stats: dict) -> str:
    return "\n".join(
        [
            f"Documentos indexados: {stats['documentos']}",
            f"Chunks indexados:     {stats['chunks']}",
            f"Modelo de embeddings: {stats['modelo'] or 'nenhum (modo léxico apenas)'}",
        ]
    )


def _comando_stats(args: argparse.Namespace) -> None:
    print(formatar_stats(executar_stats(args.indice)))


def _comando_serve(args: argparse.Namespace) -> None:
    from docserver.server import main as servir

    servir(
        docs_normalizado=Path(args.docs_normalizado),
        indice=args.indice,
        transporte="http" if args.http else "stdio",
        host=args.host,
        porta=args.porta,
        aquecer=not args.sem_aquecimento,
    )


def _ip_rede_local() -> str:
    """IP desta máquina na rede local. O `connect` em UDP só escolhe a interface de
    saída — nenhum pacote é enviado."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def _comando_server_mcp(args: argparse.Namespace) -> None:
    from docserver.server import main as servir

    if not INDICE_FIXO.exists():
        print(
            f"Índice não encontrado em {INDICE_FIXO}. Rode 'docserver ingest' na raiz do projeto primeiro.",
            file=sys.stderr,
        )
        sys.exit(1)

    host = "0.0.0.0" if args.local else "127.0.0.1"
    endereco = _ip_rede_local() if args.local else "127.0.0.1"
    print(f"docserver: servidor MCP em http://{endereco}:{PORTA_SERVER_MCP}/mcp", file=sys.stderr)
    if args.local:
        print(
            "docserver: aviso — sem autenticação; qualquer dispositivo da rede local tem acesso.",
            file=sys.stderr,
        )

    servir(
        docs_normalizado=DOCS_NORMALIZADO_FIXO,
        indice=str(INDICE_FIXO),
        transporte="http",
        host=host,
        porta=PORTA_SERVER_MCP,
        aquecer=True,
    )


def _comando_ingest(args: argparse.Namespace) -> None:
    docs_fonte = Path(args.docs_fonte)
    docs_normalizado = Path(args.docs_normalizado)
    try:
        # valida antes do --limpar: com a fonte errada, nada pode ser apagado
        validar_docs_fonte(docs_fonte)
        if args.limpar:
            limpar_saidas(docs_normalizado, args.indice)

        Path(args.indice).parent.mkdir(parents=True, exist_ok=True)
        docs_normalizado.mkdir(parents=True, exist_ok=True)

        relatorio = executar_ingestao(
            docs_fonte,
            docs_normalizado,
            args.indice,
            sem_embeddings=args.sem_embeddings,
            forcar=args.forcar,
        )
    except ErroIngestao as erro:
        print(f"Ingestão abortada: {erro}", file=sys.stderr)
        sys.exit(1)
    print(formatar_relatorio(relatorio))


def _comando_watch(args: argparse.Namespace) -> None:
    from docserver import watch

    docs_fonte = Path(args.docs_fonte)
    docs_normalizado = Path(args.docs_normalizado)
    try:
        validar_docs_fonte(docs_fonte)
    except ErroIngestao as erro:
        print(f"Ingestão abortada: {erro}", file=sys.stderr)
        sys.exit(1)
    Path(args.indice).parent.mkdir(parents=True, exist_ok=True)
    docs_normalizado.mkdir(parents=True, exist_ok=True)

    try:
        watch.observar(
            docs_fonte,
            docs_normalizado,
            args.indice,
            sem_embeddings=args.sem_embeddings,
            espera=args.espera,
        )
    except KeyboardInterrupt:
        print("docserver: watcher encerrado")


def _comando_search(args: argparse.Namespace) -> None:
    origem = None
    if args.documento:
        conexao = index.criar_indice(args.indice)
        try:
            candidatos = index.resolver_origem(conexao, args.documento)
        finally:
            conexao.close()
        if not candidatos:
            print(f"Documento não encontrado: {args.documento}. Use 'docserver stats' ou verifique o índice.")
            return
        if len(candidatos) > 1:
            print(f"Caminho ambíguo, mais de um documento corresponde a '{args.documento}':")
            for candidato in candidatos:
                print(f"  - {candidato}")
            return
        origem = candidatos[0]

    avisos: list[str] = []
    resultados = executar_busca(
        args.indice, args.consulta, args.limite, modo=args.modo, origem=origem, avisos=avisos
    )
    for aviso in avisos:
        print(f"Aviso: {aviso}")
    print(formatar_resultados(resultados))


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docserver")
    parser.add_argument("--docs-fonte", default=str(DOCS_FONTE_PADRAO))
    parser.add_argument("--docs-normalizado", default=str(DOCS_NORMALIZADO_PADRAO))
    parser.add_argument("--indice", default=INDICE_PADRAO)
    subs = parser.add_subparsers(dest="comando", required=True)

    p_ingest = subs.add_parser("ingest", help="roda o pipeline completo de ingestão")
    p_ingest.add_argument(
        "--limpar",
        action="store_true",
        help="remove os .md gerados pelo docserver e esvazia o índice antes de reingerir",
    )
    p_ingest.add_argument("--sem-embeddings", action="store_true")
    p_ingest.add_argument(
        "--forcar",
        action="store_true",
        help="permite concluir mesmo sem arquivos suportados, esvaziando um índice com conteúdo",
    )
    p_ingest.set_defaults(func=_comando_ingest)

    p_watch = subs.add_parser(
        "watch", help="observa docs-fonte e reingere automaticamente quando algum arquivo muda"
    )
    p_watch.add_argument(
        "--espera",
        type=float,
        default=2.0,
        help="segundos sem novas mudanças antes de reingerir (agrupa cópias e salvamentos em lote)",
    )
    p_watch.add_argument("--sem-embeddings", action="store_true")
    p_watch.set_defaults(func=_comando_watch)

    p_search = subs.add_parser("search", help="busca pelo terminal")
    p_search.add_argument("consulta")
    p_search.add_argument("--limite", type=int, default=5)
    p_search.add_argument("--modo", choices=["lexico", "vetorial", "hibrido"], default="hibrido")
    p_search.add_argument("--documento", help="restringe a busca a um documento (caminho, parcial ou nome)")
    p_search.set_defaults(func=_comando_search)

    p_avaliar = subs.add_parser("avaliar", help="roda o conjunto de avaliação")
    p_avaliar.add_argument("perguntas")
    p_avaliar.set_defaults(func=_comando_avaliar)

    p_serve = subs.add_parser("serve", help="sobe o servidor MCP (stdio por padrão, ou HTTP com --http)")
    p_serve.add_argument(
        "--http", action="store_true", help="expõe o servidor via HTTP (dá um link) em vez de stdio"
    )
    p_serve.add_argument("--host", default="127.0.0.1", help="apenas com --http")
    p_serve.add_argument("--porta", type=int, default=8765, help="apenas com --http")
    p_serve.add_argument(
        "--sem-aquecimento",
        action="store_true",
        help="não pré-carrega o modelo de embeddings no startup (a 1ª busca fica lenta)",
    )
    p_serve.set_defaults(func=_comando_serve)

    p_server_mcp = subs.add_parser(
        "server-mcp",
        help="sobe o servidor MCP via HTTP com o índice e os docs do projeto (use --local para a rede)",
    )
    p_server_mcp.add_argument(
        "--local",
        action="store_true",
        help=f"expõe na rede local (0.0.0.0:{PORTA_SERVER_MCP}); sem a flag, só esta máquina acessa",
    )
    p_server_mcp.set_defaults(func=_comando_server_mcp)

    p_stats = subs.add_parser("stats", help="documentos, chunks, modelo, data da ingestão")
    p_stats.set_defaults(func=_comando_stats)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = construir_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)
