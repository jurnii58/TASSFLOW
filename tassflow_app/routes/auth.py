from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash 

from tassflow_app.database import usuarios_col, empresas_col, db 
from tassflow_app import limiter 

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/", methods=["GET", "POST"])
@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute") # DEFENSA FUERZA BRUTA
def login():
    if request.method == "POST":
        usuario_intento = request.form.get("usuario")
        password_intento = request.form.get("contrasena")
        ip_cliente = request.remote_addr

        user = usuarios_col.find_one({
            "nombre_usuario": usuario_intento,
            "activo": True
        })

        if not user or not check_password_hash(user["contrasena"], password_intento):
            db["logs_seguridad"].insert_one({
                "ip_origen": ip_cliente,
                "usuario_intentado": usuario_intento,
                "fecha_intento": datetime.now(),
                "alerta": "Intento de inicio de sesión fallido"
            })
            return render_template("login.html", error="Credenciales incorrectas")

        session.clear()
        
        # ACTIVAR TIMEOU INACTIVIDAD
        session.permanent = True  

        session["usuario"] = user["nombre_usuario"]
        session["rol"] = user["rol"]
        session["usuario_id"] = str(user["_id"]) # Guardamos su ID personal
        
        # EL TATUAJE DE LA EMPRESA: Guardamos la empresa en la sesión para el "Muro Invisible"
        if "empresa_id" in user:
            session["empresa_id"] = str(user["empresa_id"])

        # Agregamos al "director" a la lista VIP del panel
        if user["rol"] == "super_admin":
            return redirect(url_for("admin.super_panel")) # Jurni va aquí
        elif user["rol"] == "director":
            return redirect(url_for("admin.dueno_panel")) # El cliente va a su nueva oficina
        elif user["rol"] == "admin":
            return redirect(url_for("admin.admin_panel")) # Los gerentes de la empresa van aquí
        else:
            return redirect(url_for("usuario.usuario_panel")) # Los empleados mortales van aquí

    return render_template("login.html")

@auth_bp.route("/registro_empresa", methods=["GET", "POST"])
@limiter.limit("3 per minute") # Protegemos el registro contra bots
def registro_empresa():
    if request.method == "POST":
        nombre_empresa = request.form.get("nombre_empresa")
        nombre_admin = request.form.get("nombre_usuario")
        password_plano = request.form.get("contrasena")

        if usuarios_col.find_one({"nombre_usuario": nombre_admin}):
            flash("Ese nombre de usuario ya está ocupado.", "error")
            return redirect(url_for("auth.login", tab="registro"))

        nueva_empresa = {
            "nombre_empresa": nombre_empresa,
            "fecha_creacion": datetime.now(),
            "estado": "Activo"
        }
        id_empresa = empresas_col.insert_one(nueva_empresa).inserted_id

        nuevo_director = {
            "nombre_usuario": nombre_admin,
            "contrasena": generate_password_hash(password_plano),
            "rol": "director",           # <--- ¡CAMBIO AQUÍ! Nace como el Propietario
            "activo": True,
            "empresa_id": id_empresa
        }
        usuario_id = usuarios_col.insert_one(nuevo_director).inserted_id

        # === AUTO-LOGIN DEL DIRECTOR DESPUÉS DEL REGISTRO ===
        session.clear()
        session.permanent = True
        
        session["usuario"] = nombre_admin
        session["rol"] = "director"
        session["usuario_id"] = str(usuario_id)
        session["empresa_id"] = str(id_empresa)
        
        flash("¡Tu empresa fue registrada con éxito! Bienvenido a tu panel.")
        return redirect(url_for("admin.dueno_panel"))  # <--- DIRECTO AL PANEL DEL DIRECTOR
    
    return redirect(url_for("auth.login"))


@auth_bp.route("/olvide_password", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def olvide_password():
    if request.method == "POST":
        username = request.form.get("usuario")
        user = usuarios_col.find_one({"nombre_usuario": username})
        if user:
            usuarios_col.update_one({"_id": user["_id"]}, {"$set": {"solicitud_reset": True}})
            flash("Solicitud enviada al administrador.")
        return redirect(url_for("auth.login"))
    return render_template("olvide_password.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))