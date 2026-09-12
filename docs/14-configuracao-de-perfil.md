# 14 — Configuração de perfil

Rota: `/painel/perfil/` · Nome: `accounts:profile_edit` · Camada: **MVP** · Fase 1

Complementares: `/painel/conta/` (login, senha) e `/admin/` (criação de contas pelo admin).

## Objetivo

Um membro da equipe deve preencher o perfil em cinco minutos, no primeiro acesso, sem sentir que está preenchendo um formulário burocrático. As informações servem a três fins: apresentação pública, crédito nas publicações e recomendação de pautas.

## Criação de contas

Só o admin cria contas, no Django Admin, informando e-mail institucional, nome, papel e cargo. Não há convite por e-mail (não há e-mail no sistema).

Primeiro acesso, duas formas:

1. **Microsoft** (padrão): a pessoa clica "Entrar com a conta da escola" e usa o e-mail `@professor.educacao.sp.gov.br`. Se o e-mail corresponder a uma conta pré-cadastrada, a conta é ativada. Sem pré-cadastro, o login é recusado com a mensagem "Peça ao administrador para cadastrar você".
2. **Senha** (reserva): o admin gera um "link de primeiro acesso" (token de uso único, 7 dias) e envia pelo canal que quiser (WhatsApp, pessoalmente). A pessoa define a senha.

Ver [23](23-seguranca-e-lgpd.md) para detalhes de autenticação.

## Assistente de primeiro acesso

Três passos, puláveis:

1. **Quem é você**: foto, nome de exibição, cargo (pré-preenchido pelo admin), headline.
2. **O que você ensina ou faz**: disciplinas (multi-seleção agrupada por área). Para cargos não docentes, o passo mostra áreas em vez de disciplinas.
3. **O que interessa a você**: tópicos (chips; os ligados às disciplinas escolhidas aparecem primeiro) e "Sobre mim" opcional.

O painel mostra "Complete seu perfil" enquanto faltarem foto, disciplinas/áreas ou bio.

## Formulário de perfil

Uma página com seções, um botão salvar. Sem abas.

### Apresentação

| Campo | Tipo | Validação | Ajuda |
|---|---|---|---|
| Foto | Upload | JPG/PNG/WebP até 5 MB; recorte quadrado no navegador antes de enviar | "Aparece nas suas publicações e no seu perfil" |
| Nome de exibição | texto, 80 | obrigatório | "Como seu nome aparece no jornal" |
| Cargo | seleção (`staff_kind`) | obrigatório | Professor, Monitor, Coordenação, Direção, Sala de leitura, Outro |
| Headline | texto, 120 | obrigatório | Ex.: "Professora de Biologia e Ciências", "Monitor escolar" |
| Sobre mim | textarea, 800 | opcional; contador | |
| Na escola desde | ano | opcional | |
| Perfil público | toggle | padrão ligado | "Desligado, seu perfil não aparece na lista nem em buscas" |

### Atuação

| Campo | Tipo | Validação |
|---|---|---|
| Disciplinas | checkboxes por área | ao menos uma para docentes com perfil público |
| Áreas de atuação | chips derivados das disciplinas; editável; obrigatório para não docentes | |

### Interesses

| Campo | Tipo | Ajuda |
|---|---|---|
| Tópicos | chips com busca; sugestão de novo tópico vai para aprovação do admin | "Usados para sugerir pautas para você" |
| Aceito sugestões em inglês | toggle (padrão ligado) | Fase 4 |

### Formação e links

| Campo | Tipo | Validação |
|---|---|---|
| Formação | lista de (título, instituição, ano), até 6 | opcional |
| Links | lista de (rótulo, URL), até 4 | `https` |

### Preferências

| Campo | Padrão |
|---|---|
| Mostrar meu nome como revisor nas publicações que revisei | ligado |
| Permitir que revisores publiquem por mim (padrão ao pedir revisão) | desligado |
| Mostrar contagem de leituras nas minhas publicações | ligado |

## Conta

`/painel/conta/`: método de login em uso (Microsoft ou senha), definir/alterar senha (apenas para contas com senha), sessões ativas com "sair de todas", baixar meus dados (JSON, Fase 2), solicitar exclusão (abre pedido ao admin, Fase 2).

## Regras

- Upload de foto passa por `MediaAsset` como qualquer imagem.
- Mudança de nome de exibição não altera créditos congelados de publicações já publicadas, salvo se o usuário marcar "atualizar créditos anteriores" (gera evento editorial).
- Novo tópico sugerido entra como `is_active = false` até o admin aprovar.
- Cargo e papel são editados só pelo admin; o usuário vê, não altera.

## Histórico

- 2026-09-12: versão inicial (com perfil de aluno e convite por e-mail).
- 2026-09-12: reescrito. Sem contas de aluno; contas criadas pelo admin; login Microsoft; link de primeiro acesso manual; campo cargo.
