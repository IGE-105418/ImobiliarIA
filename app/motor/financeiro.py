"""Motor financeiro deterministico do ImobiliarIA.

Compara estrategias de exploracao de um imovel (vender ja, arrendar a longo
prazo, Alojamento Local). Os valores por defeito sao PRESSUPOSTOS ilustrativos
e configuraveis, nao dados de mercado nem aconselhamento fiscal.
"""
from pydantic import BaseModel, Field


class Imovel(BaseModel):
    localizacao: str
    area_m2: float = Field(gt=0)
    tipologia: str
    preco_aquisicao: float = Field(ge=0)
    custos_aquisicao: float = Field(0, ge=0, description="IMT, Imposto do Selo, escritura")
    capital_obras: float = Field(0, ge=0)
    vpt: float = Field(0, ge=0, description="Valor patrimonial tributario (base do IMI)")

    @property
    def investimento_total(self) -> float:
        return self.preco_aquisicao + self.custos_aquisicao + self.capital_obras


class PressupostosVenda(BaseModel):
    preco_venda_m2: float = Field(gt=0)
    comissao_mediacao: float = Field(0.05 * 1.23, ge=0, le=1, description="5% + IVA")
    outros_custos: float = Field(1_500, ge=0)
    taxa_imposto_mais_valia: float = Field(0.14, ge=0, le=1, description="Taxa efetiva sobre o ganho (simplificacao)")


class CustosDetencao(BaseModel):
    taxa_imi: float = Field(0.003, ge=0, le=0.01)
    condominio_anual: float = Field(600, ge=0)
    seguro_anual: float = Field(250, ge=0)
    manutencao_pct_receita: float = Field(0.05, ge=0, le=1)


class PressupostosArrendamento(BaseModel):
    renda_mensal: float = Field(gt=0)
    meses_vazios_ano: float = Field(1, ge=0, le=12)
    taxa_irs: float = Field(0.25, ge=0, le=1, description="Taxa autonoma categoria F (pressuposto)")


class PressupostosAL(BaseModel):
    adr: float = Field(gt=0, description="Preco medio por noite")
    noites_disponiveis: int = Field(300, ge=0, le=366)
    ocupacao: float = Field(0.65, ge=0, le=1)
    comissao_plataforma: float = Field(0.15, ge=0, le=1)
    limpeza_por_estadia: float = Field(35, ge=0)
    noites_por_estadia: float = Field(3, gt=0)
    gestao_pct_receita: float = Field(0.20, ge=0, le=1)
    consumos_anuais: float = Field(2_400, ge=0)
    licenca_e_outros_anuais: float = Field(500, ge=0)
    taxa_imposto_efetiva: float = Field(0.20, ge=0, le=1, description="Simplificacao; depende do regime fiscal")


class ResultadoVenda(BaseModel):
    estrategia: str = "venda"
    preco_venda: float
    custos_venda: float
    imposto: float
    valor_liquido: float
    lucro: float


class ResultadoRendimento(BaseModel):
    estrategia: str
    receita_bruta_anual: float
    custos: dict[str, float]
    custos_anuais: float
    impostos_anuais: float
    rendimento_liquido_anual: float
    investimento_total: float
    yield_bruta: float
    yield_liquida: float


def _custos_fixos(im: Imovel, c: CustosDetencao, receita: float) -> dict[str, float]:
    return {
        "imi": im.vpt * c.taxa_imi,
        "condominio": c.condominio_anual,
        "seguro": c.seguro_anual,
        "manutencao": receita * c.manutencao_pct_receita,
    }


def _rendimento(estrategia: str, im: Imovel, receita: float, custos: dict[str, float],
                taxa_imposto: float) -> ResultadoRendimento:
    total = sum(custos.values())
    imposto = max(0.0, receita - total) * taxa_imposto
    liquido = receita - total - imposto
    inv = im.investimento_total
    return ResultadoRendimento(
        estrategia=estrategia,
        receita_bruta_anual=receita,
        custos=custos,
        custos_anuais=total,
        impostos_anuais=imposto,
        rendimento_liquido_anual=liquido,
        investimento_total=inv,
        yield_bruta=receita / inv if inv else 0.0,
        yield_liquida=liquido / inv if inv else 0.0,
    )


def calcular_venda(im: Imovel, p: PressupostosVenda) -> ResultadoVenda:
    preco = p.preco_venda_m2 * im.area_m2
    custos = preco * p.comissao_mediacao + p.outros_custos
    base = im.preco_aquisicao + im.custos_aquisicao
    imposto = max(0.0, preco - custos - base) * p.taxa_imposto_mais_valia
    liquido = preco - custos - imposto
    return ResultadoVenda(preco_venda=preco, custos_venda=custos, imposto=imposto,
                          valor_liquido=liquido, lucro=liquido - base)


def calcular_arrendamento(im: Imovel, p: PressupostosArrendamento,
                          c: CustosDetencao) -> ResultadoRendimento:
    receita = p.renda_mensal * (12 - p.meses_vazios_ano)
    return _rendimento("arrendamento", im, receita, _custos_fixos(im, c, receita), p.taxa_irs)


def calcular_al(im: Imovel, p: PressupostosAL, c: CustosDetencao) -> ResultadoRendimento:
    noites = p.noites_disponiveis * p.ocupacao
    receita = p.adr * noites
    custos = _custos_fixos(im, c, receita)
    custos.update({
        "plataforma": receita * p.comissao_plataforma,
        "limpeza": noites / p.noites_por_estadia * p.limpeza_por_estadia,
        "gestao": receita * p.gestao_pct_receita,
        "consumos": p.consumos_anuais,
        "licenca_e_outros": p.licenca_e_outros_anuais,
    })
    return _rendimento("alojamento_local", im, receita, custos, p.taxa_imposto_efetiva)


# --- Cenarios com obras e detencao -------------------------------------------

CUSTO_OBRAS_M2 = {"ligeira": 300.0, "intermedia": 600.0, "profunda": 1_000.0}


class PressupostosObras(BaseModel):
    nivel: str = Field("intermedia", pattern="^(ligeira|intermedia|profunda)$")
    custo_m2: float | None = Field(None, ge=0, description="Substitui o valor de referencia do nivel")
    meses_obra: int = Field(4, ge=0, le=36)
    margem_imprevistos: float = Field(0.10, ge=0, le=1)

    def custo_total(self, area_m2: float) -> float:
        base = self.custo_m2 if self.custo_m2 is not None else CUSTO_OBRAS_M2[self.nivel]
        return base * area_m2 * (1 + self.margem_imprevistos)


class PressupostosValorizacao(BaseModel):
    anos: int = Field(5, ge=1, le=30)
    pessimista: float = Field(-0.01, ge=-0.5, le=0.5)
    base: float = Field(0.03, ge=-0.5, le=0.5)
    otimista: float = Field(0.06, ge=-0.5, le=0.5)


class ResultadoRemodelarVender(BaseModel):
    estrategia: str = "remodelar_vender"
    custo_obras: float
    excede_capital_obras: bool
    custos_detencao_obra: float
    investimento_total: float
    venda: ResultadoVenda
    lucro: float
    retorno: float
    retorno_anualizado: float
    meses_totais: int


class CenarioManter(BaseModel):
    valorizacao_anual: float
    valor_final: float
    lucro_total: float
    tir: float | None


class ResultadoManter(BaseModel):
    estrategia: str = "manter"
    anos: int
    custos_detencao_anuais: float
    cenarios: dict[str, CenarioManter]


def van(fluxos: list[float], taxa: float) -> float:
    """Valor atual liquido dos fluxos anuais (fluxos[0] no ano 0)."""
    return sum(f / (1 + taxa) ** t for t, f in enumerate(fluxos))


def tir(fluxos: list[float], iteracoes: int = 80) -> float | None:
    """Taxa interna de rentabilidade anual por bissecao; None se nao existir."""
    lo, hi = -0.99, 1.0
    v_lo, v_hi = van(fluxos, lo), van(fluxos, hi)
    if v_lo * v_hi > 0:
        return None
    for _ in range(iteracoes):
        mid = (lo + hi) / 2
        v_mid = van(fluxos, mid)
        if v_lo * v_mid <= 0:
            hi = mid
        else:
            lo, v_lo = mid, v_mid
    return (lo + hi) / 2


def _custos_detencao_anuais(im: Imovel, c: CustosDetencao) -> float:
    return im.vpt * c.taxa_imi + c.condominio_anual + c.seguro_anual


def calcular_remodelar_vender(im: Imovel, obras: PressupostosObras, venda: PressupostosVenda,
                              c: CustosDetencao, meses_para_vender: int = 3) -> ResultadoRemodelarVender:
    """`venda.preco_venda_m2` deve ser o preco esperado DEPOIS das obras."""
    custo_obras = obras.custo_total(im.area_m2)
    meses = obras.meses_obra + meses_para_vender
    detencao = _custos_detencao_anuais(im, c) * meses / 12
    base = im.preco_aquisicao + im.custos_aquisicao + custo_obras + detencao
    preco = venda.preco_venda_m2 * im.area_m2
    custos_venda = preco * venda.comissao_mediacao + venda.outros_custos
    # Obras documentadas sao dedutiveis a mais-valia (simplificacao).
    imposto = max(0.0, preco - custos_venda - base) * venda.taxa_imposto_mais_valia
    liquido = preco - custos_venda - imposto
    lucro = liquido - base
    retorno = lucro / base
    anual = (1 + retorno) ** (12 / meses) - 1 if meses and retorno > -1 else retorno
    return ResultadoRemodelarVender(
        custo_obras=custo_obras,
        excede_capital_obras=custo_obras > im.capital_obras,
        custos_detencao_obra=detencao,
        investimento_total=base,
        venda=ResultadoVenda(estrategia="venda_apos_obras", preco_venda=preco, custos_venda=custos_venda,
                             imposto=imposto, valor_liquido=liquido, lucro=lucro),
        lucro=lucro,
        retorno=retorno,
        retorno_anualizado=anual,
        meses_totais=meses,
    )


def calcular_remodelar_arrendar(im: Imovel, obras: PressupostosObras, p: PressupostosArrendamento,
                                c: CustosDetencao) -> ResultadoRendimento:
    """`p.renda_mensal` deve ser a renda esperada DEPOIS das obras."""
    im_obras = im.model_copy(update={"capital_obras": obras.custo_total(im.area_m2)})
    r = calcular_arrendamento(im_obras, p, c)
    return r.model_copy(update={"estrategia": "remodelar_arrendar"})


def calcular_manter(im: Imovel, valor_atual: float, v: PressupostosValorizacao,
                    c: CustosDetencao) -> ResultadoManter:
    """Manter o imovel devoluto e vender no fim do horizonte (sem rendimento)."""
    detencao = _custos_detencao_anuais(im, c)
    inv = im.preco_aquisicao + im.custos_aquisicao
    cenarios = {}
    for nome in ("pessimista", "base", "otimista"):
        taxa = getattr(v, nome)
        final = valor_atual * (1 + taxa) ** v.anos
        fluxos = [-inv] + [-detencao] * v.anos
        fluxos[-1] += final
        cenarios[nome] = CenarioManter(valorizacao_anual=taxa, valor_final=final,
                                       lucro_total=sum(fluxos), tir=tir(fluxos))
    return ResultadoManter(anos=v.anos, custos_detencao_anuais=detencao, cenarios=cenarios)
