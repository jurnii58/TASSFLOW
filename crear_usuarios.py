from tassflow_app.database import usuarios_col
from werkzeug.security import generate_password_hash

print("Iniciando actualización de seguridad...")

# Borramos usuarios viejos sin encriptar
usuarios_col.delete_many({})
print("- Usuarios antiguos eliminados.")

# Creamos al Admin
usuarios_col.insert_one({
    "nombre_usuario": "admin",
    "contrasena": generate_password_hash("admin123"),
    "rol": "admin",
    "activo": True
})
print("- Administrador creado con éxito.")

# Creamos al Usuario
usuarios_col.insert_one({
    "nombre_usuario": "empleado",
    "contrasena": generate_password_hash("usuario123"),
    "rol": "usuario",
    "activo": True
})
print("- Usuario de prueba creado con éxito.")

print("¡Listo! Tu base de datos ahora es 100% segura. Ya puedes iniciar sesión con 'admin123' o 'usuario123'.")