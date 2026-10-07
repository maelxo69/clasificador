from ultralytics import YOLO

def main():
    model = YOLO("runs/detect/train_v3.3/weights/last.pt")   # el último punto de control
    model.train(resume=True)                                # continúa por donde iba

if __name__ == '__main__':
    main()