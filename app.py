"""Composition root: wires models, services, controllers, views and routes.

Run:  python app.py        (settings come from .env, see .env.example)
"""
import logging

from config import Config
from controllers.auth_controller import AuthController
from controllers.health_controller import HealthController
from controllers.resource_controller import ResourceController
from core.application import Application
from core.router import Router
from core.server import HttpServer
from middleware.bearer_auth import BearerAuth
from models.database import Database
from models.resource_repository import ResourceRepository
from models.token import TokenRepository
from resources import discover, ensure_unique
from services.auth_service import AuthService
from views.error_view import ErrorView
from views.health_view import HealthView
from views.resource_view import ResourceView
from views.token_view import TokenView


def build_application(config: Config, resources=None) -> Application:
    log = logging.getLogger("app")
    resources = discover() if resources is None else list(resources)
    ensure_unique(resources)

    # Models
    db = Database(config.db_path)
    tokens = TokenRepository(db)
    tokens.create_table()

    # Services & middleware
    auth = AuthService(tokens, config.client_id, config.client_secret, config.token_ttl,
                       static_token=config.static_token)
    require_token = BearerAuth(auth)

    # Fixed routes
    auth_ctrl = AuthController(auth, TokenView())
    router = (Router()
              .get("/health", HealthController(HealthView()).index)
              .add("GET", "/auth/token", auth_ctrl.token)
              .add("POST", "/auth/token", auth_ctrl.token))

    # One generic endpoint per Resource
    for resource in resources:
        repository = ResourceRepository(db, resource)
        repository.create_table()
        controller = ResourceController(resource, repository, ResourceView())
        router.post(resource.path, controller.store,
                    middleware=[require_token] if resource.protected else [])
        log.info("Registered POST %s (table %s, extra keys: %s)",
                 resource.path, resource.table, resource.extra)

    return Application(router, ErrorView())


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    config = Config.from_env()
    if config.uses_default_secret:
        logging.warning("Using the default CLIENT_SECRET. Copy .env.example to .env and set your own.")
    if config.static_token and len(config.static_token) < 24:
        logging.warning("STATIC_ACCESS_TOKEN is short. Use at least 24 random characters.")
    app = build_application(config)
    server = HttpServer(app, config.host, config.port, config.max_body_bytes)
    logging.info("Listening on http://%s:%s", config.host, server.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()