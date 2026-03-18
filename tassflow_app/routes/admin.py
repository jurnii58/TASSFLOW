from flask import Blueprint, render_template, request, redirect, send_file, url_for, session, flash, current_app
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import re
import os

# Librerías para gráficos y PDF
from fpdf import FPDF
import matplotlib.pyplot as plt
from io import BytesIO

from werkzeug.security import generate_password_hash

from tassflow_app.database import (
    usuarios_col, tareas_col, mensajes_col, 
    actividades_col, registrar_actividad, db, empresas_col
)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/crear_usuario", methods=["POST"])
def crear_usuario():
    # Cadenero actualizado
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    password = request.form["contrasena"]
    usuario_nombre = request.form["usuario"]
    
    # LÓGICA DE CONTROL DE ROL:
    # Si eres "admin" normal: siempre creas "usuario" (sin opción)
    # Si eres "director": puedes elegir entre "admin" o "usuario"
    if session.get("rol") == "admin":
        # Los admins normales NO pueden elegir rol: siempre usuario
        rol_solicitado = "usuario"
    else:
        # El director sí puede elegir
        rol_solicitado = request.form.get("rol", "usuario")

    regex = r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    if not re.match(regex, password):
        flash("La contraseña debe tener: 8 caracteres, una mayúscula, un número y un símbolo (@$!%*?&).")
        return redirect(url_for("admin.admin_panel"))

    empresa_del_jefe = session.get("empresa_id")

    usuarios_col.insert_one({
        "nombre_usuario": usuario_nombre,
        "contrasena": generate_password_hash(password),
        "rol": rol_solicitado,  # <--- Guardamos el rol definido por la lógica arriba
        "activo": True,
        "solicitud_reset": False,
        "empresa_id": ObjectId(empresa_del_jefe) if empresa_del_jefe else None 
    })
    
    registrar_actividad("creacion", f"Nuevo {rol_solicitado} registrado: {usuario_nombre}")
    return redirect(url_for("admin.admin_panel"))

@admin_bp.route("/eliminar_usuario/<id>")
def eliminar_usuario(id):
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    usuario = usuarios_col.find_one({"_id": ObjectId(id)})
    if usuario:
        tareas_col.update_many({}, {"$pull": {"usuarios": usuario["nombre_usuario"]}})
        usuarios_col.delete_one({"_id": ObjectId(id)})
        registrar_actividad("eliminacion", f"Acceso revocado al usuario: {usuario['nombre_usuario']}")

    return redirect(url_for("admin.admin_panel"))

@admin_bp.route("/asignar_tarea", methods=["POST"])
def asignar_tarea():
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    usuarios = request.form.getlist("usuarios")
    titulo = request.form["titulo"]
    
    if not (1 <= len(usuarios) <= 2):
        flash("Selecciona 1 o 2 usuarios")
        return redirect(url_for("admin.admin_panel"))

    # === EL TRUCO SAAS: Sacamos la empresa ===
    empresa_del_jefe = session.get("empresa_id")

    tareas_col.insert_one({
        "titulo": titulo,
        "descripcion": request.form["descripcion"],
        "usuarios": usuarios,
        "estado": "Pendiente",
        "prioridad": "Media",
        "fecha_creacion": datetime.now(),
        # Tatuamos la tarea con la empresa
        "empresa_id": ObjectId(empresa_del_jefe) if empresa_del_jefe else None 
    })
    
    registrar_actividad("creacion", f"Nueva tarea asignada: '{titulo}'")
    return redirect(url_for("admin.admin_panel"))

@admin_bp.route('/eliminar_tarea/<tarea_id>')
def eliminar_tarea(tarea_id):
    # Permitimos el paso si es admin O si es el director
    if session.get('rol') not in ['admin', 'director']:
        return redirect(url_for('auth.login'))
    
    tarea = tareas_col.find_one({'_id': ObjectId(tarea_id)})
    if tarea:
        tareas_col.delete_one({'_id': ObjectId(tarea_id)})
        mensajes_col.delete_many({'tarea_id': ObjectId(tarea_id)}) 
        registrar_actividad("eliminacion", f"Tarea eliminada permanentemente: '{tarea.get('titulo', 'Sin título')}'")
    
    flash("Tarea eliminada correctamente.")
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route("/admin/estadisticas")
def admin_estadisticas():
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    # === EL MURO INVISIBLE DE LA EMPRESA ===
    empresa_id = session.get("empresa_id")
    filtro_empresa = {"empresa_id": ObjectId(empresa_id)} if empresa_id else {}
    filtro_usuarios = {"rol": "usuario"}
    if empresa_id:
        filtro_usuarios["empresa_id"] = ObjectId(empresa_id)

    total_usuarios = usuarios_col.count_documents(filtro_usuarios)
    total_tareas = tareas_col.count_documents(filtro_empresa)
    tareas_pendientes = tareas_col.count_documents({"estado": "Pendiente", **filtro_empresa})
    tareas_completadas = tareas_col.count_documents({"estado": "Completada", **filtro_empresa})

    # Métricas adicionales para dashboard
    carga_por_usuario = round(tareas_pendientes / total_usuarios, 2) if total_usuarios else 0.0
    tareas_en_riesgo = tareas_pendientes  # placeholder: tareas pendientes como 'en riesgo'
    tasa_eficiencia = round((tareas_completadas / total_tareas) * 100, 1) if total_tareas else 0.0

    # =========================================================
    # MODELADO DINÁMICO DE ECUACIONES DIFERENCIALES (CÁLCULO)
    # y(t) = (y0 - A/k) * e^(-kt) + A/k
    # =========================================================
    y0 = tareas_pendientes  # Variable de estado inicial (Tareas actuales)
    A = 2.0  # Tasa constante de entrada (Supongamos 2 tareas nuevas al día)
    k = 0.15  # Coeficiente constante (El equipo resuelve el 15% de la carga al día)

    tiempos = list(range(0, 16))  # Proyección a 15 días (t)
    proyeccion = []
    for t in tiempos:
        carga_t = (y0 - (A / k)) * (2.71828 ** (-k * t)) + (A / k)
        proyeccion.append(max(0, carga_t))  # max(0) evita tareas negativas

    # Pasar datos al frontend para generar gráficos con Chart.js
    return render_template(
        "admin_estadisticas.html",
        total_usuarios=total_usuarios,
        total_tareas=total_tareas,
        tareas_pendientes=tareas_pendientes,
        tareas_completadas=tareas_completadas,
        carga_por_usuario=carga_por_usuario,
        tareas_en_riesgo=tareas_en_riesgo,
        tasa_eficiencia=tasa_eficiencia,
        now=datetime.now(),
        y0=y0,
        tiempos=tiempos,
        proyeccion=proyeccion
    )

@admin_bp.route("/admin/seguridad")
def admin_seguridad():
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    # Obtener métricas de seguridad
    total_logs = db["logs_seguridad"].count_documents({})
    logs_ultima_hora = db["logs_seguridad"].count_documents({
        "fecha_intento": {"$gte": datetime.now() - timedelta(hours=1)}
    })
    logs_ultimas_24h = db["logs_seguridad"].count_documents({
        "fecha_intento": {"$gte": datetime.now() - timedelta(hours=24)}
    })
    
    # Obtener logs recientes para mostrar en la tabla
    logs_recientes = list(db["logs_seguridad"].find().sort("fecha_intento", -1).limit(50))

    return render_template(
        "admin_seguridad.html",
        total_logs=total_logs,
        logs_ultima_hora=logs_ultima_hora,
        logs_ultimas_24h=logs_ultimas_24h,
        logs_recientes=logs_recientes
    )

@admin_bp.route("/editar_tarea/<tarea_id>", methods=["POST"])
def editar_tarea(tarea_id):
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    titulo = request.form["titulo"]
    descripcion = request.form["descripcion"]
    usuarios = request.form.getlist("usuarios")
    
    if not (1 <= len(usuarios) <= 2):
        flash("Selecciona 1 o 2 usuarios para la tarea editada.")
        return redirect(url_for("admin.admin_panel"))

    tareas_col.update_one(
        {"_id": ObjectId(tarea_id)},
        {"$set": {"titulo": titulo, "descripcion": descripcion, "usuarios": usuarios}}
    )
    
    registrar_actividad("info", f"Tarea editada: '{titulo}'")
    flash("Tarea actualizada correctamente.")
    return redirect(url_for("admin.admin_panel"))

@admin_bp.route("/resetear_password/<id>", methods=["POST"])
def resetear_password(id):
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))
    
    nueva_clave = request.form["nueva_clave"]
    regex = r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    if not re.match(regex, nueva_clave):
        flash("Error: La nueva contraseña debe tener 8 caracteres, una mayúscula, un número y un símbolo.")
        return redirect(url_for("admin.admin_panel"))

    usuario = usuarios_col.find_one({"_id": ObjectId(id)})
    if usuario:
        usuarios_col.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"contrasena": generate_password_hash(nueva_clave), "solicitud_reset": False}}
        )
        registrar_actividad("alerta", f"Contraseña restablecida por administrador para: {usuario['nombre_usuario']}")

    flash("Contraseña actualizada con éxito.")
    return redirect(url_for("admin.admin_panel"))

@admin_bp.route("/admin")
def admin_panel():
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    # Obtenemos el ID de la empresa de este jefe
    empresa_id = session.get("empresa_id")
    
    # Preparamos los filtros mágicos
    filtro_empresa = {"empresa_id": ObjectId(empresa_id)} if empresa_id else {}
    
    # Filtro para usuarios (Rol usuario + de esta empresa)
    filtro_usuarios = {"rol": "usuario"}
    if empresa_id:
        filtro_usuarios["empresa_id"] = ObjectId(empresa_id)

    # Las búsquedas ahora llevan el filtro por dentro
    historial = list(actividades_col.find(filtro_empresa).sort("fecha", -1).limit(50))
    logs_seguridad = list(db["logs_seguridad"].find().sort("fecha_intento", -1).limit(20))

    return render_template(
        "admin_panel.html",
        # Aplicamos los filtros a las listas
        usuarios=list(usuarios_col.find(filtro_usuarios)),
        tareas=list(tareas_col.find(filtro_empresa).sort("fecha_creacion", -1).limit(30)),
        
        # Aplicamos los filtros a los contadores numéricos
        total_usuarios=usuarios_col.count_documents(filtro_usuarios),
        total_tareas=tareas_col.count_documents(filtro_empresa),
        tareas_pendientes=tareas_col.count_documents({"estado": "Pendiente", **filtro_empresa}),
        tareas_completadas=tareas_col.count_documents({"estado": "Completada", **filtro_empresa}),
        
        actividades=historial,
        logs_seguridad=logs_seguridad
    )
# ==============================================================
# ÚNICA RUTA DE REPORTE PDF (Con rutas absolutas blindadas)
# ==============================================================
@admin_bp.route("/descargar_reporte")
def descargar_reporte():
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    # === EL MURO INVISIBLE DE LA EMPRESA ===
    empresa_id = session.get("empresa_id")
    filtro_empresa = {"empresa_id": ObjectId(empresa_id)} if empresa_id else {}
    filtro_usuarios = {"rol": "usuario"}
    if empresa_id:
        filtro_usuarios["empresa_id"] = ObjectId(empresa_id)

    total_usuarios = usuarios_col.count_documents(filtro_usuarios)
    total_tareas = tareas_col.count_documents(filtro_empresa)
    pendientes = tareas_col.count_documents({"estado": "Pendiente", **filtro_empresa})
    completadas = tareas_col.count_documents({"estado": "Completada", **filtro_empresa})
    
    tasa_eficiencia = (completadas / total_tareas * 100) if total_tareas > 0 else 0

    # Crear PDF ejecutivo
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()

    # === ENCABEZADO EJECUTIVO ===
    pdf.set_fill_color(250, 250, 250)
    pdf.rect(0, 0, 210, 35, 'F')

    # Linea azul sutil
    pdf.set_draw_color(100, 150, 200)
    pdf.set_line_width(0.3)
    pdf.line(0, 35, 210, 35)

    # Titulo ejecutivo
    pdf.set_text_color(60, 60, 60)
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 15, "TASSFLOW", ln=True, align='C')

    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "REPORTE EJECUTIVO - GESTION DE CARGA MENTAL", ln=True, align='C')
    pdf.ln(2)

    # === FECHA Y REFERENCIA ===
    pdf.set_text_color(80, 80, 80)
    pdf.set_font("Arial", '', 8)
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 4, f"Fecha de emision: {fecha_actual}", ln=True, align='R')
    pdf.cell(0, 4, "Referencia: RF-2026-001", ln=True, align='R')
    pdf.ln(5)

    # === SECCION: RESUMEN EJECUTIVO ===
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "RESUMEN EJECUTIVO", ln=True)
    pdf.ln(2)

    pdf.set_font("Arial", '', 9)
    resumen = f"El presente reporte detalla el rendimiento operativo del sistema Tassflow. "
    resumen += f"El sistema gestiona actualmente {total_tareas} tareas distribuidas entre {total_usuarios} colaboradores, "
    resumen += f"con una tasa de eficiencia del {tasa_eficiencia:.1f}%."

    pdf.multi_cell(0, 4, resumen)
    pdf.ln(3)

    # === SECCION: METRICAS PRINCIPALES ===
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "METRICAS PRINCIPALES", ln=True)
    pdf.ln(2)

    # Tabla ejecutiva
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(245, 245, 245)

    # Encabezados
    pdf.cell(70, 7, "Indicador", border=1, fill=True, align='L')
    pdf.cell(30, 7, "Valor", border=1, fill=True, align='C')
    pdf.cell(50, 7, "Estado", border=1, fill=True, align='C')
    pdf.cell(40, 7, "Tendencia", border=1, fill=True, align='C')
    pdf.ln()

    # Datos
    metrics = [
        ("Empleados Activos", str(total_usuarios), "Normal", "Estable"),
        ("Total Tareas", str(total_tareas), "Historico", "Estable"),
        ("Tareas Pendientes", str(pendientes), "Atencion", "Subiendo" if pendientes > completadas else "Estable"),
        ("Tareas Completadas", str(completadas), "Excelente", "Estable"),
        ("Eficiencia General", f"{tasa_eficiencia:.1f}%", "Buena" if tasa_eficiencia >= 70 else "Mejorable", "Mejorando" if tasa_eficiencia >= 70 else "Estable")
    ]

    pdf.set_font("Arial", '', 8)
    for i, (indicador, valor, estado, tendencia) in enumerate(metrics):
        fill_color = (250, 250, 250) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_color)

        pdf.cell(70, 6, indicador, border=1, fill=True)
        pdf.cell(30, 6, valor, border=1, align='C', fill=True)

        # Color del estado
        if estado == "Atencion":
            pdf.set_text_color(200, 120, 0)
        elif estado == "Excelente":
            pdf.set_text_color(0, 150, 50)
        else:
            pdf.set_text_color(0, 0, 0)

        pdf.cell(50, 6, estado, border=1, align='C', fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(40, 6, tendencia, border=1, align='C', fill=True)
        pdf.ln()

    pdf.ln(5)

    # === SECCION: ANALISIS Y RECOMENDACIONES ===
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "ANALISIS Y RECOMENDACIONES", ln=True)
    pdf.ln(2)

    pdf.set_font("Arial", '', 9)

    # Analisis basado en datos
    if pendientes > completadas:
        pdf.set_text_color(200, 120, 0)
        pdf.cell(5, 4, "-", 0, 0)
        pdf.cell(0, 4, "Se recomienda optimizar la distribucion de carga de trabajo para reducir tareas pendientes.", ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_text_color(0, 150, 50)
        pdf.cell(5, 4, "-", 0, 0)
        pdf.cell(0, 4, "Excelente balance en la gestion de tareas. Mantener las practicas actuales.", ln=True)
        pdf.set_text_color(0, 0, 0)

    if tasa_eficiencia < 70:
        pdf.set_text_color(200, 120, 0)
        pdf.cell(5, 4, "-", 0, 0)
        pdf.cell(0, 4, "Implementar estrategias para mejorar la tasa de eficiencia operativa.", ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_text_color(0, 150, 50)
        pdf.cell(5, 4, "-", 0, 0)
        pdf.cell(0, 4, "La eficiencia operativa se encuentra en niveles optimos.", ln=True)
        pdf.set_text_color(0, 0, 0)

    pdf.ln(3)

    # === CONCLUSION ===
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "CONCLUSION", ln=True)
    pdf.ln(1)

    pdf.set_font("Arial", '', 9)
    conclusion = "El sistema Tassflow continua operando de manera eficiente, proporcionando "
    conclusion += "herramientas efectivas para la gestion de carga mental organizacional. "
    conclusion += "Los indicadores presentados demuestran un rendimiento operativo satisfactorio."

    pdf.multi_cell(0, 4, conclusion)

    # === PIE DE PAGINA EJECUTIVO ===
    pdf.set_y(-25)
    pdf.set_font("Arial", 'I', 7)
    pdf.set_text_color(120, 120, 120)

    # Linea sutil
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.2)
    pdf.line(10, pdf.get_y() - 2, 200, pdf.get_y() - 2)

    pdf.ln(3)
    pdf.cell(0, 3, "Tassflow Analytics - Sistema de Gestion de Carga Mental", ln=True, align='C')
    pdf.cell(0, 3, "Documento confidencial - Para distribucion interna unicamente", ln=True, align='C')
    pdf.cell(0, 3, f"Pagina 1 de 1 - Generado el {fecha_actual}", ln=True, align='C')

    # Guardar PDF con ruta absoluta
    # Obtener el directorio base de la aplicación
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.join(base_dir, "static", "uploads")
    
    # Crear la carpeta si no existe
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Construir la ruta absoluta del archivo
    ruta_pdf = os.path.join(uploads_dir, "Reporte_Ejecutivo_Tassflow.pdf")
    
    # Guardar el PDF
    pdf.output(ruta_pdf)

    registrar_actividad("info", "Reporte PDF ejecutivo descargado por administrador")

    return send_file(ruta_pdf, as_attachment=True, mimetype='application/pdf', download_name='Reporte_Ejecutivo_Tassflow.pdf')

@admin_bp.route("/descargar_reporte_seguridad")
def descargar_reporte_seguridad():
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    # === EL MURO INVISIBLE DE LA EMPRESA ===
    empresa_id = session.get("empresa_id")
    filtro_empresa = {"empresa_id": ObjectId(empresa_id)} if empresa_id else {}

    # Obtener métricas de seguridad (con filtro de empresa)
    total_logs = db["logs_seguridad"].count_documents(filtro_empresa)
    logs_ultima_hora = db["logs_seguridad"].count_documents({
        "fecha_intento": {"$gte": datetime.now() - timedelta(hours=1)},
        **filtro_empresa
    })
    logs_ultimas_24h = db["logs_seguridad"].count_documents({
        "fecha_intento": {"$gte": datetime.now() - timedelta(hours=24)},
        **filtro_empresa
    })
    
    # Obtener tipos de alertas más comunes
    alertas_count = {}
    for log in db["logs_seguridad"].find(filtro_empresa, {"alerta": 1}):
        alerta = log.get("alerta", "Desconocida")
        alertas_count[alerta] = alertas_count.get(alerta, 0) + 1
    
    alertas_comunes = sorted(alertas_count.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Obtener IPs más activas
    ips_count = {}
    for log in db["logs_seguridad"].find({}, {"ip_origen": 1}):
        ip = log.get("ip_origen", "Desconocida")
        ips_count[ip] = ips_count.get(ip, 0) + 1
    
    ips_mas_activas = sorted(ips_count.items(), key=lambda x: x[1], reverse=True)[:5]

    # Crear PDF ejecutivo de seguridad
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()

    # === ENCABEZADO EJECUTIVO ===
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(0, 0, 210, 40, 'F')

    # Titulo ejecutivo
    pdf.set_text_color(60, 60, 60)
    pdf.set_font("Arial", 'B', 24)
    pdf.set_xy(15, 8)
    pdf.cell(120, 10, "TASSFLOW", ln=False, align='L')

    # Fecha y referencia (alineado a la derecha)
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(100, 100, 100)
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.set_xy(15, 20)
    pdf.cell(170, 4, f"Fecha de emisión: {fecha_actual}", ln=True, align='R')
    pdf.set_xy(15, 25)
    pdf.cell(170, 4, "Referencia: RS-2026-001", ln=True, align='R')

    # Subtítulo
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(120, 120, 120)
    pdf.set_xy(15, 32)
    pdf.cell(0, 5, "REPORTE DE SEGURIDAD - SISTEMA DE MONITOREO", ln=True)
    
    pdf.ln(3)

    # === SECCION: RESUMEN EJECUTIVO ===
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "RESUMEN EJECUTIVO DE SEGURIDAD", ln=True)
    pdf.ln(2)

    pdf.set_font("Arial", '', 9)
    resumen = f"El sistema de seguridad de Tassflow ha registrado {total_logs} eventos de seguridad. "
    resumen += f"En las ultimas 24 horas se detectaron {logs_ultimas_24h} incidentes, "
    resumen += f"con {logs_ultima_hora} eventos en la ultima hora."

    pdf.multi_cell(0, 4, resumen)
    pdf.ln(3)

    # === SECCION: METRICAS PRINCIPALES ===
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "METRICAS DE SEGURIDAD", ln=True)
    pdf.ln(2)

    # Tabla ejecutiva
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(245, 245, 245)

    # Encabezados
    pdf.cell(70, 7, "Indicador", border=1, fill=True, align='L')
    pdf.cell(30, 7, "Valor", border=1, fill=True, align='C')
    pdf.cell(50, 7, "Estado", border=1, fill=True, align='C')
    pdf.cell(40, 7, "Tendencia", border=1, fill=True, align='C')
    pdf.ln()

    # Datos
    metrics = [
        ("Total Eventos", str(total_logs), "Historico", "Estable"),
        ("Ultima Hora", str(logs_ultima_hora), "Normal" if logs_ultima_hora < 10 else "Atencion", "Estable"),
        ("Ultimas 24h", str(logs_ultimas_24h), "Normal" if logs_ultimas_24h < 100 else "Atencion", "Estable"),
        ("Alertas Activas", str(len(alertas_comunes)), "Monitoreo", "Estable")
    ]

    pdf.set_font("Arial", '', 8)
    for i, (indicador, valor, estado, tendencia) in enumerate(metrics):
        fill_color = (250, 250, 250) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_color)

        pdf.cell(70, 6, indicador, border=1, fill=True)
        pdf.cell(30, 6, valor, border=1, align='C', fill=True)
        pdf.cell(50, 6, estado, border=1, align='C', fill=True)
        pdf.cell(40, 6, tendencia, border=1, align='C', fill=True)
        pdf.ln()

    pdf.ln(5)

    # === SECCION: ALERTAS MAS COMUNES ===
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "ALERTAS MAS FRECUENTES", ln=True)
    pdf.ln(2)

    if alertas_comunes:
        pdf.set_font("Arial", '', 8)
        for alerta, count in alertas_comunes[:3]:
            pdf.cell(5, 4, "-", 0, 0)
            pdf.cell(0, 4, f"{alerta}: {count} eventos", ln=True)
    else:
        pdf.set_font("Arial", '', 9)
        pdf.cell(0, 4, "No se encontraron alertas registradas.", ln=True)

    pdf.ln(3)

    # === SECCION: IPs MAS ACTIVAS ===
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "DIRECCIONES IP MAS ACTIVAS", ln=True)
    pdf.ln(2)

    if ips_mas_activas:
        pdf.set_font("Arial", '', 8)
        for ip, count in ips_mas_activas[:3]:
            pdf.cell(5, 4, "-", 0, 0)
            pdf.cell(0, 4, f"{ip}: {count} intentos", ln=True)
    else:
        pdf.set_font("Arial", '', 9)
        pdf.cell(0, 4, "No se encontraron direcciones IP registradas.", ln=True)

    pdf.ln(5)

    # === CONCLUSION ===
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "CONCLUSION", ln=True)
    pdf.ln(1)

    pdf.set_font("Arial", '', 9)
    conclusion = "El sistema de seguridad de Tassflow mantiene un monitoreo continuo de actividades "
    conclusion += "sospechosas. Los indicadores presentados muestran el estado actual del sistema de seguridad."

    pdf.multi_cell(0, 4, conclusion)

    # Guardar PDF con ruta absoluta
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.join(base_dir, "static", "uploads")
    
    # Crear la carpeta si no existe
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Construir la ruta absoluta del archivo
    ruta_pdf = os.path.join(uploads_dir, "Reporte_Seguridad_Tassflow.pdf")
    
    # Guardar el PDF
    pdf.output(ruta_pdf)

    registrar_actividad("info", "Reporte PDF de seguridad descargado por administrador")

    return send_file(ruta_pdf, as_attachment=True, mimetype='application/pdf', download_name='Reporte_Seguridad_Tassflow.pdf')

@admin_bp.route("/descargar_reporte_estadisticas")
def descargar_reporte_estadisticas():
    # Permitimos el paso si es admin O si es el director
    if session.get("rol") not in ["admin", "director"]:
        return redirect(url_for("auth.login"))

    # === EL MURO INVISIBLE DE LA EMPRESA ===
    empresa_id = session.get("empresa_id")
    filtro_empresa = {"empresa_id": ObjectId(empresa_id)} if empresa_id else {}
    filtro_usuarios = {"rol": "usuario"}
    if empresa_id:
        filtro_usuarios["empresa_id"] = ObjectId(empresa_id)

    # Obtener métricas de estadísticas (SOLO DE ESTA EMPRESA)
    total_usuarios = usuarios_col.count_documents(filtro_usuarios)
    total_tareas = tareas_col.count_documents(filtro_empresa)
    tareas_pendientes = tareas_col.count_documents({"estado": "Pendiente", **filtro_empresa})
    tareas_completadas = tareas_col.count_documents({"estado": "Completada", **filtro_empresa})
    
    # Calcular métricas adicionales
    tasa_eficiencia = (tareas_completadas / total_tareas * 100) if total_tareas > 0 else 0
    carga_promedio = (total_tareas / total_usuarios) if total_usuarios > 0 else 0

    # Crear directorio uploads si falta (para guardar gráficos temporales)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.join(base_dir, "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    # Generar gráficos con matplotlib y guardarlos en uploads_dir
    labels = ['Pendientes', 'Completadas']
    valores = [tareas_pendientes, tareas_completadas]
    colores = ['#ff9f0a', '#30d158']

    # Gráfico de barras
    fig, ax = plt.subplots(figsize=(4,3))
    ax.bar(labels, valores, color=colores)
    ax.set_title('Volumen de Tareas')
    ax.set_facecolor('#1a1d2d')
    ax.tick_params(colors='#8a91a5')
    ax.spines['bottom'].set_color('#2a2d3d')
    ax.spines['left'].set_color('#2a2d3d')
    buf1 = BytesIO()
    fig.savefig(buf1, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
    buf1.seek(0)
    chart1_path = os.path.join(uploads_dir, 'estadisticas_bar.png')
    with open(chart1_path, 'wb') as f:
        f.write(buf1.getvalue())
    plt.close(fig)

    # Gráfico de rosquilla
    fig, ax = plt.subplots(figsize=(4,3))
    wedges, texts = ax.pie(valores, labels=labels, colors=colores, wedgeprops=dict(width=0.4))
    ax.set_title('Distribución de Estado')
    buf2 = BytesIO()
    fig.savefig(buf2, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
    buf2.seek(0)
    chart2_path = os.path.join(uploads_dir, 'estadisticas_donut.png')
    with open(chart2_path, 'wb') as f:
        f.write(buf2.getvalue())
    plt.close(fig)

    # Crear PDF ejecutivo de estadísticas
    pdf = FPDF('P', 'mm', 'A4')  # Portrait
    pdf.add_page()

    # Colores
    color_header = (51, 51, 51)  # Gris oscuro
    color_title = (10, 132, 255)  # Azul iOS
    color_text = (50, 50, 50)    # Gris oscuro texto
    color_light_text = (150, 150, 150)  # Gris claro

    # Header
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(0, 0, 210, 40, 'F')

    # Título principal
    pdf.set_font('Helvetica', 'B', 24)
    pdf.set_text_color(51, 51, 51)
    pdf.set_xy(15, 8)
    pdf.cell(120, 10, 'TASSFLOW', ln=False)

    # Fecha y referencia (alineado a la derecha)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(100, 100, 100)
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.set_xy(15, 20)
    pdf.cell(170, 4, f'Fecha de emisión: {fecha_actual}', ln=True, align='R')
    pdf.set_xy(15, 25)
    pdf.cell(170, 4, 'Referencia: RF-2026-002', ln=True, align='R')

    # Subtítulo
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(120, 120, 120)
    pdf.set_xy(15, 32)
    pdf.cell(0, 5, 'REPORTE EJECUTIVO - GESTION DE CARGA MENTAL', ln=True)

    # Resumen ejecutivo
    pdf.set_y(50)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 10, 'ESTADO DE LA GESTION: OPTIMIZADO', ln=True)

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    resumen = f'El presente reporte detalla el estado de la gestión de carga mental del sistema Tassflow. '
    resumen += f'El sistema gestiona actualmente {total_tareas} tareas distribuidas entre {total_usuarios} colaboradores, '
    resumen += f'con una tasa de eficiencia del {tasa_eficiencia:.1f}%.'
    pdf.multi_cell(0, 5, resumen)
    pdf.ln(5)

    # Métricas principales
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 8, 'METRICAS PRINCIPALES', ln=True)
    pdf.ln(3)

    # KPIs en tabla
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.set_text_color(51, 51, 51)

    # Headers tabla
    col_widths = [50, 40, 40, 60]
    headers = ['Indicador', 'Valor', 'Estado', 'Tendencia']
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, header, border=1, fill=True, align='C')
    pdf.ln()

    # Datos
    pdf.set_font('Helvetica', '', 9)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(50, 50, 50)

    data = [
        [f'Carga/Usuario', f'{carga_promedio:.1f}', 'Optimo' if carga_promedio <= 5 else 'Atención', 'Estable'],
        [f'Tareas Totales', f'{total_tareas}', 'Activo', 'Creciente'],
        [f'En Riesgo', f'{tareas_pendientes}', 'Atención' if tareas_pendientes > tareas_completadas else 'Normal', 'Descendente' if tareas_pendientes < tareas_completadas else 'Estable'],
        [f'Tasa Eficiencia', f'{tasa_eficiencia:.1f}%', 'Excelente' if tasa_eficiencia >= 80 else 'Buena' if tasa_eficiencia >= 70 else 'Mejorable', 'Mejorando' if tasa_eficiencia >= 70 else 'Estable'],
    ]

    for row in data:
        for i, cell in enumerate(row):
            pdf.cell(col_widths[i], 8, cell, border=1, align='C')
        pdf.ln()

    pdf.ln(5)

    # Gráficas eliminadas - Solo mostrar análisis textual

    # Análisis de gráficos
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 8, 'ANALISIS DE DISTRIBUCION DE TAREAS', ln=True)
    pdf.ln(2)

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    analisis_volumen = f'El volumen de tareas muestra una distribución entre {tareas_pendientes} tareas pendientes '
    analisis_volumen += f'y {tareas_completadas} tareas completadas. La gráfica de barras indica un rendimiento operativo '
    analisis_volumen += f'saludable con una tasa de completitud del {tasa_eficiencia:.1f}%.'
    pdf.multi_cell(0, 5, analisis_volumen)
    pdf.ln(3)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 8, 'ESTADO DE LAS TAREAS', ln=True)
    pdf.ln(2)

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    estado_tareas = f'La distribución por estado revela que el {tasa_eficiencia:.1f}% de las tareas han sido completadas '
    estado_tareas += f'exitosamente, mientras que el {(100 - tasa_eficiencia):.1f}% permanecen pendientes. '
    estado_tareas += 'Esta proporción indica una gestión eficiente de la carga de trabajo.'
    pdf.multi_cell(0, 5, estado_tareas)
    pdf.ln(3)

    # Recomendaciones
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 8, 'RECOMENDACIONES', ln=True)
    pdf.ln(2)

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    recomendaciones = []
    
    if tareas_pendientes > tareas_completadas:
        recomendaciones.append('- Priorizar la resolución de tareas pendientes para mejorar la eficiencia.')
    
    if tasa_eficiencia < 70:
        recomendaciones.append('- Implementar estrategias para mejorar la tasa de eficiencia operativa.')
    else:
        recomendaciones.append('- Mantener las prácticas actuales que han demostrado ser efectivas.')
    
    if carga_promedio > 5:
        recomendaciones.append('- Considerar redistribuir la carga de trabajo entre más colaboradores.')
    else:
        recomendaciones.append('- La distribución actual de carga por usuario es óptima.')
    
    recomendaciones.append('- Continuar monitoreando los indicadores para mantener el rendimiento.')
    
    for rec in recomendaciones:
        pdf.cell(5, 5, '-', 0, 0)
        pdf.cell(0, 5, rec[2:], ln=True)
    
    pdf.ln(3)

    # Conclusión
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 8, 'CONCLUSION', ln=True)
    pdf.ln(2)

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    conclusion = 'El sistema Tassflow demuestra una gestión efectiva de la carga mental con indicadores positivos. '
    conclusion += f'La tasa de eficiencia del {tasa_eficiencia:.1f}% y la distribución equilibrada de tareas '
    conclusion += 'sugieren un entorno productivo y sostenible.'
    pdf.multi_cell(0, 5, conclusion)

    # Guardar PDF con ruta absoluta
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.join(base_dir, "static", "uploads")
    
    # Crear la carpeta si no existe
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Construir la ruta absoluta del archivo
    ruta_pdf = os.path.join(uploads_dir, "Reporte_Estadisticas_Tassflow.pdf")
    
    # Guardar el PDF
    pdf.output(ruta_pdf)

    registrar_actividad("info", "Reporte PDF de estadísticas descargado por administrador")

    return send_file(ruta_pdf, as_attachment=True, mimetype='application/pdf', download_name='Reporte_Estadisticas_Tassflow.pdf')


@admin_bp.route("/panel_empresa")
def dueno_panel():
    # Candado sin letra Ñ
    if session.get("rol") != "director":
        return redirect(url_for("auth.login"))

    empresa_id = session.get("empresa_id")
    
    # SALVAVIDAS: Si el usuario es antiguo y no tiene empresa, no dejamos que Mongo explote
    if not empresa_id:
        flash("Error: Tu cuenta no tiene una empresa vinculada.")
        return redirect(url_for("auth.login"))

    # Búsquedas blindadas
    filtro_empresa = {"empresa_id": ObjectId(empresa_id)}
    
    todo_el_equipo = list(usuarios_col.find(filtro_empresa))
    total_admins = usuarios_col.count_documents({"rol": "admin", **filtro_empresa})
    total_empleados = usuarios_col.count_documents({"rol": "usuario", **filtro_empresa})
    
    total_tareas = tareas_col.count_documents(filtro_empresa)
    tareas_pendientes = tareas_col.count_documents({"estado": "Pendiente", **filtro_empresa})

    return render_template(
        "dueno_panel.html",
        equipo=todo_el_equipo,
        total_admins=total_admins,
        total_empleados=total_empleados,
        total_tareas=total_tareas,
        tareas_pendientes=tareas_pendientes
    )


@admin_bp.route("/super_admin")
def super_panel():
    # Candado absoluto: Solo el super_admin puede entrar
    if session.get("rol") != "super_admin":
        return redirect(url_for("auth.login"))

    # El super_admin ve TODAS las empresas y su información
    total_empresas = empresas_col.count_documents({})
    total_usuarios = usuarios_col.count_documents({})
    todas_las_empresas = list(empresas_col.find())
    
    # Métricas globales del sistema
    total_tareas = tareas_col.count_documents({})
    tareas_activas = tareas_col.count_documents({"estado": "Pendiente"})
    logs_recientes = list(db["logs_seguridad"].find().sort("fecha_intento", -1).limit(50))

    return render_template(
        "super_panel.html",
        total_empresas=total_empresas,
        total_usuarios=total_usuarios,
        empresas=todas_las_empresas,
        total_tareas=total_tareas,
        tareas_activas=tareas_activas,
        logs_recientes=logs_recientes
    )


@admin_bp.route("/descargar_bienvenida")
def descargar_bienvenida():
    # Este documento es el trofeo exclusivo del Director
    if session.get("rol") != "director": return redirect(url_for("auth.login"))

    nombre_director = session.get("usuario", "Director")
    empresa_id = session.get("empresa_id")
    empresa = db.empresas.find_one({"_id": ObjectId(empresa_id)}) if empresa_id else None
    nombre_empresa = empresa["nombre_empresa"] if empresa else "tu organización"

    # Inicializamos el PDF
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()

    # === ENCABEZADO CORPORATIVO ===
    pdf.set_fill_color(26, 29, 45) # Azul oscuro Tassflow
    pdf.rect(0, 0, 210, 45, 'F')
    
    # Acento naranja
    pdf.set_fill_color(255, 159, 10) 
    pdf.rect(0, 45, 210, 2, 'F')

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 28)
    pdf.set_xy(15, 12)
    pdf.cell(0, 10, "TASSFLOW", ln=True)
    
    pdf.set_font("Arial", '', 12)
    pdf.set_text_color(200, 200, 200)
    pdf.set_xy(15, 25)
    pdf.cell(0, 10, "MANUAL EJECUTIVO DE IMPLEMENTACIÓN", ln=True)

    # === FECHA Y DESTINATARIO ===
    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_xy(15, 60)
    pdf.cell(0, 8, f"Bienvenido, Director(a) {nombre_director}", ln=True)
    
    pdf.set_font("Arial", 'I', 11)
    pdf.set_text_color(100, 100, 100)
    fecha_actual = datetime.now().strftime("%d de %B, %Y")
    pdf.cell(0, 6, f"Documento confidencial preparado para: {nombre_empresa} - {fecha_actual}", ln=True)
    pdf.ln(10)

    # === INTRODUCCIÓN ===
    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Arial", '', 11)
    intro = (
        f"Gracias por confiar en Tassflow para la gestión operativa de {nombre_empresa}. "
        "No has adquirido un simple gestor de tareas; has integrado un motor matemático predictivo "
        "diseñado para equilibrar la productividad y proteger la salud mental de tu equipo de trabajo."
    )
    pdf.multi_cell(0, 6, intro)
    pdf.ln(8)

    # === LA JERARQUÍA CORPORATIVA ===
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(26, 29, 45)
    pdf.cell(0, 8, "1. LA ARQUITECTURA DE TU SISTEMA (ROLES)", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.set_text_color(50, 50, 50)
    
    roles = (
        "Como Director, tienes el control absoluto de tu entorno aislado en la nube. "
        "Tu sistema Tassflow funciona bajo una jerarquia estricta:\n\n"
        "- DIRECTOR (Tu): Tienes acceso al Panel de Direccion. Tu funcion es supervisar las metricas globales "
        "y dar de alta a tus Gerentes.\n"
        "- ADMIN (Gerentes): Tienen acceso al Panel Operativo. Ellos son los encargados de dar de alta "
        "a los Empleados regulares y asignarles las tareas diarias.\n"
        "- USUARIOS (Empleados): Tienen acceso a su propio panel privado donde unicamente ven "
        "las responsabilidades que se les han asignado."
    )
    pdf.multi_cell(0, 6, roles)
    pdf.ln(8)

    # === EL MOTOR MATEMÁTICO ===
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(26, 29, 45)
    pdf.cell(0, 8, "2. EL ALGORITMO DE CARGA MENTAL", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.set_text_color(50, 50, 50)
    
    motor = (
        "En la pestana de 'Estadisticas', tus gerentes tendran acceso a nuestras proyecciones dinamicas. "
        "Tassflow utiliza un modelo basado en ecuaciones diferenciales que calcula la tasa constante de "
        "entrada de trabajo contra el coeficiente de resolucion de tu equipo.\n\n"
        "Esto te permite anticipar cuellos de botella y prevenir el sindrome de burnout ("
        "desgaste profesional) antes de que afecte la rentabilidad de la empresa."
    )
    pdf.multi_cell(0, 6, motor)
    pdf.ln(8)

    # === PLAN DE ACCIÓN INMEDIATO ===
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(15, pdf.get_y(), 180, 45, 'F')
    
    pdf.set_xy(20, pdf.get_y() + 5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "GUÍA DE INICIO RÁPIDO - PRIMEROS 3 PASOS:", ln=True)
    
    pdf.set_font("Arial", '', 11)
    pasos = (
        "1. Dirígete a la sección 'Crear Personal' en tu Panel de Dirección.\n"
        "2. Registra a tu primer Administrador (Gerente de área) asignándole el rol de 'admin'.\n"
        "3. Pídele a tu nuevo Gerente que inicie sesión para registrar a su equipo operativo y "
        "asignar la primera tarea de prueba."
    )
    pdf.set_x(20)
    pdf.multi_cell(170, 6, pasos)
    pdf.ln(15)

    # === DESPEDIDA ===
    pdf.set_font("Arial", 'I', 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 6, "El éxito de tu organización es nuestra prioridad. Comienza a optimizar tu flujo de trabajo hoy mismo.\n\nAtentamente,\nEl equipo de Tassflow")

    # === PIE DE PÁGINA ===
    pdf.set_y(-25)
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(150, 150, 150)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(2)
    pdf.cell(0, 4, "Tassflow Analytics - Software as a Service", ln=True, align='C')
    pdf.cell(0, 4, "Aislamiento de base de datos activado - Encriptación AES-256", ln=True, align='C')

    # === GUARDAR Y DESCARGAR ===
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uploads_dir = os.path.join(base_dir, "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    nombre_archivo = f"Manual_Implementacion_{nombre_empresa.replace(' ', '_')}.pdf"
    ruta_pdf = os.path.join(uploads_dir, nombre_archivo)
    pdf.output(ruta_pdf)

    registrar_actividad("creacion", f"Director {nombre_director} generó su manual de bienvenida.")

    return send_file(ruta_pdf, as_attachment=True, mimetype='application/pdf', download_name=nombre_archivo)
