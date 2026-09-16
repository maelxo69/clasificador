from ultralytics import YOLO

def main():
    # Cargas el último punto de guardado antes de que se congelara VS Code
    # (Asegúrate de que la ruta coincida con el nombre de la carpeta de tu último intento)
    model = YOLO("runs/detect/train_definitivo-2/weights/last.pt")

    # Reamas el entrenamiento con resume=True (YOLO lee la configuración previa solo)
    model.train(resume=True)

if __name__ == '__main__':
    main()