import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

# Cargar las variables del .env
load_dotenv()

# Conexión a MongoDB
client = MongoClient(os.getenv("MONGO_URI"))
db = client["carga_mental_db"]

# Definir las colecciones para exportarlas fácilmente
usuarios_col = db["usuarios"]
tareas_col = db["tareas"]
mensajes_col = db["mensajes"]
documentos_col = db["documentos"]
actividades_col = db["actividades"]
empresas_col = db["empresas"]

# Función global para registrar el historial del administrador
def registrar_actividad(tipo, mensaje):
    actividades_col.insert_one({
        "tipo": tipo,
        "mensaje": mensaje,
        "fecha": datetime.now()
    })