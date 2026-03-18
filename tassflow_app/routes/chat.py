from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, current_app
from bson.objectid import ObjectId
from datetime import datetime
import os
from werkzeug.utils import secure_filename

# Importamos las colecciones correctas desde tu database.py
from tassflow_app.database import tareas_col, mensajes_col

chat_bp = Blueprint('chat', __name__)

@chat_bp.route("/chat/<tarea_id>")
def ver_chat(tarea_id):
    if not session.get('usuario'):
        return redirect(url_for("auth.login"))
    
    tarea = tareas_col.find_one({"_id": ObjectId(tarea_id)})
    # Si la tarea no existe, redirigimos para evitar errores
    if not tarea:
        return redirect(url_for("auth.login"))

    mensajes = list(
        mensajes_col.find({"tarea_id": ObjectId(tarea_id)}).sort("fecha", 1)
    )
    return render_template("chat.html", tarea=tarea, mensajes=mensajes)

@chat_bp.route("/enviar_mensaje/<tarea_id>", methods=["POST"])
def enviar_mensaje(tarea_id):
    if not session.get('usuario'):
        return redirect(url_for("auth.login"))
    
    archivo = request.files.get("archivo")
    texto = request.form.get("mensaje")

    mensaje_doc = {
        "tarea_id": ObjectId(tarea_id),
        "usuario": session["usuario"],
        "texto": texto,
        "fecha": datetime.now(),
        "archivo": None
    }

    if archivo and archivo.filename:
        nombre = secure_filename(archivo.filename)
        # Aseguramos que el nombre sea único con un timestamp
        nombre_final = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{nombre}"
        ruta = os.path.join(current_app.config["UPLOAD_FOLDER"], nombre_final)
        archivo.save(ruta)
        
        mensaje_doc["archivo"] = {
            "nombre": nombre_final,
            "tipo": archivo.content_type,
            "url": f"/static/uploads/{nombre_final}"
        }

    mensajes_col.insert_one(mensaje_doc)
    return redirect(url_for("chat.ver_chat", tarea_id=tarea_id))

@chat_bp.route("/obtener_mensajes/<tarea_id>")
def obtener_mensajes(tarea_id):
    try:
        # Intentamos buscar por ObjectId (estándar de tu app)
        query = {"tarea_id": ObjectId(tarea_id)}
        mensajes = list(mensajes_col.find(query).sort("fecha", 1))
    except Exception:
        # Fallback por si el ID llega como string puro
        mensajes = list(mensajes_col.find({"tarea_id": tarea_id}).sort("fecha", 1))

    lista = []
    for m in mensajes:
        archivo_info = None
        if m.get("archivo"):
            if isinstance(m["archivo"], dict):
                archivo_info = {
                    "url": m["archivo"].get("url"),
                    "nombre": m["archivo"].get("nombre"),
                    "tipo": m["archivo"].get("tipo")
                }
            else:
                archivo_info = {
                    "url": f"/static/uploads/{m['archivo']}",
                    "nombre": m[ "archivo"],
                    "tipo": None
                }

        fecha = m.get("fecha")
        if isinstance(fecha, datetime):
            fecha = fecha.isoformat()

        lista.append({
            "usuario": m.get("usuario"),
            "texto": m.get("texto"),
            "archivo": archivo_info,
            "fecha": fecha
        })

    return jsonify(lista)