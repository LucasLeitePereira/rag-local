"""Ponto de entrada da CLI: ingest, search, stats, serve."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from docserver import chunk, embed, extract, index

DOCS_FONTE_PADRAO = Path("docs-fonte")
DOCS_NORMALIZADO_PADRAO = Path("docs-normalizado")
INDICE_PADRAO = "data/indice.db"

MIN_CARACTERES_SUSPEITO = 20


def _deve_ignorar(caminho: Path) -> bool:
    return caminho.name.startswith(".") or caminho.name.startswith("~$")


def executar_ingestao(
    docs_fonte: Path,
    docs_normalizado: Path,
    caminho_indice: str,
    sem_embeddings: bool = False,
    embeddar_passagem_fn=None,
    nome_modelo: str | None = None,
) -> dict:
    inicio = time.perf_counter()
    relatorio = {
        "processados": 0,
        "chunks": 0,
        "ignorados": [],
        "falhas": [],
        "suspeitos": [],
        "removidos": [],
    }

    todos_chunks: list[dict] = []
    gerados: set[Path] = set()
    for caminho in sorted(p for p in docs_fonte.rglob("*") if p.is_file()):
        if _deve_ignorar(caminho):
            continue
        if caminho.suffix.lower() not in extract.EXTRATORES:
            relatorio["ignorados"].append(str(caminho))
            continue
        try:
            caminho_normalizado_arquivo = extract.normalizar(caminho, docs_fonte, docs_normalizado)
        except Exception as erro:
            relatorio["falhas"].append((str(caminho), str(erro)))
            continue

        gerados.add(caminho_normalizado_arquivo.resolve())
        relatorio["processados"] += 1
        conteudo = caminho_normalizado_arquivo.read_text(encoding="utf-8")
        _, corpo = extract.ler_front_matter(conteudo)
        if len(corpo.strip()) < MIN_CARACTERES_SUSPEITO:
            relatorio["suspeitos"].append(str(caminho))

        todos_chunks.extend(chunk.chunkar_arquivo(caminho_normalizado_arquivo))

    # arquivos normalizados cuja fonte original sumiu (foi apagada, renomeada, ou
    # passou a falhar na extração) não devem continuar servíveis nem aparecer na
    # listagem — é exatamente o que causava respostas misturando documentos.
    for orfao in sorted(p for p in docs_normalizado.rglob("*.md") if p.is_file()):
        if orfao.resolve() not in gerados:
            orfao.unlink()
            relatorio["removidos"].append(str(orfao))
    for pasta in sorted((p for p in docs_normalizado.rglob("*") if p.is_dir()), reverse=True):
        try:
            pasta.rmdir()
        except OSError:
            pass

    embeddings = None
    if not sem_embeddings and todos_chunks:
        calcular = embeddar_passagem_fn or embed.embeddar_passagem
        embeddings = [calcular(c) for c in todos_chunks]

    conexao = index.criar_indice(caminho_indice)
    index.reindexar(conexao, todos_chunks, embeddings=embeddings, nome_modelo=nome_modelo)
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
    return "\n".join(linhas)


def executar_busca(
    caminho_indice: str, consulta: str, limite: int = 5, modo: str = "hibrido", origem: str | None = None
) -> list[dict]:
    conexao = index.criar_indice(caminho_indice)
    try:
        if modo == "lexico":
            return index.buscar(conexao, consulta, limite, origem=origem)
        if modo == "vetorial":
            return index.buscar_vetorial(conexao, consulta, limite, origem=origem)
        return index.buscar_hibrido(conexao, consulta, limite, origem=origem)
    finally:
        conexao.close()


def formatar_resultados(resultados: list[dict]) -> str:
    if not resultados:
        return (
            "Nenhum trecho relevante encontrado. Tente reformular a consulta "
            "(termo técnico exato ou pergunta em linguagem natural), restrinja a um "
            "documento específico com o parâmetro documento, ou use listar_documentos "
            "para ver o que existe."
        )
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
    )


def _comando_ingest(args: argparse.Namespace) -> None:
    docs_fonte = Path(args.docs_fonte)
    docs_normalizado = Path(args.docs_normalizado)
    if args.limpar:
        import shutil

        shutil.rmtree(docs_normalizado, ignore_errors=True)
        docs_normalizado.mkdir(parents=True, exist_ok=True)
        Path(args.indice).unlink(missing_ok=True)

    Path(args.indice).parent.mkdir(parents=True, exist_ok=True)
    docs_normalizado.mkdir(parents=True, exist_ok=True)

    relatorio = executar_ingestao(
        docs_fonte, docs_normalizado, args.indice, sem_embeddings=args.sem_embeddings
    )
    print(formatar_relatorio(relatorio))


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

    resultados = executar_busca(args.indice, args.consulta, args.limite, modo=args.modo, origem=origem)
    print(formatar_resultados(resultados))


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docserver")
    parser.add_argument("--docs-fonte", default=str(DOCS_FONTE_PADRAO))
    parser.add_argument("--docs-normalizado", default=str(DOCS_NORMALIZADO_PADRAO))
    parser.add_argument("--indice", default=INDICE_PADRAO)
    subs = parser.add_subparsers(dest="comando", required=True)

    p_ingest = subs.add_parser("ingest", help="roda o pipeline completo de ingestão")
    p_ingest.add_argument("--limpar", action="store_true")
    p_ingest.add_argument("--sem-embeddings", action="store_true")
    p_ingest.set_defaults(func=_comando_ingest)

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
    p_serve.set_defaults(func=_comando_serve)

    p_stats = subs.add_parser("stats", help="documentos, chunks, modelo, data da ingestão")
    p_stats.set_defaults(func=_comando_stats)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = construir_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)
