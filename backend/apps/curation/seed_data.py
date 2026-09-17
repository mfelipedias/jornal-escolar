"""Fontes iniciais sugeridas em docs/21 (o admin confirma, ajusta a confiança ou desativa).

Endereços conferidos em 2026-09-17. Ficaram de fora, por não terem feed público funcionando
nesse dia: Agência FAPESP, Nova Escola, MEC, IBGE e Instituto Butantan; Ciência Hoje e Fiocruz
têm feed, mas parado há anos (últimas notícias de 2017 e 2025). Detalhes em docs/21, Histórico.
"""

SOURCES: list[dict] = [
    {
        "name": "Agência Brasil — Últimas notícias",
        "feed_url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",
        "site_url": "https://agenciabrasil.ebc.com.br/",
        "trust_level": 5,
    },
    {
        "name": "Agência Brasil — Educação",
        "feed_url": "https://agenciabrasil.ebc.com.br/rss/educacao/feed.xml",
        "site_url": "https://agenciabrasil.ebc.com.br/educacao",
        "trust_level": 5,
    },
    {
        "name": "Pesquisa FAPESP",
        "feed_url": "https://revistapesquisa.fapesp.br/feed/",
        "site_url": "https://revistapesquisa.fapesp.br/",
        "trust_level": 5,
    },
    {
        "name": "Jornal da USP",
        "feed_url": "https://jornal.usp.br/feed/",
        "site_url": "https://jornal.usp.br/",
        "trust_level": 5,
    },
    {
        "name": "Agência Bori",
        "feed_url": "https://abori.com.br/feed/",
        "site_url": "https://abori.com.br/",
        "trust_level": 5,
    },
    {
        "name": "INPE",
        "feed_url": "https://www.gov.br/inpe/pt-br/assuntos/ultimas-noticias/RSS",
        "site_url": "https://www.gov.br/inpe/",
        "trust_level": 5,
    },
    {
        "name": "Revista Galileu",
        "feed_url": "https://revistagalileu.globo.com/rss/galileu",
        "site_url": "https://revistagalileu.globo.com/",
        "trust_level": 4,
    },
    {
        "name": "Porvir",
        "feed_url": "https://porvir.org/feed/",
        "site_url": "https://porvir.org/",
        "trust_level": 4,
    },
    {
        "name": "BBC News Brasil",
        "feed_url": "https://feeds.bbci.co.uk/portuguese/rss.xml",
        "site_url": "https://www.bbc.com/portuguese",
        "trust_level": 4,
    },
    {
        "name": "Nexo Jornal",
        "feed_url": "https://www.nexojornal.com.br/rss.xml",
        "site_url": "https://www.nexojornal.com.br/",
        "trust_level": 4,
    },
    {
        "name": "Olhar Digital",
        "feed_url": "https://olhardigital.com.br/feed/",
        "site_url": "https://olhardigital.com.br/",
        "trust_level": 3,
    },
    {
        "name": "Tecnoblog",
        "feed_url": "https://tecnoblog.net/feed/",
        "site_url": "https://tecnoblog.net/",
        "trust_level": 3,
    },
    {
        "name": "Canaltech",
        "feed_url": "https://canaltech.com.br/rss/",
        "site_url": "https://canaltech.com.br/",
        "trust_level": 3,
    },
    {
        "name": "Nature",
        "feed_url": "https://www.nature.com/nature.rss",
        "site_url": "https://www.nature.com/",
        "trust_level": 5,
        "language": "en",
    },
    {
        "name": "MIT Technology Review",
        "feed_url": "https://www.technologyreview.com/feed/",
        "site_url": "https://www.technologyreview.com/",
        "trust_level": 5,
        "language": "en",
    },
]
