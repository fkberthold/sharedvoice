"""Contract: the authorization matrix — the no-unprotected-route guard (sv-dkl.5).

Final child of the auth epic ``sv-dkl``. Every other auth bead pinned ONE surface
(the User DAO, the session deps, the /auth router, the gated reads). This bead
pins the WHOLE access policy in one place, and — crucially — does it by
*introspecting the running app* so that a route added in the future WITHOUT a
gate fails here automatically, not only if someone remembers to update a list.

Two layers:

1. An explicit policy matrix (anonymous / member / curator x routes), which
   documents the intended access rules as readable rows.
2. ``test_no_unprotected_route`` — the load-bearing guard. It walks the app's
   real served route table and asserts every route that is not in the public
   ``EXEMPT`` allowlist rejects an anonymous caller. Adding an ungated route, or
   weakening a gate, breaks this test.

Policy (from the auth design drawer "SharedVoice — Accounts & Auth design + epic
sv-dkl"): gate EVERYTHING except ``/health`` and the auth entry points; an
anonymous visitor sees only the login/register wall. Per the "lock them down"
decision on this bead, FastAPI's auto-exposed ``/openapi.json`` + ``/docs`` +
``/redoc`` are DISABLED in ``create_app`` — a private, one-community app must not
hand an anonymous visitor a map of its entire API surface.

The curator-only row uses a probe route (``POST /_probe/curator-only`` guarded by
``require_curator``) because ``sv-lds.7`` — the first real curator-only endpoint
(root upload) — has not merged yet. WHEN sv-lds.7 LANDS: replace the probe with
its real route and add a row for it here.

Everything runs through a real ``TestClient`` against the real app, router, and
session cookies (no mocks) — the matrix is also the integration test.
"""

from __future__ import annotations

import re

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from starlette.routing import Route

from sharedvoice.app import create_app
from sharedvoice.dependencies import require_curator

JOIN_CODE = "test-join-code"

# Routes that are PUBLIC by design. Everything else must reject anonymous
# callers. Keep this list tiny and commented — it is the whole trust boundary.
EXEMPT = {
    "/health",          # liveness probe, intentionally unauthenticated
    "/auth/register",   # the way in (join-code gated inside the handler)
    "/auth/login",      # the way in
    "/auth/logout",     # safe idempotent no-op even without a session
}


def _app(tmp_path):
    return create_app(db_path=tmp_path / "t.db", storage_root=tmp_path / "blobs")


def _register(client, username, *, join_code=JOIN_CODE, password="pw"):
    return client.post(
        "/auth/register",
        json={
            "join_code": join_code,
            "username": username,
            "display_name": username.title(),
            "password": password,
        },
    )


def _three_actors(app):
    """Return (anon, member, curator) clients over one app/DB.

    Registration order is load-bearing: the FIRST registrant becomes the curator
    (``count_users == 0``), so ``curator`` registers before ``member``.
    """
    anon = TestClient(app)
    curator = TestClient(app)
    assert _register(curator, "tarpa").status_code == 201
    member = TestClient(app)
    assert _register(member, "member").status_code == 201
    return anon, member, curator


# --- fixtures -------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    return _app(tmp_path)


@pytest.fixture
def actors(app):
    return _three_actors(app)


# --- explicit policy matrix ----------------------------------------------

# Gated reads: anonymous is refused on every one.
GATED_READS = [
    ("GET", "/affirmations"),
    ("GET", "/affirmations/waking"),
    ("GET", "/affirmations/waking/root"),
    ("GET", "/auth/me"),
]


@pytest.mark.parametrize("method,path", GATED_READS)
def test_anonymous_is_refused_on_every_gated_route(actors, method, path):
    anon, _member, _curator = actors
    assert anon.request(method, path).status_code == 401


# Authenticated actors (member AND curator) get past the gate identically on the
# read surface; the member/curator split only shows up on curator-only routes
# (exercised separately below). Root is 404 because no root recording is seeded.
AUTHED_READS = [
    ("GET", "/affirmations", 200),
    ("GET", "/affirmations/waking", 200),
    ("GET", "/affirmations/waking/root", 404),
    ("GET", "/auth/me", 200),
]


@pytest.mark.parametrize("actor", ["member", "curator"])
@pytest.mark.parametrize("method,path,expected", AUTHED_READS)
def test_authenticated_actor_passes_the_gate(actors, actor, method, path, expected):
    anon, member, curator = actors
    client = member if actor == "member" else curator
    assert client.request(method, path).status_code == expected


def test_health_is_public_for_anonymous(actors):
    anon, _member, _curator = actors
    assert anon.get("/health").status_code == 200


def test_auth_entry_points_reachable_without_a_session(tmp_path):
    # register / login must not be gated — they are the way IN. Prove it end to
    # end: a fresh anonymous client registers, then a *different* fresh client
    # logs in with those creds. Neither is blocked by a require-session gate.
    app = _app(tmp_path)
    assert _register(TestClient(app), "newcomer", password="s3cret").status_code == 201
    login = TestClient(app).post(
        "/auth/login", json={"username": "newcomer", "password": "s3cret"}
    )
    assert login.status_code == 200


# --- curator-only enforcement (probe until sv-lds.7 lands) ----------------

def _app_with_curator_probe(tmp_path):
    app = _app(tmp_path)

    @app.post("/_probe/curator-only")
    def _curator_only(user=Depends(require_curator)) -> dict:  # pragma: no cover
        return {"ok": True}

    return app


def test_curator_only_route_enforces_the_role(tmp_path):
    # anon -> 401 (no session), member -> 403 (authed but not curator),
    # curator -> 200. Stands in for sv-lds.7's root upload until it merges.
    app = _app_with_curator_probe(tmp_path)
    anon, member, curator = _three_actors(app)
    assert anon.post("/_probe/curator-only").status_code == 401
    assert member.post("/_probe/curator-only").status_code == 403
    assert curator.post("/_probe/curator-only").status_code == 200


# --- the gate re-closes on logout ----------------------------------------

def test_logout_returns_a_client_to_anonymous(actors):
    _anon, member, _curator = actors
    assert member.get("/affirmations").status_code == 200
    assert member.post("/auth/logout").status_code == 204
    # Same client, session cleared: back behind the wall.
    assert member.get("/affirmations").status_code == 401
    assert member.get("/auth/me").status_code == 401


# --- the no-unprotected-route guard (the point of the bead) ---------------

def _served_routes(app):
    """Flattened ``(path, methods)`` for EVERY served route.

    FastAPI (0.139) stores ``include_router`` results as opaque ``_IncludedRouter``
    wrappers rather than flattening them into ``app.routes``; the real sub-routes
    hang off ``.original_router.routes``. Recurse through those so the sweep sees
    the auth + affirmations endpoints AND any framework routes (e.g. the auto
    docs), regardless of ``include_in_schema`` — an ``openapi()``-based inventory
    would miss exactly the routes this guard exists to catch.
    """
    out = []

    def walk(routes):
        for r in routes:
            if type(r).__name__ == "_IncludedRouter":
                walk(r.original_router.routes)
            elif isinstance(r, Route):
                out.append((r.path, set(r.methods or ())))

    walk(app.routes)
    return out


def test_no_unprotected_route(tmp_path):
    app = _app(tmp_path)
    routes = _served_routes(app)

    # Guard the guard: if FastAPI's internals change and the walk silently finds
    # nothing, this test must fail LOUD rather than pass vacuously.
    paths = {p for p, _ in routes}
    assert {"/affirmations", "/auth/me"} <= paths, (
        f"route enumeration broke — only discovered {sorted(paths)}"
    )

    anon = TestClient(app)
    unprotected = []
    for path, methods in routes:
        if path in EXEMPT:
            continue
        probe_path = re.sub(r"{[^}]+}", "x", path)
        method = "GET" if "GET" in methods else next(
            iter(methods - {"HEAD", "OPTIONS"}), "GET"
        )
        status = anon.request(method, probe_path).status_code
        if status not in (401, 403):
            unprotected.append((method, path, status))

    assert not unprotected, (
        "these routes are reachable by an anonymous caller and are not in the "
        f"public EXEMPT allowlist: {unprotected}. Either gate the route with "
        "Depends(current_user) / require_curator, or — if it is intentionally "
        "public — add it to EXEMPT with a comment explaining why."
    )


def test_openapi_and_docs_are_not_exposed(tmp_path):
    # 'lock them down' decision (sv-dkl.5): the interactive docs + schema are
    # disabled in create_app so an anonymous visitor cannot enumerate the API.
    anon = TestClient(_app(tmp_path))
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert anon.get(path).status_code == 404, f"{path} must not be served"
