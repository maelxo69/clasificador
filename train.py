from ultralytics import YOLO

def main():
    # Cargar el último punto guardado antes de pausar
    # Asegúrate de que el nombre de la carpeta coincida con el tuyo (ej: modelo_plasticos-4)
    model = YOLO("runs/detect/modelo_plasticos-5/weights/last.pt")

    # Reanudar entrenamiento
    model.train(resume=True)

if __name__ == '__main__':
    main()
