import os
from dotenv import load_dotenv

# Cargar las variables del archivo .env
load_dotenv()

class Config:
    # Llave secreta para las sesiones (cookies, login, etc.)
    SECRET_KEY = os.getenv("SECRET_KEY", "super_secreto_por_defecto")
    
    # URL de conexión a MongoDB Atlas
    MONGO_URI = os.getenv("MONGO_URI")
    
    # Ruta donde se guardarán los archivos subidos (como en el chat o documentos)
    UPLOAD_FOLDER = os.path.join("static", "uploads")