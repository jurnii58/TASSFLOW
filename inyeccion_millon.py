from pymongo import MongoClient
import random
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print(" Error: Variable de entorno MONGO_URI no encontrada. Configura tu .env o entorno.")
    exit(1)

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')  # Prueba la conexión
    print(" Conexión a MongoDB exitosa.")
except Exception as e:
    print(f" Error de conexión a MongoDB: {e}")
    exit(1)

db = client["carga_mental_db"]  
tareas_col = db["tareas"]

TOTAL_TAREAS = 1000000 
LOTE = 5000

estados = ["Pendiente", "En Proceso", "Completada"]
prioridades = ["Baja", "Media", "Alta"]
usuarios = ["admin", "empleado", "luis.antonio", "jurni"]

print(f" Iniciando inyección masiva: {TOTAL_TAREAS} tareas en TaskFlow...")
tiempo_inicio = time.time()

for i in range(0, TOTAL_TAREAS, LOTE):
    lote_tareas = []
    for j in range(LOTE):
        lote_tareas.append({
            "titulo": f"Tarea de Rendimiento #{i + j + 1}",
            "descripcion": "Registro generado para prueba de estrés de Apache Spark.",
            "estado": random.choice(estados),
            "prioridad": random.choice(prioridades),
            "usuarios": random.choice(usuarios),
            "fecha_creacion": datetime.now() - timedelta(days=random.randint(0, 30))
        })
    
    tareas_col.insert_many(lote_tareas)
    print(f" {i + LOTE} tareas inyectadas en la base de datos...")

print("==================================================")
print(f" Inyección completada en {(time.time() - tiempo_inicio):.2f} segundos.")
print("==================================================")