import os
from datetime import datetime
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
import database as db
from app.models import User

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to access this page."
login_manager.login_message_category = "warning"
csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    login_manager.init_app(app)
    csrf.init_app(app)

    # Ensure reports directory exists
    os.makedirs(app.config["REPORTS_DIR"], exist_ok=True)

    # Initialize MongoDB collections and default admin account
    db.init_db()

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.prediction import prediction_bp
    from app.routes.code_analysis import code_analysis_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(prediction_bp)
    app.register_blueprint(code_analysis_bp)
    app.register_blueprint(admin_bp)

    # Context processors for global template variables
    @app.context_processor
    def inject_global_template_vars():
        conn_info = db.get_connection_info()
        return {
            "current_year": datetime.now().year,
            "app_title": "CodeDefect AI",
            "mongodb_connected": conn_info.get("connected", False),
            "mongodb_target": conn_info.get("target", "None")
        }

    return app
