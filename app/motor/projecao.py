"""Credito habitacao e projecao de fluxos de caixa a varios anos.

Os valores por defeito sao PRESSUPOSTOS ilustrativos e configuraveis, nao
condicoes de mercado nem aconselhamento financeiro ou fiscal.
"""
from pydantic import BaseModel, Field

from app.motor.financeiro import Imovel, ResultadoRendimento, tir, van

# Custos que acompanham a receita (crescem com as rendas); os restantes crescem com a inflacao.
CUSTOS_PROPORCIONAIS = {"manutencao", "plataforma", "gestao", "limpeza"}


class PressupostosFinanciamento(BaseModel):
    ltv: float = Field(0.8, ge=0, le=1, description="Parte do preco de aquisicao financiada")
    taxa_juro_anual: float = Field(0.035, ge=0, le=0.2, description="TAN (Euribor + spread), pressuposto")
    prazo_anos: int = Field(30, ge=1, le=40)
    imposto_selo_credito: float = Field(0.006, ge=0, le=0.05, description="Imposto do Selo sobre o capital")
    comissoes_iniciais: float = Field(1_000, ge=0, description="Avaliacao, abertura de processo")
    seguros_credito_anuais: float = Field(300, ge=0, description="Seguro de vida associado ao credito")

    def montante(self, im: Imovel) -> float:
        return im.preco_aquisicao * self.ltv

    def custos_iniciais(self, im: Imovel) -> float:
        return self.montante(im) * self.imposto_selo_credito + self.comissoes_iniciais


class PressupostosProjecao(BaseModel):
    anos: int = Field(10, ge=1, le=30)
    crescimento_rendas: float = Field(0.02, ge=-0.2, le=0.2)
    inflacao_custos: float = Field(0.02, ge=-0.2, le=0.2)
    valorizacao_anual: float = Field(0.03, ge=-0.5, le=0.5)
    taxa_desconto: float = Field(0.06, ge=0, le=0.5, description="Rentabilidade minima exigida para o VAL")
    custos_venda_final: float = Field(0.05 * 1.23, ge=0, le=1)
    taxa_imposto_mais_valia: float = Field(0.14, ge=0, le=1)
    juros_dedutiveis: bool = Field(
        False, description="Na categoria F os juros do credito em principio nao sao dedutiveis; confirmar com contabilista")


class AnoProjecao(BaseModel):
    ano: int
    receita: float
    custos: float
    juros: float
    amortizacao: float
    impostos: float
    fluxo_caixa: float
    saldo_divida: float


class ResultadoProjecao(BaseModel):
    estrategia: str
    capital_proprio: float
    montante_credito: float
    prestacao_mensal: float
    anos: list[AnoProjecao]
    valor_final_imovel: float
    venda_final_liquida: float
    fluxos: list[float]
    lucro_total: float
    tir: float | None
    van: float
    cash_on_cash_ano1: float
    dscr_ano1: float | None


def prestacao_mensal(montante: float, taxa_anual: float, prazo_anos: int) -> float:
    """Prestacao constante (sistema frances)."""
    n, i = prazo_anos * 12, taxa_anual / 12
    if montante <= 0:
        return 0.0
    if i == 0:
        return montante / n
    return montante * i / (1 - (1 + i) ** -n)


def plano_anual(montante: float, taxa_anual: float, prazo_anos: int, anos: int) -> list[tuple[float, float, float]]:
    """(juros, amortizacao, saldo no fim do ano) para cada um dos primeiros `anos`."""
    pmt, i, saldo = prestacao_mensal(montante, taxa_anual, prazo_anos), taxa_anual / 12, montante
    plano = []
    for ano in range(anos):
        juros = amort = 0.0
        for _ in range(12):
            if ano >= prazo_anos or saldo <= 0:
                break
            j = saldo * i
            a = min(pmt - j, saldo)
            juros, amort, saldo = juros + j, amort + a, saldo - a
        saldo = 0.0 if saldo < 0.01 else saldo  # residuo de arredondamento
        plano.append((juros, amort, saldo))
    return plano


def fluxos_projecao(im: Imovel, base: ResultadoRendimento, taxa_imposto: float, valor_inicial: float,
                    p: PressupostosProjecao, fin: PressupostosFinanciamento | None,
                    fator_receita: float = 1.0, fator_custos: float = 1.0) -> dict:
    """Nucleo numerico da projecao (sem objetos pydantic, para ser rapido no Monte Carlo)."""
    montante = fin.montante(im) if fin else 0.0
    plano = plano_anual(montante, fin.taxa_juro_anual, fin.prazo_anos, p.anos) if fin else [(0.0, 0.0, 0.0)] * p.anos
    capital = im.investimento_total - montante + (fin.custos_iniciais(im) if fin else 0.0)
    seguros = fin.seguros_credito_anuais if fin else 0.0

    fluxos, anos = [-capital], []
    for t in range(1, p.anos + 1):
        g_rendas = (1 + p.crescimento_rendas) ** (t - 1)
        g_inflacao = (1 + p.inflacao_custos) ** (t - 1)
        receita = base.receita_bruta_anual * fator_receita * g_rendas
        custos = fator_custos * sum(
            v * fator_receita * g_rendas if k in CUSTOS_PROPORCIONAIS else v * g_inflacao
            for k, v in base.custos.items())
        juros, amort, saldo = plano[t - 1]
        dedutivel = juros if p.juros_dedutiveis else 0.0
        impostos = max(0.0, receita - custos - dedutivel) * taxa_imposto
        fluxo = receita - custos - impostos - juros - amort - seguros
        anos.append((t, receita, custos, juros, amort, impostos, fluxo, saldo))
        fluxos.append(fluxo)

    valor_final = valor_inicial * (1 + p.valorizacao_anual) ** p.anos
    custos_venda = valor_final * p.custos_venda_final
    ganho = valor_final - custos_venda - im.investimento_total
    liquida = valor_final - custos_venda - max(0.0, ganho) * p.taxa_imposto_mais_valia - plano[-1][2]
    fluxos[-1] += liquida
    return {"capital": capital, "montante": montante, "anos": anos, "fluxos": fluxos,
            "valor_final": valor_final, "liquida": liquida}


def projetar(im: Imovel, base: ResultadoRendimento, taxa_imposto: float, valor_inicial: float,
             p: PressupostosProjecao, fin: PressupostosFinanciamento | None = None) -> ResultadoProjecao:
    r = fluxos_projecao(im, base, taxa_imposto, valor_inicial, p, fin)
    anos = [AnoProjecao(ano=a[0], receita=a[1], custos=a[2], juros=a[3], amortizacao=a[4],
                        impostos=a[5], fluxo_caixa=a[6], saldo_divida=a[7]) for a in r["anos"]]
    a1 = anos[0]
    servico_divida = a1.juros + a1.amortizacao
    return ResultadoProjecao(
        estrategia=base.estrategia,
        capital_proprio=r["capital"],
        montante_credito=r["montante"],
        prestacao_mensal=prestacao_mensal(r["montante"], fin.taxa_juro_anual, fin.prazo_anos) if fin else 0.0,
        anos=anos,
        valor_final_imovel=r["valor_final"],
        venda_final_liquida=r["liquida"],
        fluxos=r["fluxos"],
        lucro_total=sum(r["fluxos"]),
        tir=tir(r["fluxos"]),
        van=van(r["fluxos"], p.taxa_desconto),
        cash_on_cash_ano1=a1.fluxo_caixa / r["capital"] if r["capital"] else 0.0,
        dscr_ano1=(a1.receita - a1.custos) / servico_divida if servico_divida else None,
    )
