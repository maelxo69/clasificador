import os
from ultralytics import YOLO

# =====================================================================
# ESCRIBE AQUÍ EL NOMBRE EXACTO DE LA IMAGEN QUE QUIERES PROBAR
# (Ejemplo: "prueba_2.jpeg", "prubea_!.jpeg", "prueba_3.jpeg")
# =====================================================================
NOMBRE_IMAGEN = "test1.jpg"

model = YOLO('runs/detect/modelo_plasticos-5/weights/best.pt')
print("👉 Clases que el modelo fue entrenado a reconocer:", model.names)

# 1. Rutas base
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)

# 2. Cargar el modelo
CARPETA_MODELO = "modelo_plasticos-5"
model_path = os.path.join(BASE_DIR, "runs", "detect", CARPETA_MODELO, "weights", "best.pt")

if not os.path.exists(model_path):
    raise FileNotFoundError(f"Error: No se encontró el modelo en: {model_path}")

print(f"-> Cargando modelo: {model_path}")
model = YOLO(model_path)

# 3. Ruta de la imagen especificada
image_path = os.path.join(CURRENT_DIR, NOMBRE_IMAGEN)

if not os.path.exists(image_path):
    raise FileNotFoundError(
        f"Error: No se encontró el archivo '{NOMBRE_IMAGEN}' en la carpeta 'pruebas/'. "
        f"Revisa si está bien escrito o si tiene otra extensión (.jpg / .jpeg)."
    )

print(f"-> Analizando imagen: {image_path}")

# 4. Realizar la predicción
results = model.predict(source=image_path, conf=0.30, imgsz=1280, save=True)

# 5. Mostrar resultados
for result in results:
    boxes = result.boxes
    print("\n==========================================")
    print(f" TOTAL DE PLÁSTICOS DETECTADOS: {len(boxes)}")
    print("==========================================")
    for box in boxes:
        cls_id = int(box.cls[0])
        class_name = model.names[cls_id]
        conf = float(box.conf[0]) * 100
        print(f" [✓] Material: {class_name} | Confianza: {conf:.2f}%")

    result.show()