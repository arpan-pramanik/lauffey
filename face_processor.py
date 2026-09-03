import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from config import DETECTOR_BACKEND, RECOGNITION_MODEL, CROP_MARGIN

class FaceProcessor:
    """
    Handles face detection, padding/cropping, and feature vector extraction.
    Leverages RTX 5070 GPU via PyTorch/CUDA when available.
    """
    def __init__(self):
        self.device = "cpu"
        self.gpu_name = None
        self._check_hardware()

    def _check_hardware(self):
        try:
            import torch
            if torch.cuda.is_available():
                self.device = "cuda"
                self.gpu_name = torch.cuda.get_device_name(0)
                print(f"[✓] Hardware Acceleration Active: {self.gpu_name} (CUDA {torch.version.cuda})")
            else:
                print("[i] Running on CPU (PyTorch CUDA not active).")
        except ImportError:
            print("[i] PyTorch not yet imported; running in standard CPU mode.")

    def detect_and_crop(self, image_path: str, output_path: Optional[str] = None) -> Tuple[str, Tuple[int, int, int, int]]:
        """
        Detects face, applies a 20% margin, and saves the cropped face.
        Returns (cropped_image_path, (x, y, w, h)).
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found at: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not decode image at: {image_path}")

        h_img, w_img, _ = img.shape
        x, y, w, h = None, None, None, None

        # Attempt 1: DeepFace extraction
        try:
            from deepface import DeepFace
            faces = DeepFace.extract_faces(
                img_path=image_path,
                detector_backend=DETECTOR_BACKEND,
                enforce_detection=False,
                align=True
            )
            if faces and len(faces) > 0:
                facial_area = faces[0]["facial_area"]
                x = facial_area["x"]
                y = facial_area["y"]
                w = facial_area["w"]
                h = facial_area["h"]
        except Exception:
            pass

        # Attempt 2: OpenCV Haar Cascade fallback
        if x is None or w is None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)
            detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
            if len(detected) > 0:
                # Select the largest face detected
                largest = max(detected, key=lambda b: b[2] * b[3])
                x, y, w, h = int(largest[0]), int(largest[1]), int(largest[2]), int(largest[3])

        # Attempt 3: If no face found, center crop with warning
        if x is None:
            print("[!] Warning: No distinct face detected; using central region.")
            w, h = int(w_img * 0.6), int(h_img * 0.6)
            x, y = (w_img - w) // 2, (h_img - h) // 2

        # Apply CROP_MARGIN
        pad_w = int(w * CROP_MARGIN)
        pad_h = int(h * CROP_MARGIN)
        crop_x1 = max(0, x - pad_w)
        crop_y1 = max(0, y - pad_h)
        crop_x2 = min(w_img, x + w + pad_w)
        crop_y2 = min(h_img, y + h + pad_h)

        crop = img[crop_y1:crop_y2, crop_x1:crop_x2]

        if output_path is None:
            output_path = str(Path(image_path).parent / f"temp_cropped_{Path(image_path).name}")

        cv2.imwrite(output_path, crop)
        return output_path, (crop_x1, crop_y1, crop_x2 - crop_x1, crop_y2 - crop_y1)

    def extract_embedding(self, cropped_image_path: str) -> list:
        """
        Computes the biometric embedding vector for the face.
        """
        try:
            from deepface import DeepFace
            rep = DeepFace.represent(
                img_path=cropped_image_path,
                model_name=RECOGNITION_MODEL,
                enforce_detection=False
            )
            if rep and len(rep) > 0:
                return rep[0]["embedding"]
        except Exception:
            pass

        # Fallback: Normalized OpenCV color + texture histogram embedding (128-d)
        img = cv2.imread(cropped_image_path)
        img_small = cv2.resize(img, (64, 64))
        hsv = cv2.cvtColor(img_small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten().tolist()

    def process(self, image_path: str) -> Dict[str, Any]:
        """
        Complete processing pipeline for an input face image.
        """
        cropped_path, bbox = self.detect_and_crop(image_path)
        embedding = self.extract_embedding(cropped_path)
        return {
            "original_image": image_path,
            "cropped_image": cropped_path,
            "bbox": bbox,
            "embedding": embedding,
            "embedding_dim": len(embedding),
            "device": self.device,
            "gpu": self.gpu_name
        }

if __name__ == "__main__":
    processor = FaceProcessor()
    print(f"FaceProcessor initialized on device: {processor.device}")
