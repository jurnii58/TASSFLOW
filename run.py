import os
from tassflow_app import create_app

# Llama a la fábrica para construir la aplicación
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # debug=True es clave mientras desarrollamos para ver los errores en pantalla
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)