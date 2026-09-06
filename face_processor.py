import os
import sys
import time
import urllib.request
import warnings
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

# Suppress informational messages from tensorflow and deepface
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
warnings.filterwarnings("ignore")

import cv2
import numpy as np

from config import CROP_MARGIN, BASE_DIR, BIOMETRIC_ACCURACY_MODE

MODELS_DIR = BASE_DIR / "models"
YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

class FaceProcessor:
    """
    Biometric Face Processing Engine supporting two operation modes:
    1. 'high' (Highest Accuracy): SOTA RetinaFace detector with 5-point landmark alignment
       + ArcFace 512-dimensional deep biometric embedding (99.83% LFW accuracy).
    2. 'fast' (Low Latency): OpenCV YuNet C++ ONNX detector + SFace 128-d extractor (sub-50ms).
    """
    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or BIOMETRIC_ACCURACY_MODE
        MODELS_DIR.mkdir(exist_ok=True)
        self._ensure_fast_models_downloaded()
        self._init_fast_models()

    def _ensure_fast_models_downloaded(self):
        if not YUNET_PATH.exists():
            print("  [*] Downloading lightweight YuNet face detector (~300KB)...")
            urllib.request.urlretrieve(YUNET_URL, YUNET_PATH)
        if not SFACE_PATH.exists():
            print("  [*] Downloading SFace recognition model (~37MB)...")
            urllib.request.urlretrieve(SFACE_URL, SFACE_PATH)

    def _init_fast_models(self):
        self.recognizer = None
        try:
            self.recognizer = cv2.FaceRecognizerSF_create(str(SFACE_PATH), "")
        except Exception:
            pass

    @staticmethod
    def capture_from_webcam(device_id: int = 0, output_path: str = "webcam_scan.jpg") -> str:
        """Captures a live frame from the user's laptop camera."""
        print(f"  [*] Initializing webcam device /dev/video{device_id}...")
        cap = cv2.VideoCapture(device_id)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera device /dev/video{device_id}")

        for _ in range(8):
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            raise RuntimeError("Failed to capture image frame from camera.")

        cv2.imwrite(output_path, frame)
        print(f"  [✓] Live webcam face scan captured: {output_path}")
        return output_path

    def detect_and_crop(self, image_path: str, output_path: Optional[str] = None) -> Tuple[str, Tuple[int, int, int, int], float]:
        """
        Detects facial boundary with RetinaFace or YuNet, applies padding, and exports cropped portrait.
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to read image at: {image_path}")

        h_img, w_img = img.shape[:2]
        x, y, w, h = None, None, None, None
        confidence = 1.0

        # Attempt 1: RetinaFace (Highest Accuracy) if in high mode
        if self.mode == "high":
            try:
                from deepface import DeepFace
                faces = DeepFace.extract_faces(
                    img_path=image_path,
                    detector_backend="retinaface",
                    enforce_detection=False,
                    align=True
                )
                if faces and len(faces) > 0:
                    best = max(faces, key=lambda f: f.get("confidence", 0))
                    fa = best["facial_area"]
                    x, y, w, h = fa["x"], fa["y"], fa["w"], fa["h"]
                    confidence = float(best.get("confidence", 1.0))
            except Exception:
                pass

        # Attempt 2: YuNet (Fast & Robust)
        if x is None:
            try:
                detector = cv2.FaceDetectorYN_create(str(YUNET_PATH), "", (w_img, h_img))
                detector.setInputSize((w_img, h_img))
                _, faces = detector.detect(img)
                if faces is not None and len(faces) > 0:
                    best_face = max(faces, key=lambda f: f[-1])
                    x, y, w, h = int(best_face[0]), int(best_face[1]), int(best_face[2]), int(best_face[3])
                    confidence = float(best_face[-1])
            except Exception:
                pass

        # Attempt 3: Haar Cascade fallback
        if x is None:
            try:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                face_cascade = cv2.CascadeClassifier(cascade_path)
                detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                if len(detected) > 0:
                    largest = max(detected, key=lambda b: b[2] * b[3])
                    x, y, w, h = int(largest[0]), int(largest[1]), int(largest[2]), int(largest[3])
                    confidence = 0.85
            except Exception:
                pass

        # Fallback: Center crop
        if x is None:
            w, h = int(w_img * 0.6), int(h_img * 0.6)
            x, y = (w_img - w) // 2, (h_img - h) // 2
            confidence = 0.50

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
        return output_path, (crop_x1, crop_y1, crop_x2 - crop_x1, crop_y2 - crop_y1), confidence

    def extract_embedding(self, image_path: str) -> Tuple[list, str]:
        """
        Extracts high-dimensional biometric embedding.
        Uses ArcFace 512-d in 'high' mode, SFace 128-d in 'fast' mode.
        """
        if self.mode == "high":
            try:
                from deepface import DeepFace
                rep = DeepFace.represent(
                    img_path=image_path,
                    model_name="ArcFace",
                    detector_backend="retinaface",
                    enforce_detection=False
                )
                if rep and len(rep) > 0:
                    return rep[0]["embedding"], "RetinaFace + ArcFace (512-d SOTA)"
            except Exception:
                pass

        # Fast SFace 128-d fallback
        img = cv2.imread(image_path)
        if self.recognizer is not None and img is not None:
            try:
                h_img, w_img = img.shape[:2]
                detector = cv2.FaceDetectorYN_create(str(YUNET_PATH), "", (w_img, h_img))
                detector.setInputSize((w_img, h_img))
                _, faces = detector.detect(img)
                if faces is not None and len(faces) > 0:
                    aligned = self.recognizer.alignCrop(img, faces[0])
                    feat = self.recognizer.feature(aligned)
                    return feat.flatten().tolist(), "YuNet + SFace (128-d Fast)"
            except Exception:
                pass

        # Normalized color/texture histogram fallback
        img_small = cv2.resize(img, (64, 64))
        hsv = cv2.cvtColor(img_small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten().tolist(), "Texture-Histogram (128-d Fallback)"

    @staticmethod
    def compute_perceptual_hash(image_path_or_array, hash_size: int = 8) -> str:
        """Computes 64-bit difference hash (dHash) for visual image invariance."""
        if isinstance(image_path_or_array, str):
            img = cv2.imread(image_path_or_array, cv2.IMREAD_GRAYSCALE)
        elif len(image_path_or_array.shape) == 3:
            img = cv2.cvtColor(image_path_or_array, cv2.COLOR_BGR2GRAY)
        else:
            img = image_path_or_array
        if img is None:
            return "0x0"
        resized = cv2.resize(img, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        val = sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])
        return hex(val)

    @staticmethod
    def compute_geometry(bbox: Tuple[int, int, int, int]) -> Dict[str, float]:
        """Extracts spatial aspect ratio and area metrics from bounding box."""
        x, y, w, h = bbox
        aspect = round(w / max(1, h), 3)
        return {
            "aspect_ratio": aspect,
            "width": w,
            "height": h,
            "area_px": w * h
        }

    def process(self, image_path: str, crop_output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Full biometric extraction with latency metrics and confidence report.
        crop_output_dir, if given, confines the cropped derivative to that
        directory instead of dropping it next to the source image.
        """
        t0 = time.perf_counter()
        crop_out = None
        if crop_output_dir:
            crop_out = str(Path(crop_output_dir) / f"temp_cropped_{Path(image_path).name}")
        cropped_path, bbox, confidence = self.detect_and_crop(image_path, output_path=crop_out)
        t_detect = time.perf_counter() - t0

        t1 = time.perf_counter()
        embedding, engine_name = self.extract_embedding(image_path)
        t_embed = time.perf_counter() - t1

        phash = self.compute_perceptual_hash(cropped_path)
        geom = self.compute_geometry(bbox)

        return {
            "original_image": image_path,
            "cropped_image": cropped_path,
            "bbox": bbox,
            "embedding": embedding,
            "embedding_dim": len(embedding),
            "confidence": confidence,
            "perceptual_hash": phash,
            "geometry": geom,
            "detect_ms": t_detect * 1000,
            "embed_ms": t_embed * 1000,
            "engine": engine_name,
            "mode": self.mode
        }

_processor_cache: Dict[str, "FaceProcessor"] = {}

def get_cached_processor(mode: str) -> "FaceProcessor":
    """
    Returns a process-wide FaceProcessor for the given mode, building it once
    and reusing it after that. Constructing one loads the ONNX/deepface
    models from disk, which is expensive enough (several seconds) that doing
    it fresh on every web request was a real source of slowness.
    """
    if mode not in _processor_cache:
        _processor_cache[mode] = FaceProcessor(mode=mode)
    return _processor_cache[mode]

if __name__ == "__main__":
    processor = FaceProcessor(mode="high")
    print(f"FaceProcessor initialized in '{processor.mode}' accuracy mode.")
