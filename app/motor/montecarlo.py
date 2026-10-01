"""Simulacao de Monte Carlo sobre a projecao a varios anos.

Em vez de um unico resultado, corre milhares de cenarios com os pressupostos
mais incertos a variar, e devolve a distribuicao da TIR e do VAL e o peso de
cada variavel no resultado. As distribuicoes por defeito sao ilustrativas.
"""
import random
import statistics

from pydantic import BaseModel, Field

from app.motor.financeiro import Imovel, ResultadoRendimento, tir, van
from app.motor.projecao import PressupostosFinanciamento, PressupostosProjecao, fluxos_projecao


class PressupostosMonteCarlo(BaseModel):
    simulacoes: int = Field(2_000, ge=100, le=20_000)
    semente: int | None = Field(None, description="Fixar para resultados reprodutiveis")
    desvio_receita: float = Field(0.10, ge=0, le=1, description="Desvio-padrao relativo da renda/ADR e ocupacao")
    custos_min: float = Field(0.90, gt=0, description="Fator minimo sobre os custos operacionais")
    custos_max: float = Field(1.30, gt=0, description="Fator maximo sobre os custos operacionais")
    desvio_valorizacao: float = Field(0.03, ge=0, le=0.5, description="Desvio-padrao absoluto da valorizacao anual")
    desvio_taxa_juro: float = Field(0.01, ge=0, le=0.1, description="Desvio-padrao absoluto da TAN")
    obras_min: float = Field(0.95, gt=0, description="Fator minimo sobre o custo das obras")
    obras_max: float = Field(1.30, gt=0, description="Fator maximo sobre o custo das obras")


class Distribuicao(BaseModel):
    media: float
    p5: float
    p50: float
    p95: float


class ResultadoMonteCarlo(BaseModel):
    estrategia: str
    simulacoes: int
    tir: Distribuicao | None
    van: Distribuicao
    prob_prejuizo: float = Field(description="Probabilidade de o lucro total ser negativo")
    prob_van_negativo: float = Field(description="Probabilidade de render menos do que a taxa de desconto")
    sensibilidade: dict[str, float] = Field(description="Correlacao de cada variavel com o VAL (-1 a 1)")


def _percentil(ordenados: list[float], q: float) -> float:
    k = (len(ordenados) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(ordenados) - 1)
    return ordenados[lo] + (ordenados[hi] - ordenados[lo]) * (k - lo)


def _distribuicao(valores: list[float]) -> Distribuicao:
    v = sorted(valores)
    return Distribuicao(media=statistics.fmean(v), p5=_percentil(v, 0.05),
                        p50=_percentil(v, 0.5), p95=_percentil(v, 0.95))


def _correlacao(x: list[float], y: list[float]) -> float:
    try:
        return statistics.correlation(x, y)
    except statistics.StatisticsError:  # variavel constante
        return 0.0


def simular(im: Imovel, base: ResultadoRendimento, taxa_imposto: float, valor_inicial: float,
            p: PressupostosProjecao, fin: PressupostosFinanciamento | None,
            mc: PressupostosMonteCarlo) -> ResultadoMonteCarlo:
    rng = random.Random(mc.semente)
    entradas: dict[str, list[float]] = {k: [] for k in ("receita", "custos", "valorizacao", "taxa_juro", "obras")}
    tirs, vans, lucros = [], [], []

    for _ in range(mc.simulacoes):
        f_receita = max(0.0, rng.gauss(1.0, mc.desvio_receita))
        f_custos = rng.triangular(mc.custos_min, mc.custos_max, 1.0)
        valorizacao = rng.gauss(p.valorizacao_anual, mc.desvio_valorizacao)
        f_obras = rng.triangular(mc.obras_min, mc.obras_max, 1.0)
        taxa_juro = max(0.0, rng.gauss(fin.taxa_juro_anual, mc.desvio_taxa_juro)) if fin else 0.0

        im_s = im.model_copy(update={"capital_obras": im.capital_obras * f_obras})
        p_s = p.model_copy(update={"valorizacao_anual": valorizacao})
        fin_s = fin.model_copy(update={"taxa_juro_anual": taxa_juro}) if fin else None
        fluxos = fluxos_projecao(im_s, base, taxa_imposto, valor_inicial, p_s, fin_s,
                                 fator_receita=f_receita, fator_custos=f_custos)["fluxos"]

        for k, v in zip(entradas, (f_receita, f_custos, valorizacao, taxa_juro, f_obras)):
            entradas[k].append(v)
        vans.append(van(fluxos, p.taxa_desconto))
        lucros.append(sum(fluxos))
        t = tir(fluxos, iteracoes=50)
        if t is not None:
            tirs.append(t)

    n = mc.simulacoes
    return ResultadoMonteCarlo(
        estrategia=base.estrategia,
        simulacoes=n,
        tir=_distribuicao(tirs) if tirs else None,
        van=_distribuicao(vans),
        prob_prejuizo=sum(x < 0 for x in lucros) / n,
        prob_van_negativo=sum(x < 0 for x in vans) / n,
        sensibilidade={k: _correlacao(v, vans) for k, v in entradas.items() if not (k == "taxa_juro" and not fin)},
    )
