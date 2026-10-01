import pytest

from app.motor.financeiro import (
    CustosDetencao, Imovel, PressupostosAL, PressupostosArrendamento, PressupostosVenda,
    calcular_al, calcular_arrendamento, calcular_venda,
)

ARROIOS = Imovel(localizacao="Lisboa, Arroios", area_m2=95, tipologia="T2",
                 preco_aquisicao=250_000, capital_obras=35_000, vpt=120_000)


def test_arrendamento_yield_bruta():
    r = calcular_arrendamento(ARROIOS, PressupostosArrendamento(renda_mensal=1_200, meses_vazios_ano=0),
                              CustosDetencao())
    assert r.receita_bruta_anual == 14_400
    assert r.yield_bruta == pytest.approx(14_400 / 285_000)


def test_al_receita_do_enunciado():
    r = calcular_al(ARROIOS, PressupostosAL(adr=110), CustosDetencao())
    assert r.receita_bruta_anual == pytest.approx(21_450)
    assert r.yield_liquida < r.yield_bruta


def test_venda_sem_ganho_nao_paga_imposto():
    r = calcular_venda(ARROIOS, PressupostosVenda(preco_venda_m2=2_000))
    assert r.imposto == 0
    assert r.lucro < 0


from app.motor.financeiro import (  # noqa: E402
    PressupostosObras, PressupostosValorizacao, calcular_manter, calcular_remodelar_arrendar,
    calcular_remodelar_vender, tir,
)


def test_custo_obras_por_nivel():
    assert PressupostosObras(nivel="intermedia", margem_imprevistos=0).custo_total(95) == 57_000
    assert PressupostosObras(custo_m2=400, margem_imprevistos=0.1).custo_total(100) == pytest.approx(44_000)


def test_remodelar_vender_assinala_capital_insuficiente():
    r = calcular_remodelar_vender(ARROIOS, PressupostosObras(nivel="profunda"),
                                  PressupostosVenda(preco_venda_m2=4_000), CustosDetencao())
    assert r.excede_capital_obras
    assert r.investimento_total > ARROIOS.preco_aquisicao + r.custo_obras
    assert r.lucro == pytest.approx(r.venda.valor_liquido - r.investimento_total)


def test_remodelar_arrendar_usa_custo_obras():
    r = calcular_remodelar_arrendar(ARROIOS, PressupostosObras(nivel="ligeira", margem_imprevistos=0),
                                    PressupostosArrendamento(renda_mensal=1_400), CustosDetencao())
    assert r.investimento_total == 250_000 + 300 * 95


def test_tir_conhecida():
    assert tir([-100, 110]) == pytest.approx(0.10, abs=1e-6)
    assert tir([100, 100]) is None


def test_manter_cenarios_ordenados():
    r = calcular_manter(ARROIOS, 266_000, PressupostosValorizacao(), CustosDetencao())
    p, b, o = (r.cenarios[k].valor_final for k in ("pessimista", "base", "otimista"))
    assert p < b < o
