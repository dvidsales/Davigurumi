"""Create only a fresh, private beta schema and restricted role. No existing data touched."""

import getpass
import os
import psycopg
from psycopg import sql

host = input("Host do session pooler Supabase: ").strip()
user = input("Usuário administrador do session pooler (postgres.PROJECT_REF): ").strip()
port = input("Porta [5432]: ").strip() or "5432"
admin_password = getpass.getpass("Senha do administrador (entrada oculta): ")
app_password = getpass.getpass(
    "Nova senha forte da conta davigurumi (entrada oculta): "
)
if len(app_password) < 24:
    raise SystemExit("Use uma senha aleatória de pelo menos 24 caracteres.")
if getpass.getpass("Confirme a nova senha: ") != app_password:
    raise SystemExit("As senhas não coincidem.")
with psycopg.connect(
    host=host,
    port=port,
    user=user,
    password=admin_password,
    dbname="postgres",
    sslmode="verify-full",
    sslrootcert=os.getenv("POSTGRES_SSLROOTCERT", "system"),
    connect_timeout=15,
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='davigurumi'")
        if cursor.fetchone():
            raise SystemExit("A conta já existe. Nenhuma senha ou schema foi alterado.")
        cursor.execute(
            sql.SQL(
                "CREATE ROLE davigurumi LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Literal(app_password))
        )
        # Managed PostgreSQL administrators can create roles without being able
        # to SET ROLE to them. Temporarily grant membership inside this transaction.
        cursor.execute("SELECT current_user")
        administrator = cursor.fetchone()[0]
        cursor.execute(
            sql.SQL("GRANT davigurumi TO {}").format(sql.Identifier(administrator))
        )
        cursor.execute("CREATE SCHEMA davigurumi AUTHORIZATION davigurumi")
        cursor.execute("REVOKE ALL ON SCHEMA davigurumi FROM PUBLIC")
        cursor.execute(
            "SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')"
        )
        for (name,) in cursor.fetchall():
            cursor.execute(
                sql.SQL("REVOKE ALL ON SCHEMA davigurumi FROM {}").format(
                    sql.Identifier(name)
                )
            )
        cursor.execute(
            sql.SQL("REVOKE davigurumi FROM {}").format(sql.Identifier(administrator))
        )
print(
    "Conta restrita e schema privado criados. Configure a nova senha somente no ambiente seguro do Render."
)
