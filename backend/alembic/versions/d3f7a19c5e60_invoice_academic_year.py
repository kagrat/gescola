"""academic year on invoices (AU-28)

Revision ID: d3f7a19c5e60
Revises: 9c5e2b7a41d8
"""
import sqlalchemy as sa
from alembic import op

revision = "d3f7a19c5e60"
down_revision = "9c5e2b7a41d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Établissements créés depuis la migration précédente sans année : on la fige
    # (même règle que 9c5e2b7a41d8). `tenants` n'est pas soumise à la RLS.
    op.execute(
        """
        UPDATE tenants SET academic_year =
            CASE WHEN extract(month FROM now()) >= 9
                 THEN extract(year FROM now())::int || '-' || (extract(year FROM now())::int + 1)
                 ELSE (extract(year FROM now())::int - 1) || '-' || extract(year FROM now())::int
            END
        WHERE academic_year IS NULL
        """
    )
    # Aucun passage d'année n'a pu avoir lieu avant la v22/v23 sur des factures :
    # toutes les factures existantes appartiennent à l'année courante de leur
    # établissement. `invoices` est sous RLS (FORCE) : rattrapage tenant par tenant.
    op.add_column("invoices", sa.Column("academic_year", sa.String(9), nullable=True))
    conn = op.get_bind()
    for tenant_id, year in conn.execute(sa.text("SELECT id, academic_year FROM tenants")).all():
        conn.execute(sa.text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)})
        conn.execute(sa.text("UPDATE invoices SET academic_year = :y WHERE tenant_id = :t"), {"y": year, "t": tenant_id})
    op.alter_column("invoices", "academic_year", nullable=False)  # échoue bruyamment si une ligne a échappé
    op.create_index("ix_invoices_tenant_year", "invoices", ["tenant_id", "academic_year"])
    # Rapports d'assiduité bornés par date.
    op.create_index("ix_attendances_tenant_date", "attendances", ["tenant_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_attendances_tenant_date", table_name="attendances")
    op.drop_index("ix_invoices_tenant_year", table_name="invoices")
    op.drop_column("invoices", "academic_year")
