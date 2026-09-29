"""Conteúdo fictício do seed de demonstração (E28). Só para desenvolvimento e apresentações.

Pessoas, turmas e fatos são inventados. Nomes de alunos seguem a política padrão (primeiro
nome e inicial). Nada aqui cita o nome da escola. Textos usam o formato de
core.services.text_to_document: "## " para subtítulo e "- " para lista.
"""

# Domínio reservado dos e-mails fictícios: é assim que o seed encontra o que criou.
DEMO_EMAIL_DOMAIN = "demo.jornal.local"

STAFF = [
    {
        "key": "carla",
        "full_name": "Carla Mendes Rocha",
        "display_name": "Carla Mendes",
        "role": "staff",
        "staff_kind": "teacher",
        "headline": "Professora de Física",
        "bio": "Gosto de transformar a sala em laboratório. Coordeno o clube de astronomia e a "
        "Feira de Ciências.",
        "disciplines": ["Física", "Química"],
        "topics": ["Astronomia", "Energia", "Divulgação científica"],
        "since_year": 2016,
        "education": [
            {"degree": "Licenciatura em Física", "institution": "Universidade", "year": 2012}
        ],
        "avatar": True,
    },
    {
        "key": "joao",
        "full_name": "João Batista Lima",
        "display_name": "",
        "role": "editor",
        "staff_kind": "coordinator",
        "headline": "Coordenação pedagógica",
        "bio": "Acompanho os projetos das turmas e ajudo a equipe a publicar no jornal.",
        "disciplines": ["Gestão e Coordenação"],
        "topics": ["ENEM e Vestibular", "Profissões"],
        "since_year": 2012,
        "education": [],
        "avatar": True,
    },
    {
        "key": "patricia",
        "full_name": "Patrícia Nogueira Alves",
        "display_name": "Patrícia Nogueira",
        "role": "staff",
        "staff_kind": "teacher",
        "headline": "Professora de Língua Portuguesa",
        "bio": "Leitora de tudo, de bula a romance russo. Organizo o sarau e as oficinas de "
        "escrita.",
        "disciplines": ["Língua Portuguesa", "Leitura e Produção de Texto"],
        "topics": ["Literatura", "Teatro"],
        "since_year": 2018,
        "education": [
            {"degree": "Letras", "institution": "Universidade", "year": 2010},
            {"degree": "Mestrado em Literatura", "institution": "Universidade", "year": 2015},
        ],
        "avatar": False,
    },
    {
        "key": "renato",
        "full_name": "Renato Figueiredo",
        "display_name": "",
        "role": "staff",
        "staff_kind": "teacher",
        "headline": "Professor de Matemática",
        "bio": "Acredito que dá para aprender matemática com a conta de luz e o preço do lanche.",
        "disciplines": ["Matemática", "Educação Financeira"],
        "topics": ["Matemática no cotidiano", "Ciência de Dados", "Educação Financeira"],
        "since_year": 2020,
        "education": [],
        "avatar": True,
    },
    {
        "key": "luciana",
        "full_name": "Luciana Freitas",
        "display_name": "",
        "role": "staff",
        "staff_kind": "teacher",
        "headline": "Professora de História",
        "bio": "Pesquiso memória e patrimônio do bairro com as turmas do ensino médio.",
        "disciplines": ["História", "Sociologia"],
        "topics": ["História do Brasil", "Cultura Afro-brasileira e Indígena", "Direitos Humanos"],
        "since_year": 2014,
        "education": [],
        "avatar": False,
    },
    {
        "key": "andre",
        "full_name": "André Takeshi Oliveira",
        "display_name": "André Takeshi",
        "role": "staff",
        "staff_kind": "teacher",
        "headline": "Professor de Tecnologia e Inovação",
        "bio": "Robótica com sucata, programação desplugada e muita paciência com Arduino.",
        "disciplines": ["Tecnologia e Inovação", "Projeto de Vida"],
        "topics": ["Robótica", "Programação", "Inteligência Artificial"],
        "since_year": 2021,
        "education": [],
        "avatar": True,
    },
    {
        "key": "sonia",
        "full_name": "Sônia Ribeiro",
        "display_name": "",
        "role": "staff",
        "staff_kind": "librarian",
        "headline": "Sala de leitura",
        "bio": "Cuido dos livros e das indicações de leitura. Pode pedir sugestão!",
        "disciplines": ["Sala de Leitura"],
        "topics": ["Literatura"],
        "since_year": 2010,
        "education": [],
        "avatar": False,
    },
    {
        "key": "marcelo",
        "full_name": "Marcelo Duarte",
        "display_name": "",
        "role": "staff",
        "staff_kind": "monitor",
        "headline": "Monitor escolar",
        "bio": "Apoio os eventos, o grêmio e os campeonatos do intervalo.",
        "disciplines": ["Monitoria", "Grêmio Estudantil"],
        "topics": ["Esportes"],
        "since_year": 2023,
        "education": [],
        "avatar": False,
    },
]

# status: "published" (padrão), "draft", "archived", "in_review" ou "changes_requested".
# Em revisão: reviewer (chave da pessoa), review_note, reviewer_may_publish e, para
# "changes_requested", changes_note (o que o revisor pediu).
# event: (dias a partir de hoje, hora, local). days_ago: quando foi publicada.
# featured: posição no destaque da home (precisa de capa).
ARTICLES = [
    {
        "author": "carla",
        "title": "Feira de Ciências reúne 40 projetos sobre energia",
        "subtitle": "Turmas da 2ª série montaram fornos solares, carregadores e cataventos com "
        "material reciclado e mediram quanto cada um produz.",
        "type": "Reportagem",
        "disciplines": ["Física", "Química"],
        "topics": ["Energia", "Meio Ambiente"],
        "days_ago": 2,
        "cover": True,
        "cover_alt": "Ilustração em tons de verde com círculos que lembram um painel solar.",
        "featured": 1,
        "reads": 312,
        "students": [("Rafael S.", "2ª série B"), ("Ana Clara M.", "2ª série B")],
        "coauthors": ["joao"],
        "sources": [
            {
                "title": "Atlas de energia solar",
                "url": "https://example.org/atlas-solar",
                "publisher": "Instituto de exemplo",
            }
        ],
        "body": """\
A quadra virou laboratório na última sexta-feira. Quarenta grupos apresentaram projetos sobre \
geração e economia de energia, e cada um precisava mostrar números: quanto o equipamento \
produz, quanto custou e o que daria para melhorar.

## Do papelão ao forno solar

O projeto mais visitado foi um forno solar feito com caixa de pizza, papel-alumínio e plástico \
transparente. Em duas horas de sol, a temperatura interna passou de 70 °C, o suficiente para \
derreter queijo num pão.

“A gente errou o ângulo três vezes antes de acertar”, contou Rafael S., da 2ª série B. O grupo \
anotou a temperatura a cada dez minutos e montou um gráfico ao vivo para os visitantes.

## O que os jurados observaram

- Se o grupo explicava o fenômeno físico por trás do projeto.
- Se as medidas foram repetidas e registradas.
- Se o material era reaproveitado ou de baixo custo.

Os três projetos mais bem avaliados vão representar a escola na mostra regional, em novembro.""",
    },
    {
        "author": "patricia",
        "title": "Sarau de primavera abre inscrições para leitura no palco",
        "subtitle": "Poemas, contos curtos e música: qualquer aluno pode se inscrever até sexta.",
        "type": "Evento",
        "disciplines": ["Língua Portuguesa", "Arte"],
        "topics": ["Literatura", "Música"],
        "days_ago": 3,
        "event": (9, 19, "Pátio coberto"),
        "cover": True,
        "cover_alt": "Ilustração em tons de coral com formas que lembram um palco iluminado.",
        "featured": 2,
        "reads": 198,
        "body": """\
O sarau de primavera volta ao pátio coberto com microfone aberto para quem quiser ler, \
recitar ou cantar. Cada apresentação tem até cinco minutos.

## Como se inscrever

- Procure a professora Patrícia ou a sala de leitura até sexta-feira.
- Informe o título do texto ou da música e se vai precisar de violão ou teclado.
- Textos autorais são muito bem-vindos.

As famílias estão convidadas. A entrada é livre e o grêmio vai vender pipoca para ajudar na \
formatura.""",
    },
    {
        "author": "renato",
        "title": "O que a conta de luz revela sobre o consumo da escola",
        "subtitle": "Um ano de faturas em gráficos, e onde dá para economizar sem apagar a luz "
        "da sala.",
        "type": "Divulgação científica",
        "disciplines": ["Matemática", "Educação Financeira"],
        "topics": ["Ciência de Dados", "Energia", "Matemática no cotidiano"],
        "days_ago": 5,
        "cover": True,
        "cover_alt": "Ilustração em tons de azul com barras que lembram um gráfico.",
        "featured": 3,
        "reads": 241,
        "students": [("Beatriz L.", "3ª série A")],
        "body": """\
A turma da 3ª série A reuniu doze meses de contas de energia e transformou tudo em planilha. \
O resultado surpreendeu: o maior consumo não é em janeiro, é em junho.

## Por que junho?

Nos meses frios, os dias são mais curtos e as luzes ficam acesas por mais tempo, inclusive nos \
corredores. Além disso, é o período com mais atividades à noite.

## Três ideias que saíram da análise

- Trocar as lâmpadas dos corredores por modelos de LED com sensor de presença.
- Desligar os bebedouros refrigerados nos fins de semana.
- Criar uma “patrulha da tomada” no fim de cada período.

“Só a troca dos corredores pagaria o investimento em menos de dois anos”, calculou Beatriz L. \
A proposta foi entregue à direção.""",
    },
    {
        "author": "luciana",
        "title": "Entrevista: a feira livre que ajudou a formar o bairro",
        "subtitle": "Dona Célia vende verduras na mesma rua há 38 anos e contou às turmas como "
        "tudo mudou.",
        "type": "Entrevista",
        "disciplines": ["História", "Sociologia"],
        "topics": ["História do Brasil"],
        "days_ago": 7,
        "cover": True,
        "cover_alt": "Ilustração em tons de âmbar com faixas que lembram toldos de feira.",
        "reads": 156,
        "students": [("Gustavo R.", "1ª série C"), ("Larissa P.", "1ª série C")],
        "body": """\
Para o projeto de memória do bairro, a 1ª série C entrevistou feirantes, moradores antigos e \
comerciantes. A conversa com dona Célia (nome fictício) foi a mais comentada.

## Quando a senhora começou na feira?

Em 1987. A rua ainda era de terra e a feira era o único lugar para comprar verdura fresca. \
Vinha gente de longe.

## O que mudou de lá para cá?

Chegaram os mercados, o asfalto e muita gente nova. Mas o freguês antigo continua vindo, e \
agora traz os netos.

## Que conselho a senhora dá para os jovens?

Conversem com os mais velhos. Tem muita história que não está em livro nenhum.""",
    },
    {
        "author": "andre",
        "title": "Robô feito com sucata vence desafio de seguir linha",
        "subtitle": "Equipe usou peças de impressora velha e um Arduino para completar o "
        "percurso em 41 segundos.",
        "type": "Notícia",
        "disciplines": ["Tecnologia e Inovação", "Física"],
        "topics": ["Robótica", "Programação"],
        "days_ago": 9,
        "cover": True,
        "cover_alt": "Ilustração em tons de violeta com linhas e círculos que lembram um circuito.",
        "reads": 287,
        "students": [("Pedro H.", "2ª série A"), ("Yasmin T.", "2ª série A")],
        "guests": [("Clube de Robótica", "montagem")],
        "body": """\
O clube de robótica voltou do desafio intermunicipal com o primeiro lugar na categoria seguidor \
de linha. O robô, apelidado de “Teimoso”, foi montado com motores de uma impressora que ia para \
o lixo.

O percurso tinha curvas fechadas e um cruzamento. O Teimoso completou em 41 segundos, sem sair \
da linha nenhuma vez.

“Reescrevemos o código na noite anterior porque ele se perdia no cruzamento”, contou Yasmin T. \
A equipe agora quer ensinar a montagem para as turmas do 1º ano.""",
    },
    {
        "author": "sonia",
        "title": "Cinco livros curtos para ler nas férias",
        "subtitle": "Indicações da sala de leitura para quem quer começar e terminar um livro "
        "em poucos dias.",
        "type": "Resenha",
        "disciplines": ["Sala de Leitura", "Leitura e Produção de Texto"],
        "topics": ["Literatura"],
        "days_ago": 12,
        "cover": False,
        "reads": 133,
        "body": """\
Livro curto não é livro menor. Separamos cinco títulos que cabem numa semana de férias e rendem \
boas conversas.

- Um romance de formação sobre um garoto que decide mudar de cidade.
- Uma coletânea de contos de terror para ler de dia.
- Uma graphic novel sobre imigração e família.
- Um livro de crônicas sobre futebol de várzea.
- Poemas curtos para ler em voz alta.

Todos estão disponíveis para empréstimo. Basta levar a carteirinha até a sala de leitura.""",
    },
    {
        "author": "marcelo",
        "title": "Interclasse de vôlei começa na próxima semana",
        "subtitle": "Doze equipes inscritas, jogos no intervalo e final aberta para as famílias.",
        "type": "Evento",
        "disciplines": ["Educação Física", "Grêmio Estudantil"],
        "topics": ["Esportes"],
        "days_ago": 4,
        "event": (5, 10, "Quadra poliesportiva"),
        "cover": False,
        "reads": 174,
        "coauthors": ["joao"],
        "body": """\
O campeonato interclasse de vôlei tem doze equipes inscritas, entre mistas e femininas. Os jogos \
acontecem no intervalo, com sets de 15 pontos.

## Regras principais

- Cada turma pode inscrever até dez jogadores.
- É obrigatório ter pelo menos duas meninas em quadra nas equipes mistas.
- Atrasos de mais de cinco minutos contam como W.O.

A tabela completa está no mural do grêmio.""",
    },
    {
        "author": "joao",
        "title": "Plantão de dúvidas para o ENEM às quintas",
        "subtitle": "Professores de todas as áreas atendem na biblioteca até a véspera da prova.",
        "type": "Evento",
        "disciplines": ["Orientação de Estudos"],
        "topics": ["ENEM e Vestibular"],
        "days_ago": 6,
        "event": (12, 15, "Sala de leitura"),
        "cover": False,
        "reads": 221,
        "body": """\
Todas as quintas-feiras, das 15h às 17h, professores de todas as áreas ficam na sala de leitura \
para tirar dúvidas de quem vai prestar o ENEM.

Não é preciso agendar. Leve a questão, a redação ou o simulado que quiser revisar.""",
    },
    {
        "author": "carla",
        "title": "Noite de observação do céu com telescópio",
        "subtitle": "Clube de astronomia convida a comunidade para ver a Lua e Saturno.",
        "type": "Evento",
        "disciplines": ["Física", "Geografia"],
        "topics": ["Astronomia"],
        "days_ago": 1,
        "event": (26, 19, "Pátio externo"),
        "cover": True,
        "cover_alt": "Ilustração em tons de verde-escuro com pontos que lembram estrelas.",
        "reads": 89,
        "body": """\
Se o céu colaborar, vai dar para ver as crateras da Lua e os anéis de Saturno. O clube de \
astronomia leva dois telescópios e um binóculo grande para o pátio.

Em caso de chuva, a atividade vira uma sessão de planetário com projetor na sala de vídeo.""",
    },
    {
        "author": "patricia",
        "title": "Poema: “O ônibus das seis”",
        "subtitle": "Produção da oficina de escrita sobre o caminho até a escola.",
        "type": "Produção de aluno",
        "disciplines": ["Leitura e Produção de Texto"],
        "topics": ["Literatura"],
        "days_ago": 15,
        "cover": False,
        "reads": 145,
        "students": [("Mariana F.", "9º ano B")],
        "body": """\
O ônibus das seis
chega cheio de sono,
de mochila e de pressa.

Na janela embaçada
eu escrevo meu nome
e o dia apaga.

Mas amanhã, às seis,
eu escrevo de novo.""",
    },
    {
        "author": "luciana",
        "title": "Horta da escola colhe a primeira safra de alface",
        "subtitle": "Projeto interdisciplinar já rendeu 60 pés de alface e uma aula sobre "
        "compostagem.",
        "type": "Projeto",
        "disciplines": ["Biologia", "Geografia"],
        "topics": ["Meio Ambiente", "Alimentação"],
        "days_ago": 18,
        "cover": True,
        "cover_alt": "Ilustração em tons de petróleo com formas arredondadas que lembram folhas.",
        "reads": 203,
        "coauthors": ["carla"],
        "students": [("Enzo G.", "1ª série A")],
        "body": """\
A horta ao lado da quadra completou três meses e entregou a primeira colheita: 60 pés de alface, \
que foram para a merenda.

## Etapas do projeto

- Análise do solo nas aulas de Biologia.
- Mapa de sol e sombra do terreno em Geografia.
- Composteira com restos da cozinha, cuidada pelas turmas do 1º ano.

A próxima plantação será de cenoura e cheiro-verde.""",
    },
    {
        "author": "andre",
        "title": "Inteligência artificial na lição de casa: pode ou não pode?",
        "subtitle": "Um professor de tecnologia explica quando a ferramenta ajuda e quando "
        "atrapalha o aprendizado.",
        "type": "Artigo de opinião",
        "disciplines": ["Tecnologia e Inovação", "Filosofia"],
        "topics": ["Inteligência Artificial"],
        "days_ago": 21,
        "cover": False,
        "reads": 402,
        "body": """\
Proibir não resolve, e liberar sem conversa também não. Ferramentas de inteligência artificial \
já estão no celular dos alunos, e a pergunta útil é outra: o que você aprendeu fazendo a tarefa?

Quando a ferramenta explica um conceito de outro jeito, ou aponta um erro no seu código, ela \
funciona como um colega paciente. Quando entrega a resposta pronta, ela tira de você justamente \
a parte que faz aprender.

Minha sugestão para as turmas: use, mas conte como usou. Mostre a pergunta que fez e o que \
mudou no seu texto depois.""",
    },
    {
        "author": "renato",
        "title": "Curiosidade: por que o pão de queijo cresce no forno?",
        "subtitle": "A resposta envolve água, vapor e um amido muito especial.",
        "type": "Curiosidade",
        "disciplines": ["Química"],
        "topics": ["Alimentação", "Divulgação científica"],
        "days_ago": 25,
        "cover": False,
        "reads": 118,
        "body": """\
O pão de queijo não leva fermento. Quem faz a massa crescer é a água, que vira vapor dentro da \
massa, e o polvilho, um amido que forma uma rede elástica capaz de segurar esse vapor.

Por isso a massa precisa ser escaldada: o calor prepara o amido para esticar sem rasgar.""",
    },
    {
        "author": "joao",
        "title": "Grêmio estudantil toma posse com nova diretoria",
        "subtitle": "Chapa eleita promete reformar o espaço de convivência e criar uma rádio "
        "no intervalo.",
        "type": "Notícia",
        "disciplines": ["Grêmio Estudantil", "Sociologia"],
        "topics": ["Política e Cidadania"],
        "days_ago": 30,
        "cover": True,
        "cover_alt": "Ilustração em tons de petróleo com faixas diagonais.",
        "reads": 267,
        "guests": [("Grêmio Estudantil", "")],
        "body": """\
A nova diretoria do grêmio tomou posse em cerimônia no auditório, com a presença das turmas e \
da coordenação. A eleição teve participação de 78% dos alunos.

As primeiras propostas são reformar os bancos do espaço de convivência e testar uma rádio no \
intervalo, com música e recados das turmas.""",
    },
    {
        "author": "carla",
        "title": "Mostra de fotografia científica encerra com exposição no corredor",
        "subtitle": "Fotos de insetos, cristais e gotas de água feitas com celular.",
        "type": "Evento",
        "disciplines": ["Biologia", "Arte"],
        "topics": ["Fotografia", "Divulgação científica"],
        "days_ago": 35,
        "event": (-20, 14, "Corredor do bloco B"),
        "cover": False,
        "reads": 97,
        "body": """\
A mostra de fotografia científica terminou com uma exposição de 30 imagens no corredor do \
bloco B. Todas foram feitas com celular e uma lente de aumento barata.

As fotos continuam expostas até o fim do bimestre.""",
    },
    {
        "author": "sonia",
        "title": "Resenha: o livro que fez a turma discutir amizade",
        "subtitle": "Clube de leitura do 8º ano escolheu um romance juvenil e a conversa "
        "rendeu duas aulas.",
        "type": "Resenha",
        "disciplines": ["Sala de Leitura", "Língua Portuguesa"],
        "topics": ["Literatura"],
        "days_ago": 40,
        "cover": False,
        "reads": 76,
        "students": [("Lucas A.", "8º ano A")],
        "body": """\
O clube de leitura do 8º ano escolheu um romance juvenil sobre dois amigos que se afastam \
depois de uma mudança de escola.

“Achei que ia ser chato, mas eu me vi em várias partes”, escreveu Lucas A. na ficha de leitura. \
O livro está disponível na sala de leitura, com três exemplares.""",
    },
    {
        "author": "renato",
        "title": "Olimpíada de Matemática: rascunho da lista de classificados",
        "subtitle": "",
        "type": "Notícia",
        "disciplines": ["Matemática"],
        "topics": ["Olimpíadas do Conhecimento"],
        "status": "draft",
        "cover": False,
        "body": """\
Texto em construção. Falta confirmar a lista com a coordenação.""",
    },
    {
        "author": "andre",
        "title": "Oficina de programação para o 9º ano",
        "subtitle": "",
        "type": None,
        "disciplines": [],
        "topics": ["Programação"],
        "status": "draft",
        "cover": False,
        "body": "",
    },
    {
        "author": "luciana",
        "title": "Memórias do bairro: entrevistas com moradores antigos",
        "subtitle": "A turma do 1º ano ouviu quem viu o bairro crescer.",
        "type": "Reportagem",
        "disciplines": ["História", "Sociologia"],
        "topics": ["História do Brasil"],
        "status": "in_review",
        "reviewer": "patricia",
        "review_note": "Pode olhar a introdução e se as citações estão claras?",
        "reviewer_may_publish": True,
        "students": [("Beatriz L.", "1ª série A")],
        "cover": False,
        "body": """\
Durante um mês, os alunos do 1º ano conversaram com seis moradores que chegaram ao bairro \
nas décadas de 1960 e 1970.

## O que mudou

Onde hoje fica a avenida havia um córrego a céu aberto. "A gente pescava lambari ali", \
lembrou seu Antônio, de 78 anos.

## Próximos passos

As entrevistas completas vão virar um podcast da turma.""",
    },
    {
        "author": "renato",
        "title": "Quanto custa o lanche? Pesquisa de preços na cantina",
        "subtitle": "Alunos compararam preços e montaram um cardápio que cabe no bolso.",
        "type": "Projeto",
        "disciplines": ["Matemática", "Educação Financeira"],
        "topics": ["Educação Financeira"],
        "status": "changes_requested",
        "reviewer": "andre",
        "review_note": "Confere as contas da tabela?",
        "changes_note": "A soma do segundo cardápio não fecha; e falta dizer quando os "
        "preços foram coletados.",
        "cover": False,
        "body": """\
Os alunos do 8º ano anotaram os preços da cantina durante duas semanas e montaram três \
cardápios semanais.

- Cardápio econômico: R$ 18,50 por semana
- Cardápio equilibrado: R$ 24,00 por semana
- Cardápio livre: R$ 31,00 por semana""",
    },
    {
        "author": "marcelo",
        "title": "Aviso antigo: troca do horário do intervalo",
        "subtitle": "Mudança valeu só para a semana de provas.",
        "type": "Notícia",
        "disciplines": ["Monitoria"],
        "topics": [],
        "days_ago": 60,
        "status": "archived",
        "cover": False,
        "body": """\
Na semana de provas, o intervalo da manhã passou a ser às 9h40.""",
    },
]

# --- Curadoria de notícias (Fase 4): fontes e notícias INVENTADAS, em domínios de exemplo ---
# Servem para as telas de sugestões e de pautas terem conteúdo na demonstração e nos prints do
# README. Nenhuma notícia real, nenhum veículo real.

NEWS_SOURCES = [
    {
        "key": "ciencia",
        "name": "Agência Ciência em Pauta (exemplo)",
        "feed_url": "https://noticias.exemplo.org/feed/",
        "site_url": "https://noticias.exemplo.org/",
        "language": "pt",
        "trust_level": 5,
        "default_topics": ["Divulgação científica"],
    },
    {
        "key": "science",
        "name": "Science Weekly (example)",
        "feed_url": "https://science.example.org/rss/",
        "site_url": "https://science.example.org/",
        "language": "en",
        "trust_level": 4,
        "default_topics": [],
    },
]

# (fonte, dias atrás, título, resumo)
NEWS_ITEMS = [
    (
        "ciencia",
        0,
        "Telescópio montado por estudantes registra os anéis de Saturno do pátio da escola",
        "Com peças de baixo custo, um clube de astronomia do ensino médio conseguiu fotografar "
        "o planeta e agora quer ensinar outras escolas a fazer o mesmo.",
    ),
    (
        "ciencia",
        1,
        "Painéis solares em escolas públicas cortam a conta de energia pela metade",
        "Levantamento com 40 escolas mostra que a energia solar se pagou em quatro anos. "
        "Pesquisadores sugerem usar os dados de consumo em aulas de Física e Matemática.",
    ),
    (
        "ciencia",
        1,
        "Cientistas explicam por que o céu fica alaranjado em dias de queimada",
        "A fumaça espalha a luz azul e deixa passar o vermelho e o laranja. O fenômeno é o "
        "mesmo que colore o pôr do sol e pode ser reproduzido num experimento simples.",
    ),
    (
        "ciencia",
        2,
        "Olimpíada de astronomia abre inscrições para estudantes do ensino médio",
        "A prova tem questões de observação do céu e de lançamento de foguetes feitos com "
        "garrafa PET. Escolas podem inscrever equipes até o fim do mês.",
    ),
    (
        "ciencia",
        3,
        "Turbina eólica de papelão vira experimento de energia em sala de aula",
        "Professores mostram como medir a energia gerada por uma miniturbina com um "
        "multímetro e comparar formatos de pás.",
    ),
    (
        "ciencia",
        2,
        "Robô feito com Arduino mede a qualidade do ar dentro da sala de aula",
        "O projeto usa sensores de gás carbônico e acende uma luz quando é hora de abrir as "
        "janelas. O código foi publicado para outras escolas usarem.",
    ),
    (
        "ciencia",
        4,
        "Juros do cartão: como montar um orçamento sem cair no rotativo",
        "Economistas explicam o rotativo com exemplos do dia a dia e sugerem planilhas simples "
        "para famílias e estudantes.",
    ),
    (
        "science",
        1,
        "NASA telescope spots water vapor on a distant planet",
        "Astronomers used the telescope to study the atmosphere of a planet twice the size of "
        "Earth, a step toward finding worlds that could host life.",
    ),
]

# Pautas de exemplo: (quem propõe, título, notas, tópicos, situação)
STORY_IDEAS = [
    (
        "joao",
        "Guia de estudos para o ENEM feito pelos próprios alunos",
        "Juntar as dicas das turmas do 3º ano e publicar em partes até a prova.",
        ["ENEM e Vestibular"],
        "open",
    ),
    (
        "luciana",
        "Sarau de poesia: bastidores do ensaio",
        "Acompanhar um ensaio e entrevistar quem vai se apresentar pela primeira vez.",
        ["Literatura"],
        "in_progress",
    ),
]
