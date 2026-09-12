from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections
from django.db.migrations.executor import MigrationExecutor


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
