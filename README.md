# ImobiliarIA

Agente de apoio à decisão para investimento imobiliário em Portugal. Compara estratégias de exploração de um imóvel (vender, arrendar, Alojamento Local, remodelar, manter) com modelos financeiros determinísticos; o LLM apenas interpreta os resultados.

Destinado a investidores e particulares que querem perceber o potencial de um imóvel antes de falar com uma agência.

## Estado

v0.1: motor financeiro (venda, arrendamento, AL) exposto por uma API FastAPI.

## Correr localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload    # documentação em http://localhost:8000/docs
pytest
```

## Roteiro

1. Motor financeiro: remodelar e vender, remodelar e arrendar, manter; fluxos a N anos com financiamento (TIR, VAL, cash-on-cash).
2. Análise de risco: sensibilidade e Monte Carlo.
3. Modelo de dados em PostgreSQL + PostGIS.
4. Dados: INE, Banco de Portugal, Turismo de Portugal, OpenStreetMap.
5. Agente LLM com ferramentas sobre o motor.
6. Interface web e relatório.

> Os valores por defeito são pressupostos ilustrativos e configuráveis. Não constituem aconselhamento financeiro, fiscal ou jurídico.
