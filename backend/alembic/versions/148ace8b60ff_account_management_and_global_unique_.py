"""account management and global unique email

Revision ID: 6c1d2a9e5b70
Revises: 01f9bb49f978
"""
from alembic import op
import sqlalchemy as sa

revision = '6c1d2a9e5b70'
down_revision = '01f9bb49f978'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. L'e-mail devient unique DANS TOUTE LA PLATEFORME, sans tenir compte de la
    #    casse : la connexion identifie un compte par son seul e-mail, donc deux
    #    comptes de même adresse (dans deux établissements) rendaient la connexion
    #    impossible pour les deux. Si des doublons existent déjà, on s'arrête avec
    #    un message explicite plutôt que de choisir à la place de l'exploitant.
    duplicates = op.get_bind().execute(
        sa.text("SELECT lower(email) AS email, count(*) AS n FROM users GROUP BY lower(email) HAVING count(*) > 1 LIMIT 10")
    ).fetchall()
    if duplicates:
        listing = ", ".join(f"{row.email} ({row.n} comptes)" for row in duplicates)
        raise RuntimeError(
            "Migration interrompue : des adresses e-mail sont utilisées par plusieurs comptes (" + listing + "). "
            "Corrigez ces doublons (modifiez ou supprimez les comptes en trop) puis relancez la migration."
        )
    op.execute("CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email))")

    # 2. Gestion des comptes.
    #    must_change_password : mot de passe provisoire à remplacer à la première connexion.
    #    session_version      : incrémenté à chaque changement/réinitialisation de mot de passe,
    #                           désactivation ou réinitialisation MFA ; les jetons d'accès portent
    #                           cette version, ce qui les invalide immédiatement (et non à leur expiration).
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "session_version")
    op.drop_column("users", "must_change_password")
    op.execute("DROP INDEX IF EXISTS uq_users_email_lower")
