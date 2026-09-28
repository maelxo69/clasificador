from flask import Flask, Response, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from ultralytics import YOLO
import cv2
import requests
import numpy as np
import time
import serial
import threading
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_maqueta_utsui'

# ================= CONEXIÓN SERIAL USB (PL2303 / ESP32-CAM) =================
# Reemplaza 'COM8' por el puerto COM que te asignó Windows para el Prolific
PUERTO_SERIAL = 'COM8'  
BAUD_RATE = 115200

try:
    esp32_serial = serial.Serial(PUERTO_SERIAL, BAUD_RATE, timeout=1)
    time.sleep(2)  # Tiempo para estabilizar la conexión Serial
    print(f"--> [HARDWARE] Conectado exitosamente con ESP32-CAM por USB en {PUERTO_SERIAL}")
except Exception as e:
    esp32_serial = None
    print(f"--> [WARNING] No se pudo abrir el puerto Serial ({PUERTO_SERIAL}): {e}")

# ================= TIEMPOS Y VARIABLES DE CONTROL =================
banda_activa = False

# Tiempos de desplazamiento (en segundos) desde la cámara hasta cada impulsador
# Ajusta estos valores según la distancia física real en tu maqueta
TIEMPOS_DESPLAZAMIENTO = {
    'PET':  1.5,  # Primer impulsador
    'LDPE': 2.8,  # Segundo impulsador
    'PVC':  4.0   # Tercer impulsador
}

# Variable global para actualización en el Dashboard (js.js)
ultima_deteccion = {"material": "--", "confianza": 0.0}

# ================= CARGA DE MODELO YOLO =================
ruta_modelo = 'runs/detect/train_definitivo/weights/best.pt'
model = YOLO(ruta_modelo)
print("Clases reconocidas por el modelo:", model.names)

# ================= BASE DE DATOS =================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        hashed_password = generate_password_hash('1234')
        admin = User(username='admin', password=hashed_password)
        db.session.add(admin)
        db.session.commit()

# ================= FUNCIONES DE HARDWARE (CABLE USB) =================

def activar_impulsador_async(material):
    """
    Se ejecuta en un hilo secundario para no congelar la transmisión de video.
    Espera a que el plástico llegue frente al impulsador y envía la orden por USB.
    """
    if material == 'HDPE':
        print("--> [HARDWARE] Material HDPE detectado: No se activa servo (rueda al final).")
        return

    tiempo_espera = TIEMPOS_DESPLAZAMIENTO.get(material, 2.0)
    time.sleep(tiempo_espera)

    if esp32_serial and esp32_serial.is_open:
        comando = f"S:{material}\n"
        esp32_serial.write(comando.encode('utf-8'))
        print(f"--> [USB CABLE] Comando enviado a ESP32: {comando.strip()}")

# ================= RUTAS DE AUTENTICACIÓN Y VISTAS =================

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
    session.clear()
    return redirect(url_for('login'))

@app.route("/")
def inicio():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template("inicio.html", nombre_usuario=session.get('user', 'Usuario'))

@app.route("/materiales")
def materiales():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template("materiales.html", nombre_usuario=session.get('user', 'Usuario'))

@app.route("/deteccion")
def deteccion():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template("deteccion.html", nombre_usuario=session.get('user', 'Usuario'))

@app.route("/ecodiseno")
def ecodiseno():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template("ecodiseno.html", nombre_usuario=session.get('user', 'Usuario'))

# ================= CÁMARA E IA =================

def generar_frames():
    global ultima_deteccion, banda_activa
    
    URL_CAMARA = 'http://192.168.11.243:81/stream'
    
    colores = {
        'HDPE': (255, 0, 0),    # Azul
        'LDPE': (0, 255, 0),    # Verde
        'PET':  (0, 0, 255),    # Rojo
        'PVC':  (0, 255, 255)   # Amarillo
    }
    
    ultimo_impreso = None  
    contador_frames = 0    
    resultados_ultimos = [] 

    while True:
        try:
            stream = requests.get(URL_CAMARA, stream=True, timeout=5)
            if stream.status_code != 200:
                time.sleep(1)
                continue

            bytes_chunk = b''
            for chunk in stream.iter_content(chunk_size=1024):
                bytes_chunk += chunk
                a = bytes_chunk.find(b'\xff\xd8') # Inicio del JPEG
                b = bytes_chunk.find(b'\xff\xd9') # Fin del JPEG
                
                if a != -1 and b != -1:
                    jpg = bytes_chunk[a:b+2]
                    bytes_chunk = bytes_chunk[b+2:]
                    
                    # Decodificación corregida con numpy
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        continue

                    contador_frames += 1
                    hay_deteccion = False
                    
                    # Salto de fotogramas para aligerar la IA (procesa 1 de cada 3 frames)
                    if contador_frames % 3 == 0:
                        resultados_ultimos = model(frame, conf=0.50, iou=0.45, imgsz=416, verbose=False)
                    
                    for r in resultados_ultimos:
                        for box in r.boxes:
                            hay_deteccion = True
                            cls_id = int(box.cls[0].item())
                            nombre_detectado = model.names[cls_id]
                            confianza = float(box.conf[0].item()) * 100
                            
                            ultima_deteccion = {
                                "material": nombre_detectado,
                                "confianza": confianza
                            }
                            
                            if nombre_detectado != ultimo_impreso:
                                print(f"--> [NUEVA DETECCIÓN] Material: {nombre_detectado} | Confianza: {confianza:.1f}%")
                                ultimo_impreso = nombre_detectado
                                
                                if banda_activa:
                                    thread_impulsador = threading.Thread(
                                        target=activar_impulsador_async, 
                                        args=(nombre_detectado,)
                                    )
                                    thread_impulsador.start()
                            
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            color_caja = colores.get(nombre_detectado, (255, 255, 255))
                            
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color_caja, 2)
                            texto = f"{nombre_detectado} {confianza:.1f}%"
                            cv2.putText(frame, texto, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_caja, 2)
                    
                    if not hay_deteccion:
                        ultimo_impreso = None

                    frame_salida = cv2.resize(frame, (640, 480))
                    ret, buffer = cv2.imencode('.jpg', frame_salida, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                           
        except Exception as e:
            print(f"--> [WARNING] Desconexión temporal de la cámara: {e}")
            time.sleep(1)

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ================= API ENDPOINTS PARA EL DASHBOARD Y HARDWARE =================

@app.route('/api/banda/iniciar', methods=['POST'])
def iniciar_banda():
    global banda_activa
    banda_activa = True
    if esp32_serial and esp32_serial.is_open:
        esp32_serial.write(b"M:ON\n")
        print("--> [CONTROL] Banda Transportadora Activada (Motor ON)")
    return jsonify({"status": "ok", "mensaje": "Banda iniciada"})

@app.route('/api/banda/detener', methods=['POST'])
def detener_banda():
    global banda_activa
    banda_activa = False
    if esp32_serial and esp32_serial.is_open:
        esp32_serial.write(b"M:OFF\n")
        print("--> [CONTROL] Banda Transportadora Detenida (Motor OFF)")
    return jsonify({"status": "ok", "mensaje": "Banda detenida"})

@app.route('/api/ultima_deteccion')
def get_ultima_deteccion():
    global ultima_deteccion
    return jsonify(ultima_deteccion)

# ================= INICIO DEL SERVIDOR =================
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)