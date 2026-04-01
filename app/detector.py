import cv2
import numpy as np
from ultralytics import YOLO
import easyocr
import torch

# Initialize models
vehicle_model = YOLO('yolov8s.pt')  # YOLOv8 small: much better accuracy for multiple plates
reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())

class VehicleDetector:
    def __init__(self):
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck in COCO
        self.fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)

    def detect_vehicles(self, frame):
        """Detect vehicle types and their bounding boxes."""
        results = vehicle_model(frame, verbose=False, conf=0.45)[0] # Confidence slightly increased for better multi-pass
        detections = []
        for box in results.boxes:
            cls = int(box.cls[0])
            if cls in self.vehicle_classes:
                conf = float(box.conf[0])
                coords = box.xyxy[0].cpu().numpy().astype(int)
                label = results.names[cls]
                detections.append({
                    'coords': coords,
                    'label': label,
                    'conf': conf
                })
        return detections

    def extract_plate(self, frame, vehicle_coords):
        """Twin-Pass optimized plate detection for multi-plate simultaneous identification."""
        x1, y1, x2, y2 = vehicle_coords
        w, h = x2 - x1, y2 - y1
        
        # Twin-Pass: Focus on bottom 60% of vehicle where plates usually are
        # This prevents identifying text on dashboards or signs behind the car
        v_crop_y1 = y1 + int(h * 0.4)
        vehicle_crop = frame[v_crop_y1:y2, x1:x2]
        
        if vehicle_crop.size == 0:
            return None, None

        ocr_results = reader.readtext(vehicle_crop, paragraph=False)
        
        best_text = ""
        best_box = None
        for (bbox, text, prob) in ocr_results:
            # High-accuracy filtering for ALPR formats
            clean_text = "".join(e for e in text if e.isalnum()).upper()
            if len(clean_text) >= 5 and prob > 0.35:
                if len(clean_text) > len(best_text):
                    best_text = clean_text
                    # Convert local crop coordinates to global frame coordinates
                    local_x1, local_y1 = bbox[0]
                    local_x2, local_y2 = bbox[2]
                    best_box = [
                        x1 + int(local_x1), 
                        v_crop_y1 + int(local_y1), 
                        x1 + int(local_x2), 
                        v_crop_y1 + int(local_y2)
                    ]
        
        return (best_text if best_text else None), best_box

    def detect_smoke(self, frame, vehicle_coords):
        """Standard smoke detection from the 4:40 PM version."""
        x1, y1, x2, y2 = vehicle_coords
        w = x2 - x1
        h = y2 - y1
        
        # Exhaust zone: Bottom 35% of the vehicle
        ex_x1 = x1 + int(w * 0.2)
        ex_x2 = x2 - int(w * 0.2)
        ex_y1 = y1 + int(h * 0.75)
        ex_y2 = y2
        
        exhaust_roi = frame[ex_y1:ex_y2, ex_x1:ex_x2]
        if exhaust_roi.size == 0:
            return False

        fgmask = self.fgbg.apply(exhaust_roi)
        # Calculate movement ratio
        movement_ratio = np.sum(fgmask > 200) / fgmask.size
        
        is_smoke_like = False
        if movement_ratio > 0.05:
            # Color profile for smoke (Gray/White/Dark)
            hsv_roi = cv2.cvtColor(exhaust_roi, cv2.COLOR_BGR2HSV)
            avg_sat = np.mean(hsv_roi[:, :, 1])
            if avg_sat < 50:
                is_smoke_like = True
        
        return is_smoke_like

def draw_annotations(frame, detections):
    for det in detections:
        cv2.putText(frame, f"{det['label']} {det.get('plate', '')}", (det['coords'][0], det['coords'][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        if det.get('smoke', False):
            cv2.rectangle(frame, (det['coords'][0], det['coords'][1]), (det['coords'][2], det['coords'][3]), (128, 0, 128), 3)
            cv2.putText(frame, "SMOKE", (det['coords'][0], det['coords'][3] + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 0, 128), 2)
        
        if det.get('plate_coords'):
            p_x1, p_y1, p_x2, p_y2 = det['plate_coords']
            cv2.rectangle(frame, (p_x1, p_y1), (p_x2, p_y2), (0, 255, 0), 2)

    return frame
