from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)

# Clave secreta obligatoria para manejar sesiones de forma segura
app.secret_key = 'clave_secreta_maqueta'

# Credenciales de acceso para tu maqueta
USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTO = "1234"

# ================= RUTAS DE ACCESO =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        password = request.form.get('password')
        
        if user == USUARIO_CORRECTO and password == PASSWORD_CORRECTO:
            session['logged_in'] = True
            return redirect(url_for('inicio'))
        else:
            error = "Usuario o contraseña incorrectos"
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ================= RUTAS PRINCIPALES =================

@app.route("/")
def inicio():
    # Verifica si el usuario ha iniciado sesión
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("inicio.html")


@app.route("/materiales")
def materiales():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("materiales.html")


@app.route("/deteccion")
def deteccion():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    # Ruta preparada para la FASE 8 (YOLO + Cámara)
    # Si aún no tienes deteccion.html, puedes crear un archivo vacío por ahora
    return render_template("deteccion.html")


@app.route("/ecodiseno")
def ecodiseno():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("ecodiseno.html")


if __name__ == "__main__":


    # host='0.0.0.0' permite que cualquier dispositivo en tu Wi-Fi acceda a la página
    app.run(host='0.0.0.0', port=5000, debug=True)