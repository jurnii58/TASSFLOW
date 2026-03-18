#!/usr/bin/env python3
"""
Script para insertar 5,000 registros de prueba en logs_seguridad
para probar la funcionalidad de bitácora de seguridad.
"""

import random
import sys
import os
from datetime import datetime, timedelta

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tassflow_app.database import db

def generar_ip_aleatoria():
    """Genera una IP aleatoria"""
    return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"

def generar_usuario_aleatorio():
    """Genera un nombre de usuario aleatorio"""
    nombres = ["admin", "root", "user", "test", "guest", "administrator", "system", "backup", "webmaster", "support"]
    dominios = ["", "123", "admin", "2024", "test", "_backup", ".old", "2", "copy", "temp"]

    nombre_base = random.choice(nombres)
    dominio = random.choice(dominios)

    return f"{nombre_base}{dominio}"

def generar_fecha_aleatoria():
    """Genera una fecha aleatoria en los últimos 30 días"""
    dias_atras = random.randint(0, 30)
    horas_atras = random.randint(0, 23)
    minutos_atras = random.randint(0, 59)

    fecha = datetime.now() - timedelta(days=dias_atras, hours=horas_atras, minutes=minutos_atras)
    return fecha

def generar_alerta_aleatoria():
    """Genera una alerta aleatoria"""
    alertas = [
        "Intento de inicio de sesión fallido",
        "Intento de acceso no autorizado",
        "Credenciales incorrectas",
        "Usuario bloqueado temporalmente",
        "IP sospechosa detectada",
        "Múltiples intentos fallidos",
        "Acceso desde ubicación inusual"
    ]
    return random.choice(alertas)

def insertar_logs_prueba():
    """Inserta 5,000 registros de prueba en logs_seguridad"""

    print("🚀 Iniciando inserción de 5,000 registros de prueba...")

    # Limpiar logs existentes para empezar limpio
    print("🧹 Limpiando logs existentes...")
    db["logs_seguridad"].delete_many({})

    registros_insertados = 0

    # Insertar en lotes de 500 para mejor rendimiento
    lote_size = 500
    total_lotes = 5000 // lote_size

    for lote in range(total_lotes):
        documentos = []

        for _ in range(lote_size):
            documento = {
                "ip_origen": generar_ip_aleatoria(),
                "usuario_intentado": generar_usuario_aleatorio(),
                "fecha_intento": generar_fecha_aleatoria(),
                "alerta": generar_alerta_aleatoria()
            }
            documentos.append(documento)

        # Insertar el lote completo
        resultado = db["logs_seguridad"].insert_many(documentos)
        registros_insertados += len(resultado.inserted_ids)

        print(f"✅ Lote {lote + 1}/{total_lotes} completado - Total: {registros_insertados} registros")

    # Verificar que se insertaron todos
    total_en_db = db["logs_seguridad"].count_documents({})
    print(f"\n🎯 Verificación final:")
    print(f"   - Registros insertados: {registros_insertados}")
    print(f"   - Registros en base de datos: {total_en_db}")

    if total_en_db == 5000:
        print("✅ ¡Éxito! Todos los 5,000 registros se insertaron correctamente.")
    else:
        print("❌ Error: No se insertaron todos los registros.")

    # Mostrar algunos ejemplos
    print("\n📋 Ejemplos de registros insertados:")
    ejemplos = list(db["logs_seguridad"].find().limit(5))
    for i, ejemplo in enumerate(ejemplos, 1):
        print(f"   {i}. IP: {ejemplo['ip_origen']} | Usuario: {ejemplo['usuario_intentado']} | Alerta: {ejemplo['alerta']}")

if __name__ == "__main__":
    try:
        insertar_logs_prueba()
    except Exception as e:
        print(f"❌ Error durante la inserción: {e}")
        sys.exit(1)