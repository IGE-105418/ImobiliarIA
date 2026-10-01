import pytest

from app.motor.financeiro import (
    CustosDetencao, Imovel, PressupostosAL, PressupostosArrendamento, calcular_al,
    calcular_arrendamento, tir, van,
)
from app.motor.montecarlo import PressupostosMonteCarlo, simular
from app.motor.projecao import (
    PressupostosFinanciamento, PressupostosProjecao, plano_anual, prestacao_mensal, projetar,
)

ARROIOS = Imovel(localizacao="Lisboa, Arroios", area_m2=95, tipologia="T2",
                 preco_aquisicao=250_000, capital_obras=35_000, vpt=120_000)
BASE_ARR = calcular_arrendamento(ARROIOS, PressupostosArrendamento(renda_mensal=1_200), CustosDetencao())
VALOR = 2_800 * 95


def test_prestacao_sistema_frances():
    # 200.000 EUR a 30 anos e 3,5%: prestacao conhecida de ~898,09 EUR
    assert prestacao_mensal(200_000, 0.035, 30) == pytest.approx(898.09, abs=0.01)
    assert prestacao_mensal(120_000, 0.0, 10) == pytest.approx(1_000)


def test_plano_amortiza_tudo_no_prazo():
    plano = plano_anual(100_000, 0.04, 5, 6)
    assert sum(a for _, a, _ in plano) == pytest.approx(100_000)
    assert plano[4][2] == pytest.approx(0, abs=1e-6)
    assert plano[5] == (0.0, 0.0, 0.0)


def test_van_e_tir_coerentes():
    fluxos = [-1_000, 300, 400, 500]
    t = tir(fluxos)
    assert van(fluxos, t) == pytest.approx(0, abs=1e-6)


def test_projecao_sem_credito_usa_capital_total():
    r = projetar(ARROIOS, BASE_ARR, 0.25, VALOR, PressupostosProjecao(anos=10))
    assert r.capital_proprio == ARROIOS.investimento_total
    assert len(r.anos) == 10 and len(r.fluxos) == 11
    assert r.dscr_ano1 is None


def test_credito_reduz_capital_e_cria_alavancagem():
    fin = PressupostosFinanciamento(ltv=0.8)
    r = projetar(ARROIOS, BASE_ARR, 0.25, VALOR, PressupostosProjecao(), fin)
    assert r.montante_credito == 200_000
    assert r.capital_proprio == pytest.approx(85_000 + 200_000 * 0.006 + 1_000)
    assert r.prestacao_mensal == pytest.approx(898.09, abs=0.01)
    assert r.anos[-1].saldo_divida < 200_000


def test_juros_dedutiveis_reduzem_impostos():
    fin = PressupostosFinanciamento()
    sem = projetar(ARROIOS, BASE_ARR, 0.25, VALOR, PressupostosProjecao(), fin)
    com = projetar(ARROIOS, BASE_ARR, 0.25, VALOR, PressupostosProjecao(juros_dedutiveis=True), fin)
    assert com.anos[0].impostos < sem.anos[0].impostos


def test_monte_carlo_reprodutivel_e_coerente():
    base_al = calcular_al(ARROIOS, PressupostosAL(adr=110), CustosDetencao())
    mc = PressupostosMonteCarlo(simulacoes=300, semente=42)
    a = simular(ARROIOS, base_al, 0.20, VALOR, PressupostosProjecao(), PressupostosFinanciamento(), mc)
    b = simular(ARROIOS, base_al, 0.20, VALOR, PressupostosProjecao(), PressupostosFinanciamento(), mc)
    assert a == b
    assert a.van.p5 <= a.van.p50 <= a.van.p95
    assert 0 <= a.prob_prejuizo <= a.prob_van_negativo <= 1
    assert a.sensibilidade["valorizacao"] > 0 and a.sensibilidade["taxa_juro"] < 0


def test_monte_carlo_sem_credito_ignora_taxa_juro():
    r = simular(ARROIOS, BASE_ARR, 0.25, VALOR, PressupostosProjecao(), None,
                PressupostosMonteCarlo(simulacoes=100, semente=1))
    assert "taxa_juro" not in r.sensibilidade
