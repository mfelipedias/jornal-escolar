# 29 — Clima: "Hoje na escola"

Camada: **MVP** (Could) · Fase 3 · Complexidade 1

## Objetivo

Um bloco pequeno e discreto na home com o tempo na escola agora. É um detalhe de "capa de jornal" que dá sensação de lugar e de atualidade. Não é uma funcionalidade central e não deve crescer.

## Fonte de dados

**Open-Meteo** (`https://api.open-meteo.com/v1/forecast`).

| Critério | Avaliação |
|---|---|
| Custo | Gratuito para uso não comercial, sem chave de API, sem cadastro |
| Limites | 10 mil requisições/dia; com cache de 30 minutos o jornal faz menos de 50/dia |
| Cobertura | Global, com modelos de alta resolução; dados horários e diários |
| Código aberto | Sim. O servidor de API pode ser **auto-hospedado** com Docker (`ghcr.io/open-meteo/open-meteo`), baixando os dados dos modelos meteorológicos |
| Privacidade | Nenhum dado do visitante é enviado; a chamada é feita pelo servidor do jornal |

Alternativas descartadas: OpenWeatherMap (exige chave, limites menores), INMET (API instável), WeatherAPI (comercial).

## Auto-hospedagem

Possível, mas **não recomendada agora**: o container precisa baixar e atualizar dezenas de GB de dados de modelos. A API pública atende. Fica como Evolução se a API pública for limitada ou descontinuada; a troca é uma variável de ambiente (`WEATHER_API_BASE`).

## Implementação

- Cidade: **Osasco, SP**. Coordenadas em `WEATHER_LAT = -23.5329` e `WEATHER_LON = -46.7918` (centro de Osasco; a previsão do Open-Meteo tem resolução de alguns quilômetros, então o ponto exato da escola não faz diferença). Fuso `America/Sao_Paulo`.
- Requisição: `current=temperature_2m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=America/Sao_Paulo&forecast_days=1`.
- Serviço `apps/core/weather.py` com `get_weather()` que consulta o cache do Django (30 minutos), chama a API com timeout de 3 segundos e, em falha, devolve `None` e mantém o último valor bom por até 6 horas.
- Mapeamento de `weather_code` (WMO) para rótulo em português e ícone em linha (SVG simples, monocromático): céu limpo, parcialmente nublado, nublado, nevoeiro, chuvisco, chuva, trovoada.
- Template tag `{% weather_widget %}` renderizado no bloco lateral da home, acima da Agenda.
- Sem JavaScript, sem chamada do navegador.

## Exibição

```
HOJE NA ESCOLA
☁ 23° · Nublado
mín 17° · máx 26° · chuva 40%
```

Texto em `text-meta`, cor `ink-2`; ícone 20px. Se `get_weather()` devolver `None`, o bloco não é renderizado. No celular aparece logo abaixo do destaque, em uma linha.

## O que não fazer

- Previsão de vários dias, mapas, alertas: não.
- "Pautas a partir do clima": não. Se um professor quiser escrever sobre a onda de calor, a pauta é dele.
- Widget na página de publicação: não, só na home.

## Histórico

- 2026-09-12: criado após decisão de incluir clima ([27](27-decisoes-pendentes-e-perguntas.md)).
