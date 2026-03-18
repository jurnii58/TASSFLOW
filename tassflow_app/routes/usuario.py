from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
from bson.objectid import ObjectId
from datetime import datetime
from tassflow_app.database import tareas_col, documentos_col, usuarios_col

usuario_bp = Blueprint('usuario', __name__)

@usuario_bp.route("/usuario")
def usuario_panel():
    # Validamos que sí sea un usuario normal
    if session.get("rol") != "usuario":
        return redirect(url_for("auth.login"))

    nombre_usuario = session.get("usuario")
    empresa_id = session.get("empresa_id")

    # === EL FILTRO DOBLE ===
    # 1. Que la tarea le pertenezca a la empresa donde trabaja
    # 2. Que su nombre esté en la lista de asignados a esa tarea
    filtro_estricto = {
        "usuarios": nombre_usuario,
        "empresa_id": ObjectId(empresa_id) if empresa_id else None
    }

    # Buscamos solo sus tareas con ese filtro
    mis_tareas = list(tareas_col.find(filtro_estricto).sort("fecha_creacion", -1))
    
    # Contadores rápidos para su pantalla
    pendientes = sum(1 for t in mis_tareas if t.get("estado") == "Pendiente")
    completadas = sum(1 for t in mis_tareas if t.get("estado") == "Completada")

    return render_template(
        "usuario_panel.html", 
        tareas=mis_tareas,
        pendientes=pendientes,
        completadas=completadas
    )

# ==============================================================
# RUTA PARA ACTUALIZAR ESTADO (DRAG & DROP)
# ==============================================================
@usuario_bp.route('/api/actualizar_estado/<id>', methods=['POST'])
def actualizar_estado(id):
    # Verificamos sesión
    if not session.get('usuario') or session.get('rol') != 'usuario':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    try:
        data = request.get_json()
        nuevo_estado = data.get('estado')
        
        # Log de depuración: Verás esto en tu terminal negra de VS Code
        print(f"--- SOLICITUD RECIBIDA ---")
        print(f"Tarea ID: {id} -> Nuevo Estado: {nuevo_estado}")

        # Lista de estados válidos
        estados_validos = ["Pendiente", "En Proceso", "Completada"]
        
        if nuevo_estado in estados_validos:
            resultado = tareas_col.update_one(
                {'_id': ObjectId(id)},
                {'$set': {'estado': nuevo_estado}}
            )
            
            if resultado.modified_count > 0:
                print("Resultado: Base de datos actualizada con éxito.")
            else:
                print("Resultado: El estado ya era el mismo o no se encontró el ID.")
                
            return jsonify({'success': True})
        else:
            print(f"Error: Estado '{nuevo_estado}' no es válido.")
            return jsonify({'success': False, 'error': 'Estado no válido'}), 400

    except Exception as e:
        print(f"ERROR CRÍTICO EN PYTHON: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==============================================================
# OTRAS FUNCIONES DEL PANEL
# ==============================================================
@usuario_bp.route("/cambiar_prioridad/<tarea_id>", methods=["POST"])
def cambiar_prioridad(tarea_id):
    if session.get("rol") != "usuario": return redirect(url_for("auth.login"))
    
    nueva_prioridad = request.form.get("prioridad")
    tareas_col.update_one({"_id": ObjectId(tarea_id)}, {"$set": {"prioridad": nueva_prioridad}})
    return redirect(url_for("usuario.usuario_panel"))

@usuario_bp.route("/solicitar_documento/<tarea_id>", methods=["POST"])
def solicitar_documento(tarea_id):
    if session.get("rol") != "usuario": return redirect(url_for("auth.login"))
    
    nombre_doc = request.form.get("nombre_documento")
    motivo = request.form.get("descripcion")
    tarea = tareas_col.find_one({"_id": ObjectId(tarea_id)})
    
    documentos_col.insert_one({
        "tarea_id": ObjectId(tarea_id),
        "tarea_titulo": tarea["titulo"] if tarea else "Desconocida",
        "usuario": session["usuario"],
        "nombre_documento": nombre_doc,
        "motivo": motivo,
        "estado": "Pendiente",
        "fecha_solicitud": datetime.now()
    })
    flash("Solicitud de documento enviada.")
    return redirect(url_for("usuario.usuario_panel"))

@usuario_bp.route("/usuario/calendario")
def usuario_calendario():
    if session.get("rol") != "usuario": return redirect(url_for("auth.login"))
    
    usuario_actual = session["usuario"]
    tareas = list(tareas_col.find({"usuarios": usuario_actual}))
    
    eventos = []
    for t in tareas:
        if t.get("estado") == "Completada": color = "#30d158" # Verde
        elif t.get("estado") == "En Proceso": color = "#ff9f0a" # Naranja
        else: color = "#ff453a" # Rojo
            
        eventos.append({
            "title": t["titulo"],
            "start": t.get("fecha_creacion").strftime("%Y-%m-%d") if t.get("fecha_creacion") else datetime.now().strftime("%Y-%m-%d"),
            "color": color,
            "extendedProps": { "estado": t.get("estado", "Pendiente") }
        })
        
    return render_template("usuario_calendario.html", eventos=eventos)

@usuario_bp.route("/usuario/documentos")
def mis_documentos():
    if session.get("rol") != "usuario": return redirect(url_for("auth.login"))
    documentos = list(documentos_col.find({"usuario": session["usuario"]}).sort("fecha_solicitud", -1))
    return render_template("usuario_documentos.html", documentos=documentos)

# ==============================================================
# RUTA PARA EDITAR TAREA
# ==============================================================
@usuario_bp.route('/api/obtener_tarea_editar/<tarea_id>', methods=['GET'])
def obtener_tarea_editar(tarea_id):
    """Obtiene los datos de la tarea y lista de usuarios para edit modal"""
    if not session.get('usuario') or session.get('rol') != 'usuario':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    try:
        tarea = tareas_col.find_one({'_id': ObjectId(tarea_id)})
        if not tarea:
            return jsonify({'success': False, 'error': 'Tarea no encontrada'}), 404
        
        # Obtener todos los usuarios (excluir campos sensibles)
        usuarios = list(usuarios_col.find({}, {'usuario': 1, '_id': 0}).sort('usuario', 1))
        lista_usuarios = [u['usuario'] for u in usuarios]
        
        return jsonify({
            'success': True,
            'tarea': {
                '_id': str(tarea['_id']),
                'titulo': tarea.get('titulo', ''),
                'descripcion': tarea.get('descripcion', ''),
                'usuarios': tarea.get('usuarios', [])
            },
            'todos_usuarios': lista_usuarios
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@usuario_bp.route('/api/guardar_tarea_editar/<tarea_id>', methods=['POST'])
def guardar_tarea_editar(tarea_id):
    """Guarda los cambios de la tarea editada"""
    if not session.get('usuario') or session.get('rol') != 'usuario':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    try:
        data = request.get_json()
        titulo = data.get('titulo', '').strip()
        descripcion = data.get('descripcion', '').strip()
        usuarios = data.get('usuarios', [])
        
        if not titulo:
            return jsonify({'success': False, 'error': 'El título es requerido'}), 400
        
        # Actualizar la tarea
        resultado = tareas_col.update_one(
            {'_id': ObjectId(tarea_id)},
            {'$set': {
                'titulo': titulo,
                'descripcion': descripcion,
                'usuarios': usuarios
            }}
        )
        
        if resultado.modified_count > 0 or resultado.matched_count > 0:
            return jsonify({'success': True, 'message': 'Tarea actualizada correctamente'})
        else:
            return jsonify({'success': False, 'error': 'No se pudo actualizar la tarea'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500