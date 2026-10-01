# ImobiliarIA

Agente de apoio à decisão para investimento imobiliário em Portugal. Compara estratégias de exploração de um imóvel (vender, arrendar, Alojamento Local, remodelar, manter) com modelos financeiros determinísticos; o LLM apenas interpreta os resultados.

Destinado a investidores e particulares que querem perceber o potencial de um imóvel antes de falar com uma agência.

## Estado

v0.2: motor financeiro exposto por uma API FastAPI (`POST /analise`).

- Seis estratégias: vender já, arrendar, Alojamento Local, remodelar e vender, remodelar e arrendar, manter.
- Crédito habitação (sistema francês, Imposto do Selo, seguros) e projeção de fluxos a N anos com TIR, VAL, cash-on-cash e DSCR.
- Simulação de Monte Carlo: distribuição da TIR e do VAL, probabilidade de prejuízo e peso de cada variável no resultado.

## Correr localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload    # documentação em http://localhost:8000/docs
pytest
```

## Roteiro

1. Sazonalidade mensal no AL e regras fiscais por regime.
2. Modelo de dados em PostgreSQL + PostGIS.
3. Dados: INE, Banco de Portugal, Turismo de Portugal, OpenStreetMap.
4. Agente LLM com ferramentas sobre o motor.
5. Interface web e relatório.

> Os valores por defeito são pressupostos ilustrativos e configuráveis. Não constituem aconselhamento financeiro, fiscal ou jurídico.
