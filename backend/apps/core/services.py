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
no painel, o de sessão. Quando reações e contagem de leituras estiverem ligadas, um cookie \
com um código aleatório evita contar a mesma leitura duas vezes, sem identificar quem lê.
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

- Quem comenta informa só um nome, de preferência apenas o primeiro.
- Os comentários só aparecem depois de aprovados por quem publicou ou pela coordenação.
- Guardamos um código cifrado do endereço IP para evitar abusos, nunca o endereço em si.

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

# Primeira versão do texto (E15). Se a página ainda estiver exatamente assim, seed_site troca
# pelo texto completo de PRIVACY_BODY; se alguém já editou, nada muda.
OLD_PRIVACY_MARKER = "RASCUNHO: revisar com a direção antes de publicar."


@transaction.atomic
def seed_site() -> dict[str, int]:
    """Cria configurações e páginas institucionais que faltam, sem alterar as existentes.

    Exceção: a Privacidade ainda com o rascunho curto da E15, nunca editada, recebe o texto
    completo (E28). Continua despublicada até a direção aprovar.
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
        and OLD_PRIVACY_MARKER in page.body_html
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


def set_page_published(user: User, page: StaticPage, published: bool) -> StaticPage:
    if not permissions.can_edit_pages(user):
        raise PermissionDenied
    page.is_published = published
    page.updated_by = user
    page.save(update_fields=["is_published", "updated_by", "updated_at"])
    return page
