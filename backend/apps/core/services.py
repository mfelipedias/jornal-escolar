from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import User
from apps.editorial import permissions
from apps.publications import rendering

from . import site_settings
from .models import StaticPage

PAGE_TITLE_MAX = 120
PAGE_LEAD_MAX = 240


def check_database() -> bool:
    """O banco responde a uma consulta simples."""
    try:
        with connections[DEFAULT_DB_ALIAS].cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return False
    return True


def check_migrations() -> bool:
    """Todas as migrações conhecidas pelo código já foram aplicadas no banco."""
    try:
        executor = MigrationExecutor(connections[DEFAULT_DB_ALIAS])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except DatabaseError:
        return False
    return not plan


# Política de privacidade (docs/23, E28). Linhas "## " viram subtítulos e blocos de "- ",
# listas (text_to_document). Precisa da aprovação da direção antes de ir ao ar.
PRIVACY_BODY = """\
Este jornal é um projeto pedagógico feito pela equipe da escola. Guardamos o mínimo de dados \
necessário para publicar, dar crédito a quem participa e manter o site seguro. Não vendemos, \
não alugamos e não compartilhamos dados para publicidade.

## Quem só lê o jornal

- Não é preciso criar conta nem informar dados para ler.
- Não usamos anúncios, rastreadores de publicidade nem ferramentas de análise de terceiros.
- O site usa só cookies técnicos: o de proteção dos formulários e, para a equipe que entra \
no painel, o de sessão.
- Quem abre uma publicação recebe o cookie “jv”, com um código aleatório que dura um ano. Ele \
serve só para lembrar a reação que você deixou, para não contar a mesma leitura duas vezes e \
para limitar quantos comentários seus esperam aprovação ao mesmo tempo. Não guarda nome, \
e-mail ou endereço IP, não identifica quem lê e não é usado para publicidade. Apagar \
os cookies do navegador apaga esse código.
- Quem reage não aparece em lugar nenhum: o site mostra só o total de cada reação.
- Os registros técnicos do servidor (página pedida, horário e erros) não guardam o endereço \
IP de quem visita e são descartados automaticamente. A Cloudflare, que protege o site contra \
ataques, trata o endereço IP conforme a política de privacidade dela.

## Alunos

- Alunos não têm conta no jornal.
- Quando um aluno participa de uma publicação, aparece nos créditos o primeiro nome com a \
inicial do sobrenome (por exemplo, “Rafael S.”) e a turma. O nome completo só é usado se a \
coordenação definir essa regra.
- O professor só credita um aluno ou publica foto em que ele apareça quando existe \
autorização assinada pelo responsável (ou pelo próprio aluno, se maior de 18 anos). O termo \
em papel fica guardado na secretaria, fora do sistema.
- Não guardamos data de nascimento, documentos, endereço nem contato de alunos ou famílias.
- Não existe página, lista ou busca por aluno: o nome aparece apenas nos créditos da \
publicação.
- A família pode revogar a autorização a qualquer momento. O crédito é trocado por uma \
descrição genérica (por exemplo, “aluno da 2ª série”) e a foto é retirada.

## Equipe da escola

- Professores e funcionários que publicam têm conta criada pela coordenação, com e-mail \
institucional, nome, cargo e o que cada pessoa decidir mostrar no perfil (foto, apresentação, \
formação, disciplinas, interesses e links).
- No login com a conta Microsoft da escola, o jornal lê apenas o e-mail e o nome.
- Senhas são guardadas de forma cifrada (hash), nunca em texto.
- O sistema registra o último acesso e o histórico de edição das publicações, para \
organizar o trabalho editorial e investigar problemas de segurança.
- Quem sair da equipe tem a conta desativada; os dados pessoais podem ser anonimizados a \
pedido.

## Comentários

- Para comentar não é preciso conta. O formulário pede só um nome e o comentário; não pedimos \
e-mail nem telefone.
- O nome informado aparece em público junto do comentário. Use só o primeiro nome.
- Nenhum comentário aparece antes de ser aprovado por quem publicou o texto ou pela \
coordenação, que pode encurtar o nome antes de aprovar.
- Links e endereços de e-mail escritos no comentário são apagados no envio.
- Não há verificação de identidade: um comentário assinado com um nome pode não ser dessa \
pessoa.
- Para evitar abusos, junto do comentário ficam um código embaralhado (hash) do endereço IP, \
nunca o endereço em si, e o código do cookie “jv”. Esses dados técnicos são apagados em 30 \
dias; os comentários rejeitados também.
- Respostas da equipe aparecem com o nome de quem respondeu.
- Para pedir a remoção de um comentário, escreva para o e-mail de contato do rodapé.

## Onde os dados ficam

- O site roda em servidor mantido pelo projeto e passa pela rede da Cloudflare, que protege \
contra ataques e entrega as páginas com segurança (HTTPS).
- Há cópias de segurança diárias do banco de dados e das fotos, criptografadas antes de sair \
do servidor.

## Seus direitos

Pela Lei Geral de Proteção de Dados (Lei 13.709/2018), você pode pedir para saber quais dados \
temos sobre você ou sobre o aluno de quem é responsável, corrigir, anonimizar ou apagar esses \
dados e revogar uma autorização. Para isso, escreva para o e-mail de contato que aparece no \
rodapé de todas as páginas. Respondemos o quanto antes, em até 15 dias.

## Mudanças nesta página

Quando esta política mudar, a nova versão será publicada aqui. Última atualização: \
setembro de 2026.
"""

# Textos iniciais das páginas institucionais. Sem nome da escola (docs/27).
# Privacidade nasce despublicada: precisa de revisão da direção (docs/23).
INITIAL_PAGES = [
    {
        "slug": StaticPage.Slug.ABOUT,
        "title": "Sobre o jornal",
        "lead": "Um jornal digital feito pela comunidade escolar.",
        "body": (
            "Aqui professores, monitores e a equipe da escola publicam notícias, "
            "reportagens, projetos e produções de alunos.\n\n"
            "Os textos são organizados por área do conhecimento, para que seja fácil "
            "encontrar o que se estuda e se produz em cada uma.\n\n"
            "Alunos participam entregando seus textos a um professor, que revisa, publica "
            "e dá o crédito."
        ),
        "is_published": True,
    },
    {
        "slug": StaticPage.Slug.CONTRIBUTE,
        "title": "Como participar",
        "lead": "Tem uma ideia, um texto ou um projeto para mostrar?",
        "body": (
            "Alunos: converse com um professor. Ele ajuda a preparar o texto e publica "
            "com o seu nome nos créditos.\n\n"
            "Professores e equipe: peça à coordenação o seu acesso ao jornal.\n\n"
            "Leitores: comente as publicações. Os comentários aparecem depois de "
            "aprovados por quem publicou."
        ),
        "is_published": True,
    },
    {
        "slug": StaticPage.Slug.PRIVACY,
        "title": "Privacidade",
        "lead": "Como o jornal trata os dados de quem lê, de quem escreve e dos alunos creditados.",
        "body": PRIVACY_BODY,
        "is_published": False,
    },
]

# Textos padrão antigos, reconhecidos por um trecho que só eles têm: o rascunho curto da E15, o
# texto da E28 (antes do cookie das reações, E38) e o da E38 (antes dos comentários, E40).
# Página nunca editada por ninguém (sem updated_by) com um desses trechos recebe o
# PRIVACY_BODY atual; se alguém já editou, nada muda.
OLD_PRIVACY_MARKER = "RASCUNHO: revisar com a direção antes de publicar."
E28_PRIVACY_MARKER = "Quando reações e contagem de leituras estiverem ligadas"
E38_PRIVACY_MARKER = "Guardamos um código cifrado do endereço IP para evitar abusos"
OLD_PRIVACY_MARKERS = (OLD_PRIVACY_MARKER, E28_PRIVACY_MARKER, E38_PRIVACY_MARKER)


@transaction.atomic
def seed_site() -> dict[str, int]:
    """Cria configurações e páginas institucionais que faltam, sem alterar as existentes.

    Exceção: a Privacidade ainda com um texto padrão antigo (E15, E28 ou E38), nunca editada, recebe
    o texto atual. Publicada ou não, continua como estava.
    """
    created_pages = 0
    for data in INITIAL_PAGES:
        defaults = {k: v for k, v in data.items() if k not in ("slug", "body")}
        document = text_to_document(data["body"])
        defaults.update(body_json=document, body_html=rendering.render(document, set()).html)
        page, created = StaticPage.objects.get_or_create(slug=data["slug"], defaults=defaults)
        created_pages += created
        if not created and _is_untouched_old_privacy(page):
            for key, value in defaults.items():
                if key != "is_published":
                    setattr(page, key, value)
            page.save()
    return {"configurações": site_settings.ensure_defaults(), "páginas": created_pages}


def _is_untouched_old_privacy(page: StaticPage) -> bool:
    return (
        page.slug == StaticPage.Slug.PRIVACY
        and page.updated_by_id is None
        and any(marker in page.body_html for marker in OLD_PRIVACY_MARKERS)
    )


def text_to_document(text: str) -> dict:
    """Texto simples → documento do editor.

    Blocos separados por linha em branco. "## Título" vira subtítulo; um bloco em que todas
    as linhas começam com "- " vira lista; o resto é parágrafo (quebras de linha mantidas).
    """
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    content = []
    for block in blocks:
        lines = block.split("\n")
        if len(lines) == 1 and block.startswith("## "):
            heading = [{"type": "text", "text": block[3:].strip()}]
            content.append({"type": "heading", "attrs": {"level": 2}, "content": heading})
        elif all(line.startswith("- ") for line in lines):
            items = [
                {"type": "listItem", "content": [_paragraph([line[2:].strip()])]} for line in lines
            ]
            content.append({"type": "bulletList", "content": items})
        else:
            content.append(_paragraph(lines))
    return {"type": "doc", "content": content}


def _paragraph(lines: list[str]) -> dict:
    inline: list[dict] = []
    for index, line in enumerate(lines):
        if index:
            inline.append({"type": "hardBreak"})
        if line:
            inline.append({"type": "text", "text": line})
    return {"type": "paragraph", "content": inline}


class PageConflictError(Exception):
    """Outra pessoa salvou a página depois da versão que o editor carregou."""


@transaction.atomic
def update_page(
    user: User, page: StaticPage, *, expected_updated_at: datetime | None = None, **fields: Any
) -> StaticPage:
    """Autosave de título, linha fina e corpo de uma página institucional (editor+).

    O HTML é sempre gerado aqui, a partir do documento limpo; figuras são descartadas
    (páginas institucionais não têm imagens).
    """
    if not permissions.can_edit_pages(user):
        raise PermissionDenied
    unknown = set(fields) - {"title", "lead", "body_json"}
    if unknown:
        raise ValueError(f"Campos não editáveis: {sorted(unknown)}")
    current = StaticPage.objects.select_for_update().get(pk=page.pk)
    if (
        expected_updated_at is not None
        and current.updated_at != expected_updated_at
        and current.updated_by_id not in (None, user.pk)
    ):
        raise PageConflictError
    if "title" in fields:
        title = " ".join(str(fields["title"] or "").split())
        if len(title) > PAGE_TITLE_MAX:
            raise ValidationError({"title": f"O título pode ter até {PAGE_TITLE_MAX} caracteres."})
        # Título apagado no meio da digitação: mantém o anterior em vez de falhar o autosave.
        current.title = title or current.title
    if "lead" in fields:
        current.lead = " ".join(str(fields["lead"] or "").split())[:PAGE_LEAD_MAX]
    if "body_json" in fields:
        result = rendering.render(fields["body_json"], allowed_assets=set())
        current.body_json = result.document
        current.body_html = result.html
    current.updated_by = user
    current.save()
    return current


def set_page_published(
    user: User, page: StaticPage, published: bool, *, request: Any = None
) -> StaticPage:
    from . import audit

    if not permissions.can_edit_pages(user):
        raise PermissionDenied
    changed = page.is_published != published
    page.is_published = published
    page.updated_by = user
    page.save(update_fields=["is_published", "updated_by", "updated_at"])
    if changed:
        action = audit.Action.PAGE_PUBLISHED if published else audit.Action.PAGE_UNPUBLISHED
        audit.record(action, actor=user, target=page, changes={"slug": page.slug}, request=request)
    return page
