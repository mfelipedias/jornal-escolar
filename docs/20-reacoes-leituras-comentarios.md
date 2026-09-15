# 20 — Reações, contador de leituras e comentários públicos

Camada: **MVP** · Fase 3

## Reações

### Tipos

| Código | Rótulo | Emoji |
|---|---|---|
| `interesting` | Interessante | 👍 |
| `learned` | Aprendi algo | 💡 |
| `liked` | Gostei | ❤️ |
| `congrats` | Parabéns | 👏 |

Fixos no código. Adicionar um quinto tipo é uma migração simples.

### Decisões

| Pergunta | Decisão | Justificativa |
|---|---|---|
| Visitante anônimo pode reagir? | **Sim** | Leitores não têm conta. Dano potencial (inflar contador) é baixo. |
| Uma reação por pessoa? | **Sim, uma por publicação**; pode trocar de tipo ou remover | Mantém o contador significativo. |
| Como identificar o anônimo? | Cookie `jv` com UUID v4, 1 ano, `SameSite=Lax`, `HttpOnly`, `Secure` | Não identifica a pessoa; documentado na privacidade. |
| Como evitar abuso? | Rate limit por IP (30/min) e por chave (10/min); ignora requisição sem cookie previamente emitido | Proporcional ao risco. |
| Mostrar quem reagiu? | **Não** | |
| Contador quando zero? | Botões sem número | Evita "0 0 0 0". |

### Modelo e interação

`Reaction(article, user | anon_key, kind)`, unicidade por `(article, user)` e `(article, anon_key)`. `Article.reactions_count` (JSONB) atualizado na mesma transação.

`POST /x/articles/<id>/react/` com `kind`: igual remove (toggle), diferente troca. Devolve o fragmento `reaction-bar`. Sem JS: formulário POST com redirecionamento. Botões com `aria-pressed`.

## Contador de leituras

### Definição de "leitura" (MVP)

Registra-se uma leitura quando, em uma publicação publicada:

1. o visitante permaneceu ao menos `reads.min_seconds` (padrão 15s) com a aba visível, **e**
2. rolou ao menos 25% do corpo (ou o corpo cabe na tela), **e**
3. não há registro para `(article, viewer_key, day)`.

`viewer_key` = `u:<user_id>` ou `a:<uuid>` do cookie. Uma pessoa conta no máximo uma leitura por publicação por dia. JavaScript mínimo envia `navigator.sendBeacon('/x/articles/<id>/read/')`. Bots sem JS não contam. Rate limit por IP (60/min).

Não contar carregamentos de página: inflaria com recarregamentos, bots, pré-carregamento e o próprio autor revisando.

### Armazenamento

`ArticleRead(article, viewer_key, day)` com `ON CONFLICT DO NOTHING`; quando há inserção, incrementa `Article.reads_count`. Limpeza mensal apaga registros com mais de 90 dias (o total já está consolidado).

### Exibição

- Publicação: "143 leituras" discreto, só se `reads_count >= 10`.
- Painel: leituras por publicação e total em 30 dias.

### Versão robusta (Evolução)

Filtrar user agents de bots e IPs de datacenter; `ip_hash` com sal diário para detectar rajadas; painel com séries temporais.

## Comentários públicos

### Princípio

Leitores comentam sem conta, identificando-se pelo nome. **Nenhum comentário aparece sem aprovação** de um autor da publicação, de um editor ou do admin. Isso mantém o espaço seguro para um público majoritariamente menor de idade e remove a necessidade de moderação reativa: o padrão é invisível até alguém aprovar.

### O que o leitor vê

Ao final da publicação, após as reações:

```
Comentários (4)
──────────────
Mariana · 12 set
Adorei a parte sobre os sensores! Dá para fazer na escola?
   ↳ Resposta de Carla Souza (autora) · 12 set
     Dá sim, vamos montar um no laboratório em outubro.

Pedro · 11 set
...

Deixe um comentário
[ Seu nome (use só o primeiro nome)      ]
[ Comentário                              ]
[ Enviar ]  Seu comentário aparece depois que o autor aprovar.
```

### Regras

| Regra | Valor |
|---|---|
| Campos | `author_name` (2 a 60 caracteres, obrigatório) e `body` (5 a 1000 caracteres). Sem e-mail, sem telefone. |
| Identificação | `anon_key` do cookie e `ip_hash` (sal mensal), só para limites e auditoria. |
| Links | URLs no corpo são removidas ao salvar e o comentário recebe a marca `had_links` para o moderador ver. |
| Limites | 3 comentários pendentes por `anon_key` por publicação; 10 comentários por IP por hora; honeypot invisível no formulário. |
| Estados | `pending` → `approved` ou `rejected`. Rejeitados são apagados após 30 dias. |
| Quem modera | Autores e coautores da publicação (`staff`), editor, admin. |
| Respostas | Só a equipe responde, e a resposta aparece como "Resposta de [nome] (autora)". Sem threads entre leitores. |
| Edição pelo leitor | Não existe. Pode pedir remoção pelo e-mail de contato da página de privacidade. |
| Desligar | `comments.enabled` global e `comments_enabled` por publicação (o autor pode fechar comentários de um texto). |
| Nome | Ajuda do campo: "use só o primeiro nome". O moderador pode editar o nome exibido antes de aprovar (ex.: reduzir sobrenome). |

### Moderação no painel

- Bloco "Comentários aguardando (3)" no início do painel e aba "Comentários" em Minhas publicações.
- Lista com: publicação, nome, texto, data, marcas (`had_links`, "mesmo IP enviou 5"), botões Aprovar, Rejeitar, Editar nome, Responder e aprovar.
- Aprovar em lote.
- Editores veem "Todos os pendentes"; comentários pendentes há mais de 3 dias geram notificação aos editores.

### Modelo

| Campo | Tipo |
|---|---|
| article | FK Article |
| author_name | varchar(60) |
| body | text (≤ 1000) |
| status | `pending`, `approved`, `rejected` |
| anon_key | uuid nullable |
| ip_hash | char(64) |
| had_links | bool |
| reply_body | text nullable |
| replied_by | FK User nullable |
| moderated_by, moderated_at | FK User, timestamp |
| created_at | timestamp |

Índice: `(article, status, created_at)`; `(status, created_at)` para a fila.

`Article.comments_count` guarda só os aprovados.

### Privacidade

- O nome informado é público. A política de privacidade explica isso e recomenda o primeiro nome.
- Não há verificação de identidade: um comentário "assinado" por alguém pode não ser dessa pessoa. Por isso a moderação por quem conhece a turma.
- Comentários rejeitados e os dados técnicos (`ip_hash`) são apagados em 30 dias.

## Sem rastreadores

Sem Google Analytics. Métricas de tráfego, se quiser, com Plausible ou Umami auto-hospedado (Evolução).

## Histórico

- 2026-09-12: versão inicial (sem comentários).
- 2026-09-12: adicionados comentários públicos moderados; arquivo renomeado.
- 2026-09-14: E38 (reações), detalhes da implementação: app `engagement`. O cookie `jv` é emitido pela página da publicação para quem não entrou; quem entrou reage com a conta. POST sem cookie (ou com cookie inválido) não grava e devolve a barra com um aviso e o cookie novo. Os limites contam toda tentativa, primeiro por IP (antes do cookie) e depois por pessoa; o bloqueio responde 429 com a barra e o aviso (o `app.js` faz o HTMX trocar a barra mesmo com 429 e 400); sem JavaScript, uma página curta com link de volta. `reactions_count` é recalculado com um `COUNT` agrupado sob `select_for_update` da publicação, em vez de somar e subtrair, e gravado por `update()`, sem disparar a invalidação do cache público. A configuração `reactions.require_login` restringe as reações a quem entrou.
