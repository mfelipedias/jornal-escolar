# Documentação do projeto — Jornal Escolar

Jornal digital da comunidade escolar · `jornal.projetosrosa.com.br`

Esta pasta é a fonte de verdade do planejamento. Cada arquivo cobre um tema e pode ser revisado de forma independente conforme o projeto evolui. Nenhum código deve ser escrito sem que a decisão correspondente esteja registrada aqui.

## Como usar

1. Leia o [briefing](01-briefing.md) primeiro. Ele define o que o projeto é, o que não é e os princípios que guiam as outras decisões.
2. Antes de implementar uma tela ou módulo, abra o arquivo correspondente e verifique se o item está marcado como **MVP**, **Evolução** ou **Experimental**.
3. Quando uma decisão mudar, edite o arquivo e registre a mudança na seção "Histórico" ao final dele.
4. O [plano de desenvolvimento incremental](26-plano-de-desenvolvimento.md) é o roteiro de execução. Ele referencia os demais documentos.

## Índice

### Produto
| Arquivo | Conteúdo |
|---|---|
| [01-briefing.md](01-briefing.md) | Ideia principal, objetivo, público, princípios, visão crítica e riscos |
| [02-personas-papeis-permissoes.md](02-personas-papeis-permissoes.md) | Personas, tipos de usuário e matriz de permissões |
| [03-funcionalidades-priorizacao.md](03-funcionalidades-priorizacao.md) | Lista de funcionalidades, MoSCoW, o que não construir, complexidade |
| [04-fluxo-editorial.md](04-fluxo-editorial.md) | Estados de uma publicação, transições, papéis de autoria, notificações |

### Arquitetura
| Arquivo | Conteúdo |
|---|---|
| [05-arquitetura-tecnica.md](05-arquitetura-tecnica.md) | Comparação de tecnologias, stack escolhida e decisões registradas |
| [06-modelo-de-dados.md](06-modelo-de-dados.md) | Entidades, campos, relacionamentos, índices e diagrama |
| [07-rotas-e-api.md](07-rotas-e-api.md) | Mapa de URLs, endpoints internos (HTMX/JSON) e API pública futura |
| [08-estrutura-do-repositorio.md](08-estrutura-do-repositorio.md) | Árvore de diretórios e papel de cada pasta |
| [23-seguranca-e-lgpd.md](23-seguranca-e-lgpd.md) | Autenticação, autorização, dados de menores, uploads, auditoria |
| [24-infraestrutura-e-deploy.md](24-infraestrutura-e-deploy.md) | Docker Compose, proxy, backups, ambiente de desenvolvimento |

### Design e telas
| Arquivo | Conteúdo |
|---|---|
| [09-design-system.md](09-design-system.md) | Direção visual, tipografia, cores, espaçamento, componentes, estados |
| [10-pagina-inicial.md](10-pagina-inicial.md) | Home |
| [11-pagina-publicacao.md](11-pagina-publicacao.md) | Página de leitura de uma publicação |
| [12-paginas-de-navegacao.md](12-paginas-de-navegacao.md) | Área, disciplina, tipo, lista de professores, busca, sobre |
| [13-perfil-publico-professor.md](13-perfil-publico-professor.md) | Perfil público de um membro da equipe |
| [14-configuracao-de-perfil.md](14-configuracao-de-perfil.md) | Edição do próprio perfil e criação de contas |
| [15-painel-professor.md](15-painel-professor.md) | Painel, minhas publicações, revisões, comentários, sugestões |
| [16-editor-de-publicacoes.md](16-editor-de-publicacoes.md) | Editor de conteúdo, armazenamento e mídia |
| [17-tela-de-revisao.md](17-tela-de-revisao.md) | Revisão, comentários editoriais e aprovação |
| [18-painel-administrativo.md](18-painel-administrativo.md) | Administração: usuários, taxonomia, moderação, configurações |

### Funcionalidades transversais
| Arquivo | Conteúdo |
|---|---|
| [19-busca-e-filtros.md](19-busca-e-filtros.md) | Busca global e filtros |
| [20-reacoes-leituras-comentarios.md](20-reacoes-leituras-comentarios.md) | Reações, contador de leituras e comentários públicos moderados |
| [21-curadoria-de-noticias.md](21-curadoria-de-noticias.md) | Fontes externas, APIs, classificação, recomendação, direitos autorais |
| [22-ia.md](22-ia.md) | Onde IA agrega valor, onde não, riscos e arquitetura (fase congelada) |
| [29-clima.md](29-clima.md) | Bloco "Hoje na escola" com Open-Meteo |

### Execução
| Arquivo | Conteúdo |
|---|---|
| [25-roadmap.md](25-roadmap.md) | Fases, dependências, riscos, resultado esperado |
| [26-plano-de-desenvolvimento.md](26-plano-de-desenvolvimento.md) | Etapas pequenas e verificáveis com critérios de aceite |
| [27-decisoes-pendentes-e-perguntas.md](27-decisoes-pendentes-e-perguntas.md) | Respostas do dono do projeto, decisões resultantes e o que continua aberto |
| [28-glossario.md](28-glossario.md) | Vocabulário do projeto |
| [30-versionamento.md](30-versionamento.md) | Esquema de versões, changelog, releases |

### Guias de operação (para quem não é da área)
| Arquivo | Conteúdo |
|---|---|
| [31-guia-backup.md](31-guia-backup.md) | Como o backup funciona, o que configurar uma vez, como conferir e como restaurar |
| [32-guia-login-microsoft.md](32-guia-login-microsoft.md) | Como o login com a conta da escola funciona, o que registrar, e o que acontece se não funcionar |

## Convenções usadas nos documentos

- **MVP**: necessário para o jornal funcionar e ser usado pela escola.
- **Evolução**: planejado, mas só depois do MVP estar em uso.
- **Experimental**: vale testar; não condiciona a arquitetura.
- Nomes de código (tabelas, campos, rotas, apps) estão em inglês e em `snake_case`. Textos de interface são em português do Brasil.
- Decisões arquiteturais seguem o formato: problema, alternativas, trade-offs, decisão, consequência.
- O vocabulário de negócio está no [glossário](28-glossario.md).
