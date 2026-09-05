import os
import cv2
from ultralytics import YOLO

# 1. Ruta base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Carpeta exacta de tu modelo
CARPETA_MODELO = "modelo_plasticos-5"

model_path = os.path.join(BASE_DIR, "runs", "detect", CARPETA_MODELO, "weights", "best.pt")
if not os.path.exists(model_path):
    model_path = os.path.join(BASE_DIR, "runs", "detect", CARPETA_MODELO, "weights", "last.pt")

if not os.path.exists(model_path):
    print(f"Error: No se encontró el modelo en: {model_path}")
    exit()

print(f"-> Cargando modelo: {model_path}")
model = YOLO(model_path)

# 3. Ruta a tu imagen de prueba (test.jpg)
image_path = os.path.join(BASE_DIR, "pruebas", "test1.jpg")

# Si la imagen está en la raíz en lugar de 'pruebas/', buscarla también allí
if not os.path.exists(image_path):
    image_path = os.path.join(BASE_DIR, "test1.jpg")

if not os.path.exists(image_path):
    print(f"Error: No se encontró el archivo 'test1.jpg'.")
    exit()

print(f"-> Analizando imagen: {image_path}")

# 4. Realizar la predicción
results = model.predict(source=image_path, conf=0.20, imgsz=1280, save=True)

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