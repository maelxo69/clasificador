from flask import Flask, Response, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from ultralytics import YOLO
import cv2
import requests
import numpy as np
import time
import threading
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_maqueta_utsui'

# ================= CONEXIÓN CON LA ESP32-CAM (POR WIFI) =================
# Cambia SOLO esta IP si la ESP32 cambia de dirección (la muestra el Monitor Serie al arrancar)
IP_ESP32 = '192.168.1.75'
URL_CAMARA = f'http://{IP_ESP32}:81/stream'    # video
URL_COMANDOS = f'http://{IP_ESP32}:8080'       # órdenes de banda y servos

banda_activa = False

# ================= CICLO DE CLASIFICACIÓN (tiempos en SEGUNDOS) =================
# Flujo con PALETAS:
#   1. Pones el objeto frente a la cámara y pulsas "Iniciar banda". La banda queda QUIETA y la IA vigila.
#   2. Cuando la IA ve el mismo material VOTOS_CONFIRMACION veces, lo confirma.
#   3. Baja la paleta de ese material (HDPE no tiene paleta: cae al final de la banda).
#   4. La banda rueda hasta que el objeto llega a la paleta y resbala fuera de la banda.
#   5. La banda se apaga, la paleta sube, y el sistema espera a que el cuadro quede vacío
#      antes de aceptar un objeto nuevo.
T_ESPERA_DETECCION = 3.0     # seg que dura cada "ventana" para juntar los votos (se reinicia si no se confirma)
VOTOS_CONFIRMACION = 2       # veces que la IA debe ver el MISMO material dentro de la ventana para confirmarlo
CONF_MINIMA_CICLO = 50       # % de confianza mínima para que una detección cuente como voto (súbela si hay falsos positivos)

# Seg que rueda la banda DESDE LA CÁMARA hasta que el objeto llega a su paleta.
# HDPE no tiene paleta: rueda hasta el final de la banda.   (AJUSTA ESTOS VALORES CON TU MAQUETA)
TIEMPO_A_DESTINO = {
    'PET': 2.5,
    'LDPE': 4.0,
    'PVC': 5.5,
    'HDPE': 7.0
}
T_CAIDA = 1.5                # seg EXTRA que sigue rodando la banda con la paleta abajo, hasta que el objeto cae
T_REARME = 1.5               # seg que el cuadro debe estar SIN objetos antes de aceptar uno nuevo

# ----- PALETAS (servos): se cambian aquí, SIN volver a subir nada a la ESP32 -----
# reposo = ángulo con la paleta ARRIBA (deja pasar los objetos)
# empuje = ángulo con la paleta ABAJO (bloquea el paso y desvía el objeto fuera de la banda)
# vel_ida / vel_vuelta = velocidad al bajar / al subir, de 1 (muy lento) a 100 (lo más rápido)
# Prueba los ángulos en el navegador: http://IP:8080/servo/pet/mover?angulo=90&vel=100
SERVOS = {
    'PET':  {'reposo': 0, 'empuje': 90, 'vel_ida': 50, 'vel_vuelta': 70},
    'LDPE': {'reposo': 0, 'empuje': 90, 'vel_ida': 90, 'vel_vuelta': 90},
    'PVC':  {'reposo': 0, 'empuje': 90, 'vel_ida': 50, 'vel_vuelta': 70}
}
T_MARGEN_SERVO = 1.0         # seg extra de espera para que la paleta termine de moverse ANTES de encender la banda

# ----- MOTOR -----
VELOCIDAD_MOTOR = 210      # fuerza de la banda, de 0 a 255 (si es muy baja el motor no alcanza a girar)
RAMPA_ARRANQUE_MS = 0   # arranque SUAVE: la banda sube de 0 a la fuerza de arriba en este tiempo (ms). 0 = tirón directo, que puede despegar el rodamiento
T_PAUSA_ENTRE_OBJETOS = 0.5  # seg de pausa antes de empezar con el siguiente objeto
MATERIALES_CON_SERVO = ['PET', 'LDPE', 'PVC']

estado_ciclo = "EN ESPERA"
ultima_clasificacion = {"id": 0, "material": "--", "confianza": 0.0}
_lock_captura = threading.Lock()
_captura = {'activa': False, 'votos': {}, 'conf': {}}
_hilo_ciclo = None
_paleta_abajo = None      # material cuya paleta está bajada en este momento (None = todas arriba)
_ultimo_visto = 0.0       # última vez que la IA vio un objeto válido en el cuadro

ultima_deteccion = {
    "material": "--",
    "confianza": 0.0
}

MATERIALES = ['HDPE', 'LDPE', 'PET', 'PVC']
CONTAR_SOLO_CON_BANDA = False
COOLDOWN_CONTEO = 1.0
_lock_conteo = threading.Lock()
_eventos = []
_ultimo_conteo = {'material': None, 'ts': 0.0}

# >>> ESTIRAR A CUADRADO <<<
# False: la IA recibe el cuadro tal cual llega de la cámara (comportamiento de siempre).
# True:  la IA recibe el cuadro estirado a 640x640 (como el "Stretch to 640x640" de Roboflow)
#        y las cajas se devuelven al tamaño real del video.
ESTIRAR_A_CUADRADO = False

# >>> FILTROS PARA DETECCIONES FALSAS <<<
CONF_MINIMA = 0.45      # confianza mínima de la IA. Prueba con 0.70 para que sea más exigente
AREA_MAX_CAJA = 0.8     # fracción máxima del video que puede ocupar una caja (1.0 = sin límite; 0.5 = ignora cajas de más de la mitad)

def registrar_deteccion(material, confianza):
    ahora = time.time()
    with _lock_conteo:
        if material == _ultimo_conteo['material'] and ahora - _ultimo_conteo['ts'] < COOLDOWN_CONTEO:
            _ultimo_conteo['ts'] = ahora
            return
        _ultimo_conteo.update(material=material, ts=ahora)
        _eventos.append((ahora, material, float(confianza)))

ruta_modelo = 'runs/detect/train_v3.3/weights/best.pt'
model = YOLO(ruta_modelo)
print("Clases reconocidas por el modelo:", model.names)

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

def enviar_comando(comando):
    # Envía la orden a la ESP32 por WiFi. Comandos: M:ON, M:OFF, P:BAJAR:<MAT>, P:SUBIR:<MAT>
    parametros = {}
    if comando == "M:ON":
        ruta, parametros = "/motor/on", {"vel": VELOCIDAD_MOTOR, "rampa": RAMPA_ARRANQUE_MS}
    elif comando == "M:OFF":
        ruta = "/motor/off"
    elif comando.startswith("P:"):
        # P:BAJAR:PET  /  P:SUBIR:PET
        try:
            _, accion, mat = comando.split(":")
        except ValueError:
            return False
        if mat not in SERVOS or accion not in ("BAJAR", "SUBIR"):
            return False
        cfg = SERVOS[mat]
        bajar = (accion == "BAJAR")
        ruta = "/servo/" + mat.lower() + "/mover"
        parametros = {"angulo": cfg['empuje'] if bajar else cfg['reposo'],
                      "vel": cfg['vel_ida'] if bajar else cfg['vel_vuelta']}
    else:
        return False

    for intento in range(1, 4):
        if comando == "M:ON" and not banda_activa:
            return False   # si se pulsó Detener, nunca se enciende la banda
        try:
            r = requests.get(URL_COMANDOS + ruta, params=parametros, timeout=3)
            if r.status_code == 200:
                print(f"--> [WIFI] Enviado a ESP32: {comando} {parametros}")
                return True
        except requests.exceptions.RequestException as e:
            print(f"--> [WARNING] No se pudo enviar {comando} (intento {intento}/3): {e}")
            time.sleep(0.3)
    print(f"--> [ERROR] La ESP32 no recibió la orden: {comando}")
    return False

def tiempo_paleta(material, bajar):
    # Cuánto esperar a que la paleta termine de moverse (misma fórmula de velocidad que el sketch)
    cfg = SERVOS[material]
    vel = cfg['vel_ida'] if bajar else cfg['vel_vuelta']
    ms_por_grado = (100 - max(1, min(100, vel))) * 3 // 10
    recorrido = abs(cfg['empuje'] - cfg['reposo'])
    return recorrido * ms_por_grado / 1000 + T_MARGEN_SERVO

def mover_paleta(material, bajar):
    # Baja o sube la paleta y espera a que termine. Devuelve False si falló o se pulsó Detener
    if not enviar_comando(f"P:{'BAJAR' if bajar else 'SUBIR'}:{material}"):
        return False
    return esperar(tiempo_paleta(material, bajar))

def abortar(motivo):
    global banda_activa
    print(f"--> [ERROR] {motivo}. Ciclo detenido")
    banda_activa = False

def votar(material, confianza):
    # Lo llama el análisis de la cámara: cada detección cuenta como un voto mientras la IA "mira"
    if confianza < CONF_MINIMA_CICLO:
        return
    with _lock_captura:
        if _captura['activa']:
            _captura['votos'][material] = _captura['votos'].get(material, 0) + 1
            _captura['conf'].setdefault(material, []).append(confianza)

def esperar(segundos):
    # Espera sin bloquear para siempre: devuelve False si se pulsó Detener
    fin = time.time() + segundos
    while time.time() < fin:
        if not banda_activa:
            return False
        time.sleep(0.05)
    return banda_activa

def esperar_clasificacion():
    with _lock_captura:
        _captura.update(activa=True, votos={}, conf={})
    fin = time.time() + T_ESPERA_DETECCION
    material, confianza = None, 0.0
    while material is None and time.time() < fin and banda_activa:
        with _lock_captura:
            for mat, n in _captura['votos'].items():
                if n >= VOTOS_CONFIRMACION:
                    lista = _captura['conf'][mat]
                    material, confianza = mat, sum(lista) / len(lista)
                    break
        time.sleep(0.05)
    with _lock_captura:
        _captura['activa'] = False
    return material, confianza

def esperar_camara_vacia():
    # Tras cada objeto, no acepta uno nuevo hasta que el cuadro lleve T_REARME seg sin detecciones.
    # Así un objeto que se quedó en el cuadro no dispara el ciclo una y otra vez.
    inicio = time.time()
    avisado = False
    while banda_activa:
        if time.time() - _ultimo_visto >= T_REARME:
            return True
        if not avisado and time.time() - inicio > 5:
            print("--> [CICLO] Hay un objeto en el cuadro; retíralo para continuar")
            avisado = True
        time.sleep(0.1)
    return False

def ciclo_clasificacion():
    global estado_ciclo, ultima_clasificacion, _paleta_abajo
    print("--> [CICLO] Iniciado")
    try:
        enviar_comando("M:OFF")                      # empieza con la banda quieta
        for m in MATERIALES_CON_SERVO:
            enviar_comando(f"P:SUBIR:{m}")           # y todas las paletas arriba
        esperar(1.0)

        while banda_activa:
            # 1. Banda quieta: la IA vigila hasta confirmar un material
            estado_ciclo = "ESPERANDO OBJETO"
            material, confianza = esperar_clasificacion()
            if material is None:
                continue

            # 2. Se registra en el historial de la página y en el dashboard
            ultima_clasificacion = {"id": ultima_clasificacion["id"] + 1, "material": material, "confianza": confianza}
            registrar_deteccion(material, confianza)
            print(f"--> [CICLO] Material confirmado: {material} ({confianza:.1f}%)")

            # 3. Baja la paleta de ese material (HDPE no tiene: cae al final de la banda)
            if material in MATERIALES_CON_SERVO:
                estado_ciclo = f"BAJANDO PALETA {material}"
                _paleta_abajo = material
                if not mover_paleta(material, True):
                    if banda_activa:
                        abortar(f"No se pudo bajar la paleta {material}")
                    break

            # 4. La banda rueda hasta que el objeto llega a la paleta y cae
            estado_ciclo = f"LLEVANDO A {material}"
            if not enviar_comando("M:ON"):
                if banda_activa:
                    abortar("No se pudo encender la banda")
                break
            if not esperar(TIEMPO_A_DESTINO.get(material, 2.0) + T_CAIDA):
                break
            enviar_comando("M:OFF")

            # 5. Sube la paleta
            if _paleta_abajo:
                estado_ciclo = f"SUBIENDO PALETA {material}"
                if not mover_paleta(material, False):
                    break
                _paleta_abajo = None

            # 6. Pausa y espera a que el cuadro quede vacío antes de aceptar otro objeto
            if not esperar(T_PAUSA_ENTRE_OBJETOS):
                break
            estado_ciclo = "ESPERANDO CUADRO VACÍO"
            if not esperar_camara_vacia():
                break
    finally:
        with _lock_captura:
            _captura['activa'] = False
        enviar_comando("M:OFF")
        if _paleta_abajo:
            enviar_comando(f"P:SUBIR:{_paleta_abajo}")   # nunca deja una paleta bajada
            _paleta_abajo = None
        estado_ciclo = "EN ESPERA"
        print("--> [CICLO] Detenido")

def iniciar_ciclo():
    global _hilo_ciclo
    if _hilo_ciclo is None or not _hilo_ciclo.is_alive():
        _hilo_ciclo = threading.Thread(target=ciclo_clasificacion, daemon=True)
        _hilo_ciclo.start()

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
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("inicio.html", nombre_usuario=session.get('user', 'Usuario'))

@app.route("/materiales")
def materiales():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("materiales.html", nombre_usuario=session.get('user', 'Usuario'))

@app.route("/deteccion")
def deteccion():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("deteccion.html", nombre_usuario=session.get('user', 'Usuario'))

@app.route("/ecodiseno")
def ecodiseno():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("ecodiseno.html", nombre_usuario=session.get('user', 'Usuario'))

@app.route("/dashboard")
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template("dashboard.html", nombre_usuario=session.get('user', 'Usuario'))

def generar_frames():
    global ultima_deteccion, banda_activa, _ultimo_visto

    colores = {
        'HDPE': (255, 0, 0),
        'LDPE': (0, 255, 0),
        'PET': (0, 0, 255),
        'PVC': (0, 255, 255)
    }

    ultimo_impreso = None
    contador_frames = 0
    resultados_ultimos = []

    while True:
        try:
            print("--> [CAMARA] Conectando con la ESP32-CAM...")
            stream = requests.get(URL_CAMARA, stream=True, timeout=5)

            if stream.status_code != 200:
                print(f"--> [WARNING] La cámara respondió con código {stream.status_code}")
                time.sleep(1)
                continue

            print("--> [CAMARA] Stream conectado correctamente")
            bytes_chunk = b''

            for chunk in stream.iter_content(chunk_size=1024):
                bytes_chunk += chunk
                a = bytes_chunk.find(b'\xff\xd8')
                b = bytes_chunk.find(b'\xff\xd9')

                if a == -1 or b == -1:
                    continue

                jpg = bytes_chunk[a:b + 2]
                bytes_chunk = bytes_chunk[b + 2:]

                frame = cv2.imdecode(
                    np.frombuffer(jpg, dtype=np.uint8),
                    cv2.IMREAD_COLOR
                )

                if frame is None:
                    continue

                contador_frames += 1
                hay_deteccion = False

                # >>> ESTIRAR A CUADRADO: factores para devolver las cajas al tamaño real del cuadro
                alto, ancho = frame.shape[:2]
                if ESTIRAR_A_CUADRADO:
                    esc_x, esc_y = ancho / 640, alto / 640
                else:
                    esc_x, esc_y = 1.0, 1.0

                nueva_inferencia = (contador_frames % 3 == 0)
                if nueva_inferencia:
                    # >>> ESTIRAR A CUADRADO: imagen que recibe la IA
                    entrada = cv2.resize(frame, (640, 640)) if ESTIRAR_A_CUADRADO else frame
                    resultados_ultimos = model(
                        entrada,
                        conf=CONF_MINIMA,
                        iou=0.45,
                        imgsz=416,
                        verbose=False
                    )

                for r in resultados_ultimos:
                    for box in r.boxes:
                        # >>> FILTRO: ignora cajas demasiado grandes
                        fx1, fy1, fx2, fy2 = box.xyxy[0].tolist()
                        proporcion = ((fx2 - fx1) * esc_x) * ((fy2 - fy1) * esc_y) / (ancho * alto)
                        if proporcion > AREA_MAX_CAJA:
                            continue
                        hay_deteccion = True
                        _ultimo_visto = time.time()
                        cls_id = int(box.cls[0].item())
                        nombre_detectado = model.names[cls_id]
                        confianza = float(box.conf[0].item()) * 100

                        ultima_deteccion = {
                            "material": nombre_detectado,
                            "confianza": confianza
                        }

                        if nueva_inferencia:
                            votar(nombre_detectado, confianza)   # voto para el ciclo de clasificación

                        if nombre_detectado != ultimo_impreso:
                            print(f"--> [NUEVA DETECCIÓN] Material: {nombre_detectado} | Confianza: {confianza:.1f}% | Caja: {proporcion:.0%} del video")
                            ultimo_impreso = nombre_detectado

                            # Con la banda apagada (modo prueba) se cuenta aquí;
                            # con el ciclo en marcha se cuenta al confirmar el material
                            if not banda_activa and not CONTAR_SOLO_CON_BANDA:
                                registrar_deteccion(nombre_detectado, confianza)

                        # >>> ESTIRAR A CUADRADO: cajas devueltas al tamaño real del cuadro
                        bx1, by1, bx2, by2 = box.xyxy[0].tolist()
                        x1, x2 = int(bx1 * esc_x), int(bx2 * esc_x)
                        y1, y2 = int(by1 * esc_y), int(by2 * esc_y)
                        color_caja = colores.get(nombre_detectado, (255, 255, 255))

                        cv2.rectangle(
                            frame,
                            (x1, y1),
                            (x2, y2),
                            color_caja,
                            2
                        )

                        texto = f"{nombre_detectado} {confianza:.1f}%"

                        cv2.putText(
                            frame,
                            texto,
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            color_caja,
                            2
                        )

                if not hay_deteccion:
                    ultimo_impreso = None

                frame_salida = cv2.resize(frame, (640, 480))

                ret, buffer = cv2.imencode(
                    '.jpg',
                    frame_salida,
                    [cv2.IMWRITE_JPEG_QUALITY, 80]
                )

                if not ret:
                    continue

                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n'
                    + buffer.tobytes()
                    + b'\r\n'
                )

        except requests.exceptions.RequestException as e:
            print(f"--> [WARNING] Desconexión temporal de la cámara: {e}")
            time.sleep(1)

        except Exception as e:
            print(f"--> [WARNING] Error en el procesamiento de la cámara: {e}")
            time.sleep(1)

@app.route('/video_feed')
def video_feed():
    return Response(
        generar_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/banda/iniciar', methods=['POST'])
def iniciar_banda():
    global banda_activa
    banda_activa = True
    iniciar_ciclo()
    return jsonify({"status": "ok", "mensaje": "Banda iniciada"})

@app.route('/api/banda/detener', methods=['POST'])
def detener_banda():
    global banda_activa
    banda_activa = False
    enviar_comando("M:OFF")
    return jsonify({"status": "ok", "mensaje": "Banda detenida"})

@app.route('/api/ultima_deteccion')
def get_ultima_deteccion():
    return jsonify({
        **ultima_deteccion,
        "estado": estado_ciclo,
        "id": ultima_clasificacion["id"],
        "clasificado": ultima_clasificacion
    })

@app.route('/api/estadisticas')
def api_estadisticas():
    ahora = time.time()
    minutos = 10

    with _lock_conteo:
        ev = list(_eventos)

    totales = {m: 0 for m in MATERIALES}
    serie = {m: [0] * minutos for m in MATERIALES}

    for ts, m, _ in ev:
        if m not in totales:
            continue

        totales[m] += 1
        i = int((ahora - ts) // 60)

        if i < minutos:
            serie[m][minutos - 1 - i] += 1

    conf = sum(c for _, _, c in ev) / len(ev) if ev else 0
    por_minuto = sum(
        1 for ts, _, _ in ev
        if ahora - ts < 60
    )

    return jsonify(
        totales=totales,
        total=len(ev),
        serie=serie,
        confianza_prom=round(conf, 1),
        por_minuto=por_minuto
    )

@app.route('/api/estadisticas/reiniciar', methods=['POST'])
def api_estadisticas_reiniciar():
    with _lock_conteo:
        _eventos.clear()
        _ultimo_conteo.update(
            material=None,
            ts=0.0
        )

    return jsonify({
        "status": "ok",
        "mensaje": "Conteo reiniciado"
    })

if __name__ == "__main__":
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False
    )