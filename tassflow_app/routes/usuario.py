from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
import math
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import requests
from tassflow_app.database import tareas_col, documentos_col, usuarios_col, db

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
# RUTA MÓVIL: OBTENER TAREAS DE USUARIO
# ============================================================== 
@usuario_bp.route("/api/mobile_tareas/<nombre_usuario>", methods=["GET"])
def mobile_tareas(nombre_usuario):
    tareas_db = list(db["tareas"].find({
        "usuarios": nombre_usuario,
        "estado": {"$ne": "Completada"}
    }).sort("fecha_creacion", -1))

    lista_tareas = []
    for t in tareas_db:
        lista_tareas.append({
            "id": str(t["_id"]),
            "titulo": t.get("titulo", "Sin título"),
            "descripcion": t.get("descripcion", ""),
            "prioridad": t.get("prioridad", "Media"),
            "estado": t.get("estado", "Pendiente")
        })

    return jsonify({"success": True, "tareas": lista_tareas}), 200

# ==============================================================
# OTRAS FUNCIONES DEL PANEL
# ==============================================================
@usuario_bp.route("/cambiar_prioridad/<tarea_id>", methods=["POST"])
def cambiar_prioridad(tarea_id):
    if session.get("rol") != "usuario":
        return redirect(url_for("auth.login"))

    nueva_prioridad = request.form.get("prioridad")
    usuario_id = session.get("usuario_id")
    
    # 🛡️ EL COACH DE SALUD (ESCUDO PROTECTOR) 🛡️
    # Si el empleado intenta echarse encima una tarea pesada...
    if nueva_prioridad == "Alta" and usuario_id:
        # Revisamos cómo está su corazón en este momento
        ultimo_bpm = db["registro_biometrico"].find_one(
            {"usuario_id": ObjectId(usuario_id)},
            sort=[("fecha", -1)]
        )
        
        # Si su corazón está acelerado (Cámbialo a 70 temporalmente para hacer la prueba)
        if ultimo_bpm and ultimo_bpm.get("ritmo_cardiaco_promedio", 0) >= 100:
            flash(
                f"⚠️ Alerta de Salud: Tu ritmo cardíaco actual es de {ultimo_bpm['ritmo_cardiaco_promedio']} BPM. "
                "Por tu bienestar, el sistema recomienda no asumir tareas de alta carga mental en este momento. "
                "Tómate un respiro.",
                "error"
            )
            return redirect(request.referrer or url_for("usuario.usuario_panel")) # Cancelamos el cambio y la regresamos a su tablero
    # =========================================================

    # Si todo está bien (o si eligió Baja/Media), actualizamos la tarea normal
    tareas_col.update_one(
        {"_id": ObjectId(tarea_id)},
        {"$set": {"prioridad": nueva_prioridad}}
    )
    
    flash("Prioridad actualizada correctamente", "success")
    return redirect(request.referrer or url_for("usuario.usuario_panel"))

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

@usuario_bp.route("/api/sincronizar_fit", methods=["POST"])
def sincronizar_google_fit():
    # 1. Verificamos que sea un usuario válido
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"error": "No autorizado"}), 401

    # 2. El Token de Permiso (La "Llave" del usuario)
    # Nota: En un flujo real, el usuario te da este token al darle clic a "Iniciar sesión con Google"
    access_token = request.json.get("google_access_token")
    if not access_token:
        return jsonify({"error": "Falta el token de Google Fit"}), 400

    # 3. Configuramos la máquina del tiempo (Queremos los datos de las últimas 24 horas)
    ahora = int(datetime.now().timestamp() * 1000)
    ayer = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)

    # 4. Preparamos la "llamada telefónica" a la API de Google
    url_google_fit = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
    
    cabeceras = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Le decimos a Google exactamente qué datos queremos (com.google.heart_rate.bpm)
    cuerpo_peticion = {
        "aggregateBy": [{
            "dataTypeName": "com.google.heart_rate.bpm"
        }],
        "bucketByTime": { "durationMillis": 86400000 }, # Agrupado por 1 día (en milisegundos)
        "startTimeMillis": ayer,
        "endTimeMillis": ahora
    }

    # 5. ¡Hacemos la llamada!
    respuesta = requests.post(url_google_fit, headers=cabeceras, json=cuerpo_peticion)
    
    if respuesta.status_code != 200:
        return jsonify({"error": "Google rechazó la conexión", "detalles": respuesta.text}), 400

    datos_fit = respuesta.json()

    # 6. Extraemos el ritmo cardíaco de la maraña de datos que nos manda Google
    try:
        # Navegamos por el JSON de Google para sacar el promedio (fpVal)
        ritmo_promedio = datos_fit['bucket'][0]['dataset'][0]['point'][0]['value'][0]['fpVal']
    except (IndexError, KeyError):
        return jsonify({"error": "No hay datos de ritmo cardíaco registrados hoy"}), 404

    # 7. Guardamos el dato biométrico en MongoDB
    db["registro_biometrico"].insert_one({
        "usuario_id": ObjectId(usuario_id),
        "ritmo_cardiaco_promedio": round(ritmo_promedio, 1),
        "origen": "Google Fit API",
        "fecha": datetime.now()
    })

    return jsonify({
        "mensaje": "Sincronización exitosa", 
        "bpm": round(ritmo_promedio, 1)
    }), 200

@usuario_bp.route('/api/predict_burnout/<usuario_id>', methods=['POST'])
def predict_burnout(usuario_id):
    datos = request.get_json() or {}

    A = float(datos.get('tasa_entrada', 2.0))
    k = float(datos.get('eficiencia', 0.15))
    UMBRAL_COLAPSO = 10.0

    saturacion_maxima = A / k if k != 0 else float('inf')
    dias_proyeccion = 15
    proyeccion_futura = []
    alerta_disparada = False
    dia_critico = None

    for t in range(1, dias_proyeccion + 1):
        y_t = (1 - saturacion_maxima) * math.exp(-k * t) + saturacion_maxima
        proyeccion_futura.append({
            "dia": t,
            "tareas_acumuladas": round(y_t, 2)
        })
        if y_t >= UMBRAL_COLAPSO and not alerta_disparada:
            alerta_disparada = True
            dia_critico = t

    if saturacion_maxima >= UMBRAL_COLAPSO:
        status = "RIESGO CRÍTICO"
        mensaje = (
            f"ALERTA PREDICTIVA: El empleado alcanzará el límite de colapso ({UMBRAL_COLAPSO} tareas) "
            f"en el DÍA {dia_critico if dia_critico else 'desconocido'}. "
            f"Su saturación perpetua será de {round(saturacion_maxima, 1)} tareas. Se requiere intervención."
        )
    else:
        status = "SALUDABLE"
        mensaje = (
            f"Operación estable. El empleado se estabilizará matemáticamente en un máximo de "
            f"{round(saturacion_maxima, 1)} tareas pendientes."
        )

    return jsonify({
        "usuario_id": usuario_id,
        "diagnostico": {
            "estado": status,
            "mensaje_gerencial": mensaje,
            "saturacion_limite": round(saturacion_maxima, 2)
        },
        "datos_grafica": proyeccion_futura
    }), 200