"""Ponto de entrada da CLI: ingest, search, stats, serve."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from docserver import chunk, extract, index

DOCS_FONTE_PADRAO = Path("docs-fonte")
DOCS_NORMALIZADO_PADRAO = Path("docs-normalizado")
INDICE_PADRAO = "data/indice.db"

MIN_CARACTERES_SUSPEITO = 20


def _deve_ignorar(caminho: Path) -> bool:
    return caminho.name.startswith(".") or caminho.name.startswith("~$")


def executar_ingestao(docs_fonte: Path, docs_normalizado: Path, caminho_indice: str) -> dict:
    inicio = time.perf_counter()
    relatorio = {
        "processados": 0,
        "chunks": 0,
        "ignorados": [],
        "falhas": [],
        "suspeitos": [],
    }

    todos_chunks: list[dict] = []
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

        relatorio["processados"] += 1
        conteudo = caminho_normalizado_arquivo.read_text(encoding="utf-8")
        _, corpo = extract.ler_front_matter(conteudo)
        if len(corpo.strip()) < MIN_CARACTERES_SUSPEITO:
            relatorio["suspeitos"].append(str(caminho))

        todos_chunks.extend(chunk.chunkar_arquivo(caminho_normalizado_arquivo))

    conexao = index.criar_indice(caminho_indice)
    index.reindexar(conexao, todos_chunks)
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
    return "\n".join(linhas)


def executar_busca(caminho_indice: str, consulta: str, limite: int = 5) -> list[dict]:
    conexao = index.criar_indice(caminho_indice)
    try:
        return index.buscar(conexao, consulta, limite)
    finally:
        conexao.close()


def formatar_resultados(resultados: list[dict]) -> str:
    if not resultados:
        return (
            "Nenhum resultado encontrado. Tente reformular a consulta "
            "(termo técnico exato ou pergunta em linguagem natural) "
            "ou use listar_documentos para ver o que existe."
        )
    blocos = []
    for i, r in enumerate(resultados, 1):
        blocos.append(f"[{i}] {r['caminho_origem']} › {r['secao']}\n{r['texto'][:300]}")
    return "\n\n".join(blocos)


def _carregar_perguntas(caminho_perguntas: Path) -> list[dict]:
    import yaml

    conteudo = Path(caminho_perguntas).read_text(encoding="utf-8")
    return yaml.safe_load(conteudo) or []


def _buscar_no_modo(conexao, modo: str, pergunta: str) -> list[dict]:
    if modo == "lexico":
        return index.buscar(conexao, pergunta, limite=5)
    raise ValueError(f"modo de busca ainda não implementado: {modo}")


def executar_avaliacao(
    caminho_perguntas: Path,
    caminho_indice: str,
    modos: tuple[str, ...] = ("lexico",),
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
                topo = _buscar_no_modo(conexao, modo, item["pergunta"])
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
    resultado = executar_avaliacao(Path(args.perguntas), args.indice)
    print(formatar_tabela_avaliacao(resultado))


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

    relatorio = executar_ingestao(docs_fonte, docs_normalizado, args.indice)
    print(formatar_relatorio(relatorio))


def _comando_search(args: argparse.Namespace) -> None:
    resultados = executar_busca(args.indice, args.consulta, args.limite)
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
    p_search.set_defaults(func=_comando_search)

    p_avaliar = subs.add_parser("avaliar", help="roda o conjunto de avaliação")
    p_avaliar.add_argument("perguntas")
    p_avaliar.set_defaults(func=_comando_avaliar)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = construir_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)
