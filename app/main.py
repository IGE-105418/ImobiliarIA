from fastapi import FastAPI
from pydantic import BaseModel

from app.motor.financeiro import (
    CustosDetencao, Imovel, PressupostosAL, PressupostosArrendamento, PressupostosObras,
    PressupostosValorizacao, PressupostosVenda, ResultadoManter, ResultadoRemodelarVender,
    ResultadoRendimento, ResultadoVenda, calcular_al, calcular_arrendamento, calcular_manter,
    calcular_remodelar_arrendar, calcular_remodelar_vender, calcular_venda,
)
from app.motor.montecarlo import PressupostosMonteCarlo, ResultadoMonteCarlo, simular
from app.motor.projecao import PressupostosFinanciamento, PressupostosProjecao, ResultadoProjecao, projetar

app = FastAPI(
    title="ImobiliarIA",
    description="Analise de estrategias de investimento imobiliario em Portugal.",
    version="0.1.0",
)


class PedidoAnalise(BaseModel):
    imovel: Imovel
    venda: PressupostosVenda | None = None
    arrendamento: PressupostosArrendamento | None = None
    alojamento_local: PressupostosAL | None = None
    obras: PressupostosObras | None = None
    venda_apos_obras: PressupostosVenda | None = None
    arrendamento_apos_obras: PressupostosArrendamento | None = None
    valorizacao: PressupostosValorizacao | None = None
    financiamento: PressupostosFinanciamento | None = None
    projecao: PressupostosProjecao | None = None
    monte_carlo: PressupostosMonteCarlo | None = None
    custos: CustosDetencao = CustosDetencao()


class RespostaAnalise(BaseModel):
    venda: ResultadoVenda | None = None
    arrendamento: ResultadoRendimento | None = None
    alojamento_local: ResultadoRendimento | None = None
    remodelar_vender: ResultadoRemodelarVender | None = None
    remodelar_arrendar: ResultadoRendimento | None = None
    manter: ResultadoManter | None = None
    projecao: dict[str, ResultadoProjecao] | None = None
    risco: dict[str, ResultadoMonteCarlo] | None = None
    aviso: str = ("Resultados baseados em pressupostos configuraveis. Nao constituem "
                  "aconselhamento financeiro, fiscal ou juridico.")


@app.get("/saude")
def saude() -> dict:
    return {"estado": "ok"}


@app.post("/analise", response_model=RespostaAnalise)
def analisar(pedido: PedidoAnalise) -> RespostaAnalise:
    im, c, obras = pedido.imovel, pedido.custos, pedido.obras
    resposta = RespostaAnalise(
        venda=calcular_venda(im, pedido.venda) if pedido.venda else None,
        arrendamento=calcular_arrendamento(im, pedido.arrendamento, c) if pedido.arrendamento else None,
        alojamento_local=calcular_al(im, pedido.alojamento_local, c) if pedido.alojamento_local else None,
    )
    if obras and pedido.venda_apos_obras:
        resposta.remodelar_vender = calcular_remodelar_vender(im, obras, pedido.venda_apos_obras, c)
    if obras and pedido.arrendamento_apos_obras:
        resposta.remodelar_arrendar = calcular_remodelar_arrendar(im, obras, pedido.arrendamento_apos_obras, c)
    if pedido.valorizacao and pedido.venda:
        valor_atual = pedido.venda.preco_venda_m2 * im.area_m2
        resposta.manter = calcular_manter(im, valor_atual, pedido.valorizacao, c)
    # Projecao a varios anos e Monte Carlo para as estrategias de rendimento.
    rendimentos = []
    if resposta.arrendamento:
        rendimentos.append((resposta.arrendamento, pedido.arrendamento.taxa_irs))
    if resposta.alojamento_local:
        rendimentos.append((resposta.alojamento_local, pedido.alojamento_local.taxa_imposto_efetiva))
    if rendimentos and (pedido.projecao or pedido.monte_carlo):
        proj = pedido.projecao or PressupostosProjecao()
        valor_atual = pedido.venda.preco_venda_m2 * im.area_m2 if pedido.venda else im.preco_aquisicao
        fin = pedido.financiamento
        resposta.projecao = {b.estrategia: projetar(im, b, taxa, valor_atual, proj, fin) for b, taxa in rendimentos}
        if pedido.monte_carlo:
            resposta.risco = {b.estrategia: simular(im, b, taxa, valor_atual, proj, fin, pedido.monte_carlo)
                              for b, taxa in rendimentos}
    return resposta
