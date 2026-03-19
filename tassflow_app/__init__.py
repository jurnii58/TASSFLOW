from flask import Flask
import os
from datetime import datetime, timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from .config import Config

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"], # Límites generales por IP
    storage_uri="memory://"
)

def create_app(config_class=Config):
    # Inicializamos la aplicación
    app = Flask(__name__)
    
    app.config.from_object(config_class)

    # Si la pestaña queda inactiva por 30 minutos, la sesión muere automáticamente
    app.permanent_session_lifetime = timedelta(minutes=30)
    
    # Conectamos el escudo antibloqueo a nuestra aplicación
    limiter.init_app(app)

    # Datos globales disponibles en todas las plantillas
    @app.context_processor
    def inject_globals():
        return {"now": datetime.now()}

    # Crear la carpeta de uploads automáticamente si no existe en tu computadora
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # IMPORTAR Y REGISTRAR LAS RUTAS (BLUEPRINTS)
    # Importamos las rutas aquí adentro para evitar "importaciones circulares"
    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.usuario import usuario_bp
    from .routes.chat import chat_bp

    # Le decimos a la app que use estas rutas
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(usuario_bp)
    app.register_blueprint(chat_bp)

    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return app
