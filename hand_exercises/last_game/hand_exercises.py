import cv2
import mediapipe as mp
import numpy as np
import math
from PIL import Image, ImageDraw, ImageFont

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
cap = cv2.VideoCapture(0)
# -----------------------------------------------------
# Function: put_text_pil
# Draw text on a video frame using PIL (better fonts than cv2.putText)
# -----------------------------------------------------

def put_text_pil(frame, text, position, font_size=40, color=(0, 255, 0)):
    # Convert OpenCV BGR image to PIL RGB format
    frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
     # Possible font paths (Linux, Windows, etc.)
    font_paths = [
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    font = None
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except IOError:
            continue
    if font is None:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(frame_pil)
    draw.text(position, text, font=font, fill=color)
    frame = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)
    return frame

# -----------------------------------------------------
# Function: calculate_distance
# Compute Euclidean distance between two 2D points
# -------------------------------------------------

def calculate_distance(point1, point2):
    x1, y1 = point1
    x2, y2 = point2
    return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# -----------------------------------------------------
# Function: get_finger_states
# Detect whether each finger is open or closed
# -----------------------------------------------------

def get_finger_states(landmarks):
    # Finger tip and dip landmark indices
    finger_tips = {'thumb': 4, 'index': 8, 'middle': 12, 'ring': 16, 'pinky': 20}
    finger_dips = {'thumb': 3, 'index': 7, 'middle': 11, 'ring': 15, 'pinky': 19}
    # Wrist and middle finger tip used to check hand orientation
    wrist = landmarks.landmark[0]
    middle_tip = landmarks.landmark[finger_tips['middle']]
    hand_orientation_up = middle_tip.y < wrist.y
    finger_states = {}
     # Extra check for thumb based on its distance to the middle base
    thumb_tip = landmarks.landmark[finger_tips['thumb']]
    middle_base = landmarks.landmark[9]
    thumb_to_middle_base_dist = calculate_distance((thumb_tip.x, thumb_tip.y), (middle_base.x, middle_base.y))
    # Iterate over all fingers and check if they are open/closed
    for finger, tip_idx in finger_tips.items():
        dip_idx = finger_dips[finger]
        tip = landmarks.landmark[tip_idx]
        dip = landmarks.landmark[dip_idx]
         # Distance between finger tip and dip
        distance = calculate_distance((tip.x, tip.y), (dip.x, dip.y))
        dy = tip.y - dip.y
        # Orientation-based condition: if hand is up, finger open = tip above dip
        if hand_orientation_up:
            is_open = dy < 0
        else:
            is_open = dy > 0
              # Thumb uses special logic because it moves sideways
        if finger == 'thumb':
            if thumb_to_middle_base_dist < 0.06:
                finger_states[finger] = False
            else:
                finger_states[finger] = distance > 0.05
        else:
            finger_states[finger] = distance > 0.04 and is_open
    return finger_states
# -----------------------------------------------------
# Function: detect_wrist_circle
# Check if wrist and fingers form a circle-like gesture
# -----------------------------------------------------

def detect_wrist_circle(landmarks):
    wrist = landmarks.landmark[0]
    finger_tips = [landmarks.landmark[i] for i in [8, 12, 16, 20]]
     # Distances between adjacent fingers
    distances = []
    for i in range(len(finger_tips) - 1):
        dist = calculate_distance((finger_tips[i].x, finger_tips[i].y), (finger_tips[i + 1].x, finger_tips[i + 1].y))
        distances.append(dist)
        # Distances from wrist to each finger tip
    wrist_distances = [calculate_distance((wrist.x, wrist.y), (tip.x, tip.y)) for tip in finger_tips]
     # Circle gesture condition: fingers close to each other + medium distance from wrist
    return np.mean(distances) < 0.05 and 0.1 < np.mean(wrist_distances) < 0.3

# -----------------------------------------------------
# Gesture detection functions (return True if gesture is detected)
# -----------------------------------------------------
def detect_open_fingers_except_thumb(landmarks):
    states = get_finger_states(landmarks)
    return (not states['thumb'] and all(states[f] for f in ['index', 'middle', 'ring', 'pinky']))

def detect_only_thumb_open(landmarks):
    states = get_finger_states(landmarks)
    return (states['thumb'] and all(not states[f] for f in ['index', 'middle', 'ring', 'pinky']))

def detect_all_fingers_closed(landmarks):
    states = get_finger_states(landmarks)
    return all(not states[f] for f in states)

def detect_only_ring_pinky_open(landmarks):
    states = get_finger_states(landmarks)
    return (not states['thumb'] and not states['index'] and not states['middle']
            and states['ring'] and states['pinky'])

def detect_middle_ring_pinky_open(landmarks):
    states = get_finger_states(landmarks)
    return (not states['thumb'] and not states['index']
            and states['middle'] and states['ring'] and states['pinky'])

def detect_circle_shape(landmarks):
    return detect_wrist_circle(landmarks)


# ----------------------
# Main Loop
# ----------------------
if __name__ == "__main__":
    with mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.5) as hands:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            # Convert BGR (OpenCV) to RGB (Mediapipe)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(frame_rgb)
            frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
             # If at least one hand is detected

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                     # Run different gesture detectors and display instructions

                    if detect_open_fingers_except_thumb(hand_landmarks):
                        frame = put_text_pil(frame, "Κλείσε τον αντίχειρα, άνοιξε τα υπόλοιπα δάχτυλα", (50, 50))
                    elif detect_middle_ring_pinky_open(hand_landmarks):
                        frame = put_text_pil(frame, "Κλείσε αντίχειρα και δείκτη, άνοιξε τα υπόλοιπα", (50, 50))
                    elif detect_all_fingers_closed(hand_landmarks):
                        frame = put_text_pil(frame, "Κλείσε όλα τα δάχτυλα", (50, 50))
                    elif detect_only_ring_pinky_open(hand_landmarks):
                        frame = put_text_pil(frame, "Άνοιξε μόνο παράμεσο και μικρό δάχτυλο", (50, 50))
                    elif detect_circle_shape(hand_landmarks):
                        frame = put_text_pil(frame, "Κάνε κύκλο τον καρπό", (50, 50))
                    elif detect_only_thumb_open(hand_landmarks):
                        frame = put_text_pil(frame, "Άνοιξε μόνο τον αντίχειρα", (50, 50))

            cv2.imshow('Αναγνώριση Χειρονομιών Χωρίς Ονομασίες', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
               break

    cap.release()
    cv2.destroyAllWindows()
