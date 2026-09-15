"""Ponto de entrada da CLI: ingest, watch, search, stats, serve."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

from docserver import chunk, embed, extract, index, rerank

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


def _sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _motivo_reconstrucao(conexao, sem_embeddings: bool, nome_modelo: str | None) -> str | None:
    """Por que a ingestão precisa reprocessar todos os arquivos, ou None se pode ser
    incremental."""
    if index.verificar_esquema(conexao):
        return f"índice em formato antigo (versão {index.versao_esquema(conexao)})"
    if sem_embeddings:
        return None
    modelo_atual = nome_modelo or embed.NOME_MODELO
    modelo_salvo = index.modelo_registrado(conexao)
    if modelo_salvo is not None and modelo_salvo != modelo_atual:
        return f"modelo de embeddings trocado ({modelo_salvo} → {modelo_atual})"
    if index.chunks_sem_vetor(conexao) > 0:
        return "há chunks sem embeddings"
    return None


def executar_ingestao(
    docs_fonte: Path,
    docs_normalizado: Path,
    caminho_indice: str,
    sem_embeddings: bool = False,
    embeddar_passagem_fn=None,
    nome_modelo: str | None = None,
    forcar: bool = False,
) -> dict:
    """Pipeline incremental. Só extrai, divide e gera embeddings dos arquivos novos ou
    alterados (sha256 diferente do registrado no índice); os inalterados ficam como
    estão, e os que sumiram da fonte (ou passaram a falhar na extração) saem do índice.
    Reprocessa tudo quando o índice está em formato antigo, o modelo de embeddings
    mudou ou há chunks sem vetor numa ingestão com embeddings.

    Levanta `ErroIngestao` — sem tocar no índice — se `docs_fonte` não existe, ou (a
    menos que `forcar`) se não há nenhum arquivo suportado ou se o resultado
    esvaziaria um índice que tinha conteúdo."""
    validar_docs_fonte(docs_fonte)
    inicio = time.perf_counter()
    relatorio = {
        "processados": 0,
        "novos": [],
        "alterados": [],
        "inalterados": 0,
        "documentos_removidos": [],
        "chunks": 0,
        "chunks_novos": 0,
        "ignorados": [],
        "falhas": [],
        "suspeitos": [],
        "removidos": [],
        "preservados": [],
        "reconstrucao": None,
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

    conexao = index.criar_indice(caminho_indice)
    try:
        relatorio["reconstrucao"] = _motivo_reconstrucao(conexao, sem_embeddings, nome_modelo)
        registrados = {} if relatorio["reconstrucao"] else index.arquivos_registrados(conexao)
        chunks_atuais = conexao.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

        novos_chunks: list[dict] = []
        registros: list[dict] = []
        mantidas: set[str] = set()
        chunks_mantidos = 0
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

            origem = extract.origem_para(caminho, docs_fonte)
            sha256 = _sha256(caminho)
            registro = registrados.get(origem)
            if registro and registro["sha256"] == sha256 and destino.is_file():
                destinos[chave] = caminho
                gerados.add(destino.resolve())
                mantidas.add(origem)
                chunks_mantidos += registro["chunks"]
                relatorio["inalterados"] += 1
                continue

            try:
                caminho_normalizado_arquivo = extract.normalizar(caminho, docs_fonte, docs_normalizado)
            except Exception as erro:
                relatorio["falhas"].append((str(caminho), str(erro)))
                continue

            destinos[chave] = caminho
            gerados.add(caminho_normalizado_arquivo.resolve())
            relatorio["processados"] += 1
            relatorio["alterados" if registro else "novos"].append(str(caminho))
            meta, corpo = extract.ler_front_matter(caminho_normalizado_arquivo.read_text(encoding="utf-8"))
            if len(extract.remover_marcadores_pagina(corpo)) < MIN_CARACTERES_SUSPEITO:
                relatorio["suspeitos"].append(str(caminho))

            chunks_arquivo = chunk.chunkar_arquivo(caminho_normalizado_arquivo, docs_normalizado)
            novos_chunks.extend(chunks_arquivo)
            registros.append(
                {
                    "caminho_origem": origem,
                    "caminho_normalizado": caminho_normalizado_arquivo.resolve()
                    .relative_to(Path(docs_normalizado).resolve())
                    .as_posix(),
                    "sha256": sha256,
                    "tamanho": caminho.stat().st_size,
                    "chunks": len(chunks_arquivo),
                    "extrator": meta.get("extrator"),
                    "ingerido_em": meta.get("ingerido_em"),
                }
            )

        total_final = chunks_mantidos + len(novos_chunks)
        if total_final == 0 and not forcar and chunks_atuais > 0:
            raise ErroIngestao(
                "a ingestão não gerou nenhum chunk e substituiria um índice que tem conteúdo. "
                "Índice e docs-normalizado foram mantidos; use --forcar se a intenção é mesmo esvaziá-lo."
            )

        reprocessadas = {r["caminho_origem"] for r in registros}
        # origens no índice que não foram mantidas nem reprocessadas: fonte apagada,
        # renomeada ou que passou a falhar na extração
        relatorio["documentos_removidos"] = sorted(index.origens_indexadas(conexao) - mantidas - reprocessadas)

        embeddings = None
        if not sem_embeddings:
            if embeddar_passagem_fn is not None:
                embeddings = [embeddar_passagem_fn(c) for c in novos_chunks]
            else:
                embeddings = embed.embeddar_passagens(novos_chunks) if novos_chunks else []

        relatorio["camada_vetorial_removida"] = index.atualizar_indice(
            conexao,
            novos_chunks,
            registros,
            relatorio["documentos_removidos"],
            embeddings=embeddings,
            nome_modelo=nome_modelo,
            reconstruir=bool(relatorio["reconstrucao"]),
        )
    finally:
        conexao.close()

    # arquivos normalizados cuja fonte original sumiu (foi apagada, renomeada, ou
    # passou a falhar na extração) não devem continuar servíveis nem aparecer na
    # listagem — é exatamente o que causava respostas misturando documentos. Só
    # depois do commit: se a gravação falhar, o índice anterior ainda os referencia.
    relatorio["removidos"], relatorio["preservados"] = _remover_gerados(docs_normalizado, gerados)

    relatorio["chunks"] = total_final
    relatorio["chunks_novos"] = len(novos_chunks)
    relatorio["tempo"] = time.perf_counter() - inicio
    return relatorio


def formatar_relatorio(relatorio: dict) -> str:
    linhas = [
        f"Ingestão concluída em {relatorio['tempo']:.1f}s",
        "",
        f"  Novos:                   {len(relatorio['novos'])}",
        f"  Alterados:               {len(relatorio['alterados'])}",
        f"  Inalterados (pulados):   {relatorio['inalterados']}",
        f"  Removidos do índice:     {len(relatorio['documentos_removidos'])}",
        f"  Chunks indexados:        {relatorio['chunks']} ({relatorio['chunks_novos']} novos)",
        f"  Ignorados (formato):     {len(relatorio['ignorados'])}",
        f"  Falhas de extração:      {len(relatorio['falhas'])}",
        f"  Suspeitos (texto vazio): {len(relatorio['suspeitos'])}",
        f"  Removidos (órfãos):      {len(relatorio['removidos'])}",
    ]
    if relatorio.get("reconstrucao"):
        linhas.append("")
        linhas.append(f"Índice reconstruído do zero: {relatorio['reconstrucao']}.")
    for rotulo, chave in (("Novos", "novos"), ("Alterados", "alterados")):
        if relatorio[chave]:
            linhas.append("")
            linhas.append(f"{rotulo}:")
            linhas.extend(f"  + {caminho}" for caminho in relatorio[chave])
    if relatorio["documentos_removidos"]:
        linhas.append("")
        linhas.append("Removidos do índice:")
        linhas.extend(f"  - {origem}" for origem in relatorio["documentos_removidos"])
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
    reranquear: bool = True,
) -> list[dict]:
    conexao = index.criar_indice(caminho_indice)
    try:
        index.exigir_esquema_atual(conexao)
        if modo == "lexico":
            return index.buscar(conexao, consulta, limite, origem=origem)
        if modo == "vetorial":
            return index.buscar_vetorial(conexao, consulta, limite, origem=origem)
        return index.buscar_hibrido(
            conexao, consulta, limite, origem=origem, avisos=avisos, reranquear_fn=None if reranquear else False
        )
    finally:
        conexao.close()


def formatar_paginas(resultado: dict) -> str | None:
    """`p. N` ou `pp. N–M` para chunks de PDF; None para os demais formatos."""
    inicio, fim = resultado.get("pagina_inicio"), resultado.get("pagina_fim")
    if inicio is None:
        return None
    if fim is None or fim == inicio:
        return f"p. {inicio}"
    return f"pp. {inicio}–{fim}"


def formatar_resultados(resultados: list[dict]) -> str:
    if not resultados:
        return MENSAGEM_SEM_RESULTADOS
    blocos = []
    for i, r in enumerate(resultados, 1):
        paginas = formatar_paginas(r)
        sufixo = f" ({paginas})" if paginas else ""
        blocos.append(f"[{i}] {r['caminho_origem']} › {r['secao']}{sufixo}\n{r['texto'][:300]}")
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
    if modo == "hibrido" or modo.startswith("hibrido+"):
        # `hibrido` puro é a linha de base sem reranker; `hibrido+<reranker>` liga um
        chave = modo.partition("+")[2]
        reranquear_fn = (lambda texto, itens: rerank.pontuar(texto, itens, chave)) if chave else False
        return index.buscar_hibrido(
            conexao,
            pergunta,
            limite=5,
            embeddar_consulta_fn=embeddar_consulta_fn,
            nome_modelo=nome_modelo,
            dimensao=dimensao,
            reranquear_fn=reranquear_fn,
        )
    raise ValueError(f"modo de busca desconhecido: {modo}")


TOP_K_AVALIACAO = 5


def _normalizar_trecho(texto: str) -> str:
    """Forma usada para comparar `trecho` com o texto dos chunks: sem acento, sem
    caixa e com espaços colapsados (a extração de PDF quebra linhas no meio da frase)."""
    return " ".join(index._sem_acentos(texto).split())


def _metricas_vazias() -> dict:
    return {
        "positivas": 0,
        "hit1": 0,
        "hit5": 0,
        "rr": 0.0,
        "com_trecho": 0,
        "trecho5": 0,
        "negativas": 0,
        "negativas_vazias": 0,
        "consultas": 0,
        "tempo_s": 0.0,
    }


def _pontuar_resposta(metricas: dict, item: dict, topo: list[dict]) -> None:
    esperado = item.get("esperado")
    if esperado is None:
        metricas["negativas"] += 1
        if not topo:
            metricas["negativas_vazias"] += 1
        return

    metricas["positivas"] += 1
    posicoes = [i for i, r in enumerate(topo[:TOP_K_AVALIACAO], 1) if r["caminho_origem"] == esperado]
    if posicoes:
        metricas["hit5"] += 1
        metricas["rr"] += 1 / posicoes[0]
        if posicoes[0] == 1:
            metricas["hit1"] += 1

    trecho = item.get("trecho")
    if trecho:
        metricas["com_trecho"] += 1
        alvo = _normalizar_trecho(trecho)
        if any(
            r["caminho_origem"] == esperado and alvo in _normalizar_trecho(r["texto"])
            for r in topo[:TOP_K_AVALIACAO]
        ):
            metricas["trecho5"] += 1


def validar_perguntas(caminho_perguntas: Path, caminho_indice: str) -> list[str]:
    """Confere o conjunto de avaliação contra o índice: cada `esperado` precisa estar
    indexado e cada `trecho` precisa existir em algum chunk desse documento — senão a
    pergunta mede um erro de digitação, não a busca. Devolve os problemas encontrados."""
    perguntas = _carregar_perguntas(caminho_perguntas)
    problemas = []
    conexao = index.criar_indice(caminho_indice)
    try:
        for numero, item in enumerate(perguntas, 1):
            rotulo = f"#{numero} \"{item.get('pergunta', '')}\""
            if not item.get("pergunta") or item.get("perfil") not in ("tecnico", "natural"):
                problemas.append(f"{rotulo}: precisa de 'pergunta' e de 'perfil' (tecnico ou natural)")
                continue
            esperado = item.get("esperado")
            if esperado is None:
                if item.get("trecho"):
                    problemas.append(f"{rotulo}: pergunta negativa (esperado: null) não pode ter 'trecho'")
                continue
            textos = [
                linha[0]
                for linha in conexao.execute("SELECT texto FROM chunks WHERE caminho_origem = ?", (esperado,))
            ]
            if not textos:
                problemas.append(f"{rotulo}: documento esperado não está no índice: {esperado}")
                continue
            trecho = item.get("trecho")
            if trecho:
                alvo = _normalizar_trecho(trecho)
                if not any(alvo in _normalizar_trecho(texto) for texto in textos):
                    problemas.append(f"{rotulo}: trecho não encontrado em nenhum chunk de {esperado}: {trecho!r}")
    finally:
        conexao.close()
    return problemas


def executar_avaliacao(
    caminho_perguntas: Path,
    caminho_indice: str,
    modos: tuple[str, ...] = ("lexico",),
    embeddar_consulta_fn=None,
    nome_modelo: str | None = None,
    dimensao: int | None = None,
) -> dict:
    """Roda cada pergunta do conjunto de avaliação em cada modo e acumula, por modo e
    perfil, os contadores de `_metricas_vazias` (hit@1, hit@5, MRR@5, trecho@5,
    negativas sem resultado e tempo). As taxas são calculadas em `taxas_avaliacao`."""
    perguntas = _carregar_perguntas(caminho_perguntas)
    resultado: dict[str, dict[str, dict]] = {modo: {} for modo in modos}

    conexao = index.criar_indice(caminho_indice)
    try:
        for item in perguntas:
            for modo in modos:
                metricas = resultado[modo].setdefault(item["perfil"], _metricas_vazias())
                inicio = time.perf_counter()
                topo = _buscar_no_modo(
                    conexao,
                    modo,
                    item["pergunta"],
                    embeddar_consulta_fn=embeddar_consulta_fn,
                    nome_modelo=nome_modelo,
                    dimensao=dimensao,
                )
                metricas["tempo_s"] += time.perf_counter() - inicio
                metricas["consultas"] += 1
                _pontuar_resposta(metricas, item, topo)
    finally:
        conexao.close()

    return resultado


def _somar_metricas(por_perfil: dict) -> dict:
    total = _metricas_vazias()
    for metricas in por_perfil.values():
        for chave, valor in metricas.items():
            total[chave] += valor
    return total


def taxas_avaliacao(metricas: dict) -> dict:
    """Converte os contadores em taxas (0–1) e latência média; `None` quando não há
    pergunta daquele tipo."""

    def _razao(parte, todo):
        return parte / todo if todo else None

    return {
        "hit1": _razao(metricas["hit1"], metricas["positivas"]),
        "hit5": _razao(metricas["hit5"], metricas["positivas"]),
        "mrr5": _razao(metricas["rr"], metricas["positivas"]),
        "trecho5": _razao(metricas["trecho5"], metricas["com_trecho"]),
        "negativas_vazias": _razao(metricas["negativas_vazias"], metricas["negativas"]),
        "ms_por_consulta": _razao(metricas["tempo_s"] * 1000, metricas["consultas"]),
    }


def formatar_tabela_avaliacao(resultado: dict) -> str:
    """Uma linha por modo × perfil, mais a linha "geral" de cada modo. `neg vazio` é a
    fração das perguntas sem resposta que voltaram sem resultado (só modos com corte
    de relevância chegam a devolver vazio)."""
    colunas = [
        ("hit@1", "hit1", "pct"),
        ("hit@5", "hit5", "pct"),
        ("MRR@5", "mrr5", "dec"),
        ("trecho@5", "trecho5", "pct"),
        ("neg vazio", "negativas_vazias", "pct"),
        ("ms/cons", "ms_por_consulta", "ms"),
    ]

    def _celula(valor, formato):
        if valor is None:
            return "—"
        if formato == "pct":
            return f"{valor:.0%}"
        if formato == "dec":
            return f"{valor:.2f}"
        return f"{valor:.0f}"

    linhas_dados = []
    for modo, por_perfil in resultado.items():
        grupos = [(perfil, por_perfil[perfil]) for perfil in sorted(por_perfil)]
        grupos.append(("geral", _somar_metricas(por_perfil)))
        for perfil, metricas in grupos:
            taxas = taxas_avaliacao(metricas)
            detalhe = f"{metricas['hit5']}/{metricas['positivas']}"
            linhas_dados.append(
                [modo, perfil, detalhe, *(_celula(taxas[chave], formato) for _, chave, formato in colunas)]
            )

    cabecalho = ["modo", "perfil", "acertos", *(titulo for titulo, _, _ in colunas)]
    larguras = [max(len(str(linha[i])) for linha in [cabecalho, *linhas_dados]) for i in range(len(cabecalho))]

    def _linha(celulas):
        esquerda = [f"{celulas[i]:<{larguras[i]}}" for i in range(2)]
        direita = [f"{celulas[i]:>{larguras[i]}}" for i in range(2, len(celulas))]
        return "  ".join(esquerda + direita).rstrip()

    return "\n".join([_linha(cabecalho), *(_linha(linha) for linha in linhas_dados)])


def _comando_avaliar(args: argparse.Namespace) -> None:
    if not Path(args.indice).exists():
        print(f"Índice não encontrado em {args.indice}. Rode 'docserver ingest' primeiro.")
        raise SystemExit(1)

    problemas = validar_perguntas(Path(args.perguntas), args.indice)
    if problemas:
        print("Conjunto de avaliação inválido:")
        for problema in problemas:
            print(f"- {problema}")
        raise SystemExit(1)
    if args.validar:
        print("Conjunto de avaliação válido.")
        return

    conexao = index.criar_indice(args.indice)
    try:
        mensagem_esquema = index.verificar_esquema(conexao)
        tem_vetores = index._tabela_vetorial_existe(conexao)
    finally:
        conexao.close()
    if mensagem_esquema:
        print(f"Índice indisponível: {mensagem_esquema}")
        raise SystemExit(1)
    modos = ("lexico", "vetorial", "hibrido") if tem_vetores else ("lexico", "hibrido")
    rerankers = _rerankers_da_avaliacao(args.rerankers)
    modos += tuple(f"hibrido+{chave}" for chave in rerankers)
    if tem_vetores:
        # carrega o modelo antes de medir: senão a 1ª consulta vetorial carrega a
        # latência do import do torch e dos pesos
        embed.embeddar_consulta("aquecimento")
    for chave in rerankers:
        try:
            rerank.obter_modelo(chave)
        except Exception as erro:  # noqa: BLE001
            print(f"Reranker {chave} indisponível: {erro}")
            raise SystemExit(1)

    resultado = executar_avaliacao(Path(args.perguntas), args.indice, modos=modos)
    print(formatar_tabela_avaliacao(resultado))
    if not tem_vetores:
        print("\nÍndice sem camada vetorial: modo vetorial omitido e híbrido equivale ao léxico com corte.")

    if args.min_hit5 is not None:
        # a meta vale para a busca como o servidor a faz: com o reranker configurado
        configurado = rerank.reranker_configurado()
        modo_meta = f"hibrido+{configurado}" if configurado in rerankers else "hibrido"
        hit5 = taxas_avaliacao(_somar_metricas(resultado[modo_meta]))["hit5"]
        if hit5 is None or hit5 < args.min_hit5:
            atual = "—" if hit5 is None else f"{hit5:.0%}"
            print(f"\nhit@5 do modo {modo_meta} ({atual}) abaixo da meta de {args.min_hit5:.0%}.")
            raise SystemExit(1)


def _rerankers_da_avaliacao(opcao: str | None) -> list[str]:
    """`--rerankers a,b` (ou `nenhum`); sem a opção, o reranker configurado, se houver."""
    if opcao is None:
        configurado = rerank.reranker_configurado()
        return [configurado] if configurado else []
    return [c.strip() for c in opcao.split(",") if c.strip() and c.strip().lower() not in rerank.DESLIGADO]


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
    conexao = index.criar_indice(args.indice)
    try:
        mensagem_esquema = index.verificar_esquema(conexao)
        candidatos = index.resolver_origem(conexao, args.documento) if args.documento and not mensagem_esquema else []
    finally:
        conexao.close()
    if mensagem_esquema:
        print(f"Índice indisponível: {mensagem_esquema}")
        sys.exit(1)
    if args.documento:
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
        args.indice,
        args.consulta,
        args.limite,
        modo=args.modo,
        origem=origem,
        avisos=avisos,
        reranquear=not args.sem_rerank,
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
    p_search.add_argument(
        "--sem-rerank", action="store_true", help="não reordena os resultados híbridos com o reranker"
    )
    p_search.set_defaults(func=_comando_search)

    p_avaliar = subs.add_parser("avaliar", help="roda o conjunto de avaliação")
    p_avaliar.add_argument("perguntas")
    p_avaliar.add_argument(
        "--validar",
        action="store_true",
        help="só confere o conjunto (documentos esperados indexados e trechos existentes), sem rodar a busca",
    )
    p_avaliar.add_argument(
        "--min-hit5",
        type=float,
        default=None,
        metavar="TAXA",
        help="sai com código 1 se o hit@5 geral do modo híbrido (com o reranker configurado) ficar abaixo desta taxa (0–1)",
    )
    p_avaliar.add_argument(
        "--rerankers",
        default=None,
        metavar="LISTA",
        help=f"rerankers comparados, separados por vírgula ({', '.join(rerank.MODELOS_RERANKER)}) ou 'nenhum'; "
        "padrão: o da env RERANKER",
    )
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
