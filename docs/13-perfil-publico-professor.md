# 13 — Perfil público de um membro da equipe

Rota: `/professores/<slug>/` · Nome: `accounts:teacher_detail` · Camada: **MVP** · Fase 1

Vale para todos os cargos (professor, monitor, coordenação, direção, sala de leitura). A URL usa "professores" por ser o termo que os leitores buscam; a lista chama-se "Quem escreve".

## Objetivo

Mostrar quem é a pessoa e o que ela produz no jornal, de forma que um aluno ou colega entenda a área de atuação em segundos. Não é um currículo. É uma página de autor.

## Estrutura

```
┌──────────────────────────────────────────────────────────────┐
│ MASTHEAD                                                     │
├──────────────────────────────────────────────────────────────┤
│ ┌────────┐  Carla Souza                                      │
│ │ foto   │  Professora de Biologia e Ciências                │
│ │ 160px  │  Ciências da Natureza · Biologia · Ciências       │
│ └────────┘  Na escola desde 2019                             │
│                                                              │
│ Sobre                                                        │
│ Texto de até 800 caracteres.                                 │
│                                                              │
│ Formação            Interesses                               │
│ · Licenciatura em   #Ecologia #Divulgação científica         │
│   Biologia, UFXX,   #Educação ambiental                      │
│   2012                                                       │
│ · Mestrado em ...   Links                                    │
│                     Lattes · Site                            │
├──────────────────────────────────────────────────────────────┤
│ PUBLICAÇÕES (23)         [Todas] [Como autora] [Colaborações]│
│ card compact                                                 │
│ card compact                                                 │
│ ...                                                          │
│ [Carregar mais]                                              │
├──────────────────────────────────────────────────────────────┤
│ PARTICIPAÇÃO EDITORIAL (Evolução)                            │
│ Linha do tempo: 2026 · 8 publicações, 5 revisões             │
│                 2025 · 12 publicações, 3 revisões            │
└──────────────────────────────────────────────────────────────┘
```

## Dados exibidos

| Campo | Origem | Regra |
|---|---|---|
| Foto | `User.avatar` | Se ausente, círculo com iniciais na cor da área principal |
| Nome | `User.display_name` | |
| Headline | `TeacherProfile.headline` | Inclui o cargo (`staff_kind`) como etiqueta discreta se o headline não o mencionar |
| Áreas e disciplinas | `areas`, `disciplines` | Chips clicáveis |
| Desde | `since_year` | Opcional |
| Sobre | `bio` | Texto simples com quebras de linha |
| Formação | `education` | Lista; opcional |
| Interesses | `topics` | Chips; clicáveis a partir da Fase 3 |
| Links | `links` | `rel="noopener nofollow"` |
| Publicações | `ArticleContributor` com `user` = professor, publicação `published` | Abas: Todas; Como autor(a) (`author`, `coauthor`); Colaborações (`collaborator`, `reviewer`, `editor`, respeitando `show_reviewer_credit`) |
| Participação editorial | `EditorialEvent` por ano | Evolução, Fase 6 |

Nunca exibido: e-mail, telefone, data de nascimento, papel no sistema.

## Ações

| Ação | Quem |
|---|---|
| Abrir publicações, disciplinas, links | Todos |
| "Editar perfil" | O próprio professor e admin (botão discreto ao lado do nome) |

## Estados

- Perfil sem publicações: "Ainda não há publicações" com texto neutro.
- Perfil `is_public = false`: 404 para o público; o próprio usuário vê com faixa "Seu perfil está oculto".
- Usuário desativado: perfil some da lista; a página continua acessível se houver publicações (crédito histórico), com bio e contatos ocultos.

## SEO

- JSON-LD `Person` com `name`, `jobTitle`, `image`. Sem `worksFor`: o nome da escola não aparece no site.
- Open Graph com a foto.

## Por que alunos não têm esta página

Alunos não têm conta no sistema, por decisão da escola. Um perfil público de menor de idade, com foto, turma e produção, criaria um dossiê indexável. O crédito de autoria nas publicações já reconhece o trabalho. Registrado em [27](27-decisoes-pendentes-e-perguntas.md).

## Histórico

- 2026-09-12: versão inicial.
- 2026-09-12: vale para toda a equipe, com cargo.
