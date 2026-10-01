from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analise_completa():
    resp = client.post("/analise", json={
        "imovel": {"localizacao": "Lisboa, Arroios", "area_m2": 95, "tipologia": "T2",
                   "preco_aquisicao": 250000, "capital_obras": 35000, "vpt": 120000},
        "venda": {"preco_venda_m2": 2800},
        "arrendamento": {"renda_mensal": 1200},
        "alojamento_local": {"adr": 110},
    })
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["arrendamento"]["yield_liquida"] > corpo["alojamento_local"]["yield_liquida"]


def test_valida_area_negativa():
    resp = client.post("/analise", json={
        "imovel": {"localizacao": "x", "area_m2": -1, "tipologia": "T1", "preco_aquisicao": 1}})
    assert resp.status_code == 422


def test_analise_com_obras_e_valorizacao():
    resp = client.post("/analise", json={
        "imovel": {"localizacao": "Lisboa, Arroios", "area_m2": 95, "tipologia": "T2",
                   "preco_aquisicao": 250000, "capital_obras": 35000, "vpt": 120000},
        "venda": {"preco_venda_m2": 2800},
        "obras": {"nivel": "ligeira"},
        "venda_apos_obras": {"preco_venda_m2": 3600},
        "arrendamento_apos_obras": {"renda_mensal": 1400},
        "valorizacao": {"anos": 5},
    })
    assert resp.status_code == 200
    corpo = resp.json()
    for chave in ("remodelar_vender", "remodelar_arrendar", "manter"):
        assert corpo[chave] is not None
