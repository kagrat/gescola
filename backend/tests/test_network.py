from app.models.user import UserRole


def test_super_admin_can_provision_network_and_admin(client, make_user, auth_headers):
    super_admin, pwd = make_user(role=UserRole.SUPER_ADMIN)
    headers = auth_headers(super_admin, pwd)

    network_resp = client.post("/api/v1/networks", json={"name": "Groupe La Colombe", "code": "colombe-group"}, headers=headers)
    assert network_resp.status_code == 201
    network = network_resp.json()

    admin_resp = client.post(
        f"/api/v1/networks/{network['id']}/admins",
        json={"email": "promoteur@colombe.bj", "password": "Str0ng#Passw0rd!", "full_name": "M. Le Promoteur"},
        headers=headers,
    )
    assert admin_resp.status_code == 201
    assert admin_resp.json()["role"] == "network_admin"
    assert admin_resp.json()["tenant_id"] is None


def test_non_super_admin_cannot_manage_networks(client, make_user, auth_headers):
    admin, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    resp = client.post("/api/v1/networks", json={"name": "X", "code": "x"}, headers=auth_headers(admin, pwd))
    assert resp.status_code == 403


def test_network_overview_aggregates_across_schools(client, make_user, make_tenant, make_network, auth_headers):
    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)
    super_headers = auth_headers(super_admin, pwd_super)

    network = make_network(name="Groupe Test")
    tenant_a = make_tenant(name="École A")
    tenant_b = make_tenant(name="École B")
    client.post(f"/api/v1/networks/{network.id}/tenants/{tenant_a.id}", headers=super_headers)
    client.post(f"/api/v1/networks/{network.id}/tenants/{tenant_b.id}", headers=super_headers)

    admin_a, pwd_a = make_user(tenant=tenant_a, role=UserRole.SCHOOL_ADMIN)
    admin_b, pwd_b = make_user(tenant=tenant_b, role=UserRole.SCHOOL_ADMIN)
    headers_a = auth_headers(admin_a, pwd_a)
    headers_b = auth_headers(admin_b, pwd_b)

    # École A : 1 élève, facture 100000 payée 40000
    student_a = client.post("/api/v1/students", json={"first_name": "A", "last_name": "A"}, headers=headers_a).json()
    invoice_a = client.post(
        "/api/v1/invoices", json={"student_id": student_a["id"], "label": "Scolarité", "amount_due": 100000, "due_date": "2026-10-01"},
        headers=headers_a,
    ).json()
    client.post("/api/v1/payments", json={"invoice_id": invoice_a["id"], "amount": 40000, "method": "cash"}, headers=headers_a)

    # École B : 2 élèves, facture 50000 payée intégralement
    client.post("/api/v1/students", json={"first_name": "B1", "last_name": "B"}, headers=headers_b)
    student_b2 = client.post("/api/v1/students", json={"first_name": "B2", "last_name": "B"}, headers=headers_b).json()
    invoice_b = client.post(
        "/api/v1/invoices", json={"student_id": student_b2["id"], "label": "Scolarité", "amount_due": 50000, "due_date": "2026-10-01"},
        headers=headers_b,
    ).json()
    client.post("/api/v1/payments", json={"invoice_id": invoice_b["id"], "amount": 50000, "method": "cash"}, headers=headers_b)

    network_admin, pwd_net = make_user(network=network, role=UserRole.NETWORK_ADMIN)
    net_headers = auth_headers(network_admin, pwd_net)

    overview = client.get("/api/v1/network/overview", headers=net_headers)
    assert overview.status_code == 200
    data = overview.json()

    assert data["network"]["name"] == "Groupe Test"
    assert data["totals"]["school_count"] == 2
    assert data["totals"]["active_students"] == 3
    assert data["totals"]["revenue_due"] == 150000.0
    assert data["totals"]["revenue_collected"] == 90000.0

    schools_by_name = {s["name"]: s for s in data["schools"]}
    assert schools_by_name["École A"]["active_students"] == 1
    assert schools_by_name["École A"]["revenue_collected"] == 40000.0
    assert schools_by_name["École B"]["active_students"] == 2
    assert schools_by_name["École B"]["recovery_rate_percent"] == 100.0


def test_network_admin_sees_only_own_network(client, make_user, make_tenant, make_network, auth_headers):
    super_admin, pwd_super = make_user(role=UserRole.SUPER_ADMIN)
    super_headers = auth_headers(super_admin, pwd_super)

    network_1 = make_network(name="Réseau 1")
    network_2 = make_network(name="Réseau 2")
    tenant_1 = make_tenant(name="École du réseau 1")
    tenant_2 = make_tenant(name="École du réseau 2")
    client.post(f"/api/v1/networks/{network_1.id}/tenants/{tenant_1.id}", headers=super_headers)
    client.post(f"/api/v1/networks/{network_2.id}/tenants/{tenant_2.id}", headers=super_headers)

    admin_1, pwd_admin_1 = make_user(network=network_1, role=UserRole.NETWORK_ADMIN)
    overview = client.get("/api/v1/network/overview", headers=auth_headers(admin_1, pwd_admin_1))
    assert overview.status_code == 200
    names = [s["name"] for s in overview.json()["schools"]]
    assert names == ["École du réseau 1"]


def test_school_admin_cannot_access_network_overview(client, make_user, auth_headers):
    admin, pwd = make_user(role=UserRole.SCHOOL_ADMIN)
    resp = client.get("/api/v1/network/overview", headers=auth_headers(admin, pwd))
    assert resp.status_code == 403


def test_network_admin_without_network_returns_404(client, make_user, auth_headers):
    """Cas défensif : un compte network_admin sans network_id (ne devrait pas
    arriver via le flux normal de création, mais l'API doit rester sûre)."""
    orphan_admin, pwd = make_user(role=UserRole.NETWORK_ADMIN)  # network=None
    resp = client.get("/api/v1/network/overview", headers=auth_headers(orphan_admin, pwd))
    assert resp.status_code == 404


def test_class_creation_includes_cycle(client, make_tenant, make_user, auth_headers):
    tenant = make_tenant()
    admin, pwd = make_user(tenant=tenant, role=UserRole.SCHOOL_ADMIN)
    headers = auth_headers(admin, pwd)

    resp = client.post("/api/v1/classes", json={"name": "Petite Section B", "level": "Petite Section", "cycle": "maternelle"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["cycle"] == "maternelle"

    default_resp = client.post("/api/v1/classes", json={"name": "CM1 B", "level": "CM1"}, headers=headers)
    assert default_resp.status_code == 201
    assert default_resp.json()["cycle"] == "primaire"
