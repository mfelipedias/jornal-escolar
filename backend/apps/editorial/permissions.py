"""Única fonte das regras de permissão (docs/02 "Matriz de permissões", docs/04).

Views, services, templates e testes usam estas funções; nenhuma regra é repetida em outro
lugar. Todas recebem o usuário (pode ser anônimo) e devolvem bool. Nos templates, use a tag
{% can "acao" objeto as variavel %} (apps/editorial/templatetags/permissions.py), que chama
a função can_<acao> daqui.

A E12 cobriu rascunho, publicado e arquivado; a E29 acrescentou a revisão por colega
(em revisão, alterações sugeridas); a E30 fechou a matriz (perfil, entrada, administração,
comentário interno da revisão) e a testa célula a célula em editorial/tests/test_matrix.py.
Linhas da matriz que dependem de recursos futuros (pautas, fontes) ganham função quando a
etapa delas chegar. Reações: can_react (E38). Comentários públicos: can_comment e
can_reply_comment (E40); moderação e abrir/fechar comentários: can_moderate_comments e
can_toggle_comments (E41).
"""

from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import TeacherProfile, User
from apps.core.site_settings import get_setting
from apps.publications.models import Article, ArticleContributor, MediaAsset

AnyUser = User | AnonymousUser


def is_staff_member(user: AnyUser) -> bool:
    """Tem conta ativa na equipe (qualquer papel)."""
    return bool(user.is_authenticated and user.is_active)


# --- conta, perfil e administração ---


def can_log_in(user: AnyUser) -> bool:
    """Entrar (Microsoft ou senha): só contas da equipe ativas. Visitante não tem conta."""
    return bool(isinstance(user, User) and user.pk and user.is_active)


def can_view_profile(user: AnyUser, profile: TeacherProfile) -> bool:
    """Perfil público: todo mundo. Perfil oculto: só o próprio dono."""
    if profile.is_public:
        return True
    return is_staff_member(user) and user.pk == profile.user_id


def can_edit_profile(user: AnyUser, person: User) -> bool:
    """Cada um edita o próprio perfil; o administrador edita qualquer um (no Django Admin)."""
    if not is_staff_member(user):
        return False
    return user.pk == person.pk or is_admin(user)


def can_access_admin(user: AnyUser) -> bool:
    """Django Admin: contas, papéis, taxonomia, configurações e auditoria (docs/02).

    Espelha User.is_staff, que o save() deriva do papel; aqui a regra fica legível e
    também recusa conta desativada.
    """
    return is_admin(user)


def can_anonymize(user: AnyUser) -> bool:
    """Anonimizar uma conta da equipe ou o crédito de um aluno (docs/23): só o administrador.

    Mesma linha da matriz que configurações e auditoria.
    """
    return is_admin(user)


def can_export_user_data(user: AnyUser, person: User) -> bool:
    """Baixar os dados de uma conta (docs/23, "Acesso"): a própria pessoa ou o administrador."""
    if not is_staff_member(user):
        return False
    return user.pk == person.pk or is_admin(user)


def is_editor(user: AnyUser) -> bool:
    """Editor ou admin: papéis são hierárquicos (admin ⊃ editor ⊃ staff)."""
    return is_staff_member(user) and user.role in (User.Role.EDITOR, User.Role.ADMIN)


def is_admin(user: AnyUser) -> bool:
    return is_staff_member(user) and user.role == User.Role.ADMIN


def is_author(user: AnyUser, article: Article) -> bool:
    """Autor ou coautor da publicação: os dois têm as mesmas permissões de edição."""
    if not is_staff_member(user):
        return False
    return article.contributors.filter(
        user=user, role__in=ArticleContributor.EDITING_ROLES
    ).exists()


def reviewer_credit(article: Article) -> ArticleContributor | None:
    """O colega designado para revisar (há no máximo um por vez; docs/04)."""
    return (
        article.contributors.filter(role=ArticleContributor.Role.REVIEWER, user__isnull=False)
        .select_related("user")
        .first()
    )


def is_designated_reviewer(user: AnyUser, article: Article) -> bool:
    if not is_staff_member(user):
        return False
    return article.contributors.filter(user=user, role=ArticleContributor.Role.REVIEWER).exists()


def can_create_article(user: AnyUser) -> bool:
    return is_staff_member(user)


def can_duplicate(user: AnyUser, article: Article) -> bool:
    """Duplicar como rascunho: autores e editores. O revisor edita o texto durante a revisão,
    mas não leva uma cópia (com os créditos dos alunos) para uma publicação dele."""
    if not can_create_article(user):
        return False
    return is_editor(user) or is_author(user, article)


def can_view(user: AnyUser, article: Article) -> bool:
    """Publicado: todo mundo. Outros estados: autores, revisor designado e editores."""
    if article.status == Article.Status.PUBLISHED:
        return True
    return is_editor(user) or is_author(user, article) or is_designated_reviewer(user, article)


def can_react(user: AnyUser, article: Article) -> bool:
    """Reagir a uma publicação publicada: todo mundo, o visitante pelo cookie anônimo (docs/20).

    Com a configuração reactions.require_login ligada, só quem entrou no sistema.
    """
    if article.status != Article.Status.PUBLISHED:
        return False
    return is_staff_member(user) or not get_setting("reactions.require_login")


def comments_open(article: Article) -> bool:
    """O formulário de comentário aparece: publicada, comentários ligados no site e no texto."""
    return (
        article.status == Article.Status.PUBLISHED
        and article.comments_enabled
        and bool(get_setting("comments.enabled"))
    )


def can_comment(user: AnyUser, article: Article) -> bool:
    """Comentar em público: todo mundo, sem conta; o comentário vai para a moderação (docs/20)."""
    return comments_open(article)


def can_reply_comment(user: AnyUser, article: Article) -> bool:
    """Responder a um comentário público, em nome da equipe: autores e coautores da publicação,
    editor e admin. O revisor designado não responde (a linha da matriz é 🔒, sem 🟡)."""
    return is_editor(user) or is_author(user, article)


def can_moderate_comments(user: AnyUser, article: Article) -> bool:
    """Aprovar, rejeitar e editar o nome de comentários públicos (docs/20, "Quem modera"):
    autores e coautores da publicação, editor e admin. O revisor designado não modera."""
    return is_editor(user) or is_author(user, article)


def can_toggle_comments(user: AnyUser, article: Article) -> bool:
    """Abrir ou fechar os comentários de uma publicação: quem assina o texto e editores."""
    return is_editor(user) or is_author(user, article)


def can_edit(user: AnyUser, article: Article) -> bool:
    """Autores e editores; o revisor designado também, enquanto a revisão está com ele."""
    if is_editor(user) or is_author(user, article):
        return True
    return article.status == Article.Status.IN_REVIEW and is_designated_reviewer(user, article)


# Estados de onde o autor publica sozinho (em revisão, precisa cancelar o pedido antes).
AUTHOR_PUBLISH_FROM = (Article.Status.DRAFT, Article.Status.CHANGES_REQUESTED)


def can_publish(user: AnyUser, article: Article) -> bool:
    if article.status == Article.Status.PUBLISHED:
        return False
    if is_editor(user):
        return True
    # "never" (reservado): toda publicação precisa de outra pessoa (docs/02, "Política editorial").
    if get_setting("editorial.self_publish") == "never":
        return False
    return article.status in AUTHOR_PUBLISH_FROM and is_author(user, article)


# --- revisão por colega (docs/04, docs/17) ---


def can_request_review(user: AnyUser, article: Article) -> bool:
    """Pedir revisão (ou reenviar depois de alterações sugeridas): autores e editores."""
    if article.status not in (Article.Status.DRAFT, Article.Status.CHANGES_REQUESTED):
        return False
    return is_editor(user) or is_author(user, article)


def can_be_reviewer(member: AnyUser, article: Article) -> bool:
    """Qualquer colega ativo, menos quem assina o texto: ninguém revisa o próprio texto."""
    return is_staff_member(member) and not is_author(member, article)


def can_cancel_review(user: AnyUser, article: Article) -> bool:
    if article.status != Article.Status.IN_REVIEW:
        return False
    return is_editor(user) or is_author(user, article)


def can_review(user: AnyUser, article: Article) -> bool:
    """Sugerir alterações ou aprovar: revisor designado, editor e admin, nunca um autor."""
    if article.status != Article.Status.IN_REVIEW or is_author(user, article):
        return False
    return is_editor(user) or is_designated_reviewer(user, article)


def can_approve_and_publish(user: AnyUser, article: Article) -> bool:
    """Aprovar e publicar: editor, ou revisor a quem o autor deu "pode publicar por mim"."""
    if not can_review(user, article):
        return False
    if is_editor(user):
        return True
    return article.contributors.filter(
        user=user, role=ArticleContributor.Role.REVIEWER, can_publish=True
    ).exists()


def can_comment_on_review(user: AnyUser, article: Article) -> bool:
    """Comentário interno da revisão (E32): autores, revisor designado e editores."""
    return is_editor(user) or is_author(user, article) or is_designated_reviewer(user, article)


def can_resolve_comment(user: AnyUser, article: Article) -> bool:
    """Resolver ou reabrir um comentário da revisão: revisor ou autor (docs/17); editores
    também, porque veem e comentam em qualquer texto."""
    return can_comment_on_review(user, article)


def can_decline_review(user: AnyUser, article: Article) -> bool:
    """Recusar a revisão: só o próprio revisor designado."""
    return article.status == Article.Status.IN_REVIEW and is_designated_reviewer(user, article)


def can_resume(user: AnyUser, article: Article) -> bool:
    """Retomar como rascunho depois de alterações sugeridas: autores e editores."""
    if article.status != Article.Status.CHANGES_REQUESTED:
        return False
    return is_editor(user) or is_author(user, article)


def can_archive(user: AnyUser, article: Article) -> bool:
    if article.status == Article.Status.ARCHIVED:
        return False
    return is_editor(user) or is_author(user, article)


def archive_requires_note(user: AnyUser, article: Article) -> bool:
    """Editor ou admin arquivando texto alheio precisa explicar o motivo."""
    return is_editor(user) and not is_author(user, article)


def can_restore(user: AnyUser, article: Article) -> bool:
    if article.status != Article.Status.ARCHIVED:
        return False
    return is_editor(user) or is_author(user, article)


def can_edit_credits(user: AnyUser, article: Article) -> bool:
    """O revisor edita o texto, mas não os créditos: se achar erro, comenta (docs/17)."""
    return is_editor(user) or is_author(user, article)


def can_upload_media(user: AnyUser) -> bool:
    return is_staff_member(user)


def can_edit_media(user: AnyUser, asset: MediaAsset) -> bool:
    """Metadados da imagem: quem enviou, autores da publicação onde ela está, ou editor."""
    if is_editor(user):
        return True
    if not is_staff_member(user):
        return False
    if asset.uploaded_by_id == user.pk:
        return True
    return asset.article_id is not None and is_author(user, asset.article)


def can_access_editorial(user: AnyUser) -> bool:
    """Painel editorial (/painel/editorial/): visão geral, alertas e todas as publicações."""
    return is_editor(user)


def can_reassign_reviewer(user: AnyUser, article: Article) -> bool:
    """Trocar o revisor de um texto em revisão (revisão parada, colega ausente): editor+."""
    return article.status == Article.Status.IN_REVIEW and is_editor(user)


def can_feature(user: AnyUser) -> bool:
    """Definir destaques da home."""
    return is_editor(user)


def can_edit_pages(user: AnyUser) -> bool:
    """Editar e publicar as páginas institucionais (Sobre, Privacidade, Como participar)."""
    return is_editor(user)
