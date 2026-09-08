from ultralytics import YOLO

def main():
    model = YOLO("runs/detect/modelo_plasticos-5/weights/last.pt")

    # Reanudar entrenamiento
    model.train(resume=True)

if __name__ == '__main__':
    main()