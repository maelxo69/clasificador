from flask import Flask, Response, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from ultralytics import YOLO
import cv2
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_maqueta_utsui'

# Carga de modelo
ruta_modelo = 'runs/detect/modelo_plasticos-5/weights/best.pt'
model = YOLO(ruta_modelo)
print("Clases reconocidas por el modelo:", model.names)

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
    
    nombre_usuario = session.get('user', 'Usuario')
    return render_template("inicio.html", nombre_usuario=nombre_usuario)

@app.route("/materiales")
def materiales():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    nombre_usuario = session.get('user', 'Usuario')
    return render_template("materiales.html", nombre_usuario=nombre_usuario)

@app.route("/deteccion")
def deteccion():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    nombre_usuario = session.get('user', 'Usuario')
    return render_template("deteccion.html", nombre_usuario=nombre_usuario)

@app.route("/ecodiseno")
def ecodiseno():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    nombre_usuario = session.get('user', 'Usuario')
    return render_template("ecodiseno.html", nombre_usuario=nombre_usuario)


# ================= CÁMARA E IA =================

def generar_frames():
    URL_CAMARA = 'http://192.168.1.85:4747/video' 
    
    while True:
        cap = cv2.VideoCapture(URL_CAMARA)
        
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
            else:
                # Procesar el frame con tu modelo best.pt con imgsz=1280 y conf ajustada
                resultados = model(frame, conf=0.60, imgsz=600)
                
                # Imprimir en consola lo que va detectando
                for r in resultados:
                    for box in r.boxes:
                        cls_id = int(box.cls[0].item())
                        nombre_detectado = model.names[cls_id]
                        confianza = float(box.conf[0].item()) * 100
                        print(f"Objeto: {nombre_detectado} | Confianza: {confianza:.1f}%")
                
                # Dibujar las cajas sobre el frame
                frame_procesado = resultados[0].plot()

                # Codificar la imagen para enviarla a la web
                ret, buffer = cv2.imencode('.jpg', frame_procesado)
                frame_final = buffer.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_final + b'\r\n')
        
        cap.release()
        cv2.waitKey(1000) # Espera 1 segundo y reintenta conectar si se cae el stream

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# ================= INICIO DEL SERVIDOR =================
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)