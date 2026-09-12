from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_maqueta_utsui'

# Configuración de la Base de Datos SQLite local
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de Usuario para la Base de Datos
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Crear la base de datos y el usuario admin por defecto al iniciar la app
with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        hashed_password = generate_password_hash('1234')
        admin = User(username='admin', password=hashed_password)
        db.session.add(admin)
        db.session.commit()

# ================= RUTAS DE AUTENTICACIÓN =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user_input = request.form.get('username')
        pass_input = request.form.get('password')
        
        user = User.query.filter_by(username=user_input).first()
        
        if user and check_password_hash(user.password, pass_input):
            session['logged_in'] = True
            session['user'] = user.username
            
            return redirect(url_for('inicio'))
        else:
            error = "Usuario o contraseña incorrectos"
            
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        user_input = request.form.get('username')
        pass_input = request.form.get('password')
        
        # Verificar si el usuario ya existe en la base de datos
        existing_user = User.query.filter_by(username=user_input).first()
        if existing_user:
            error = "El nombre de usuario ya está en uso."
        else:
            hashed_password = generate_password_hash(pass_input)
            new_user = User(username=user_input, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
            
    return render_template('registro.html', error=error)

@app.route('/logout')
def logout():
    session.clear() # Borra toda la sesión por completo
    return redirect(url_for('login'))
# ================= RUTAS PRINCIPALES (PROTEGIDAS) =================

@app.route("/")
def inicio():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Recuperamos el nombre del usuario de la sesión (o usamos un valor por defecto si no existe)
    nombre_usuario = session.get('user_name', 'Usuario')
    
    # Se lo enviamos a la plantilla inicio.html
    return render_template("inicio.html", nombre_usuario=nombre_usuario)

@app.route("/materiales")
def materiales():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("materiales.html")

@app.route("/deteccion")
def deteccion():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("deteccion.html")


@app.route("/ecodiseno")
def ecodiseno():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("ecodiseno.html")

    # host='0.0.0.0' permite que cualquier dispositivo en tu Wi-Fi acceda a la página
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)