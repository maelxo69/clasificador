from ultralytics import YOLO

def main():
    # 1. Cargamos tu mejor modelo anterior como base para aprovechar lo que ya aprendió
    # (Asegúrate de que la ruta apunte exactamente a donde guardaste el best.pt anterior)
    model = YOLO("runs/detect/train/weights/best.pt") 

    # 2. Entrenamos con tu nuevo dataset limpio y balanceado
    model.train(
        data="dataset/data.yaml",    # Ruta a tu archivo de configuración del nuevo dataset
        epochs=30,                   # Épocas recomendadas para afinar el modelo sin sobreentrenarlo
        imgsz=640,                   # Resolución estándar de entrada
        batch=16,                   # Tamaño del lote (ajusta a 8 si te llega a faltar memoria VRAM)
        name="train_definitivo"  # Nombre limpio para esta nueva carpeta de resultados
    )

if __name__ == '__main__':
    main()