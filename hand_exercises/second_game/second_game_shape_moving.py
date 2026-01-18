import cv2
import mediapipe as mp
import numpy as np
import random
import time
import os
import requests
import sys

# ------------------------------------------------------------
# ✅ Make project root importable (so we can import translations.py next to app.py)
# File path: hand_exercises/second_game/second_game_shape_moving.py
# Root path:  hand_exercises/second_game -> hand_exercises -> project root
# ------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from translations import TRANSLATIONS  # uses the same translations.py as Flask (next to app.py)

# ------------------------------------------------------------
# ✅ Read args passed from Flask
# argv[1] = username, argv[2] = age, argv[3] = lang ("el" or "en")
# ------------------------------------------------------------
username = sys.argv[1] if len(sys.argv) > 1 else "Guest"
age = int(sys.argv[2]) if len(sys.argv) > 2 else 0
lang_arg = sys.argv[3] if len(sys.argv) > 3 else "el"
if lang_arg not in ("el", "en"):
    lang_arg = "el"


def tr(key: str, **kwargs) -> str:
    """
    Translation helper.
    - Looks up key in selected language dict
    - Falls back to Greek if missing, then to key itself
    - Supports format placeholders: tr("level_label", level=1, score=2, goal=10)
    """
    base = TRANSLATIONS.get("el", {})
    cur = TRANSLATIONS.get(lang_arg, base)
    text = cur.get(key) or base.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def send_stats(username, age, score, time_seconds, result):
    data = {
        "username": username,
        "age": age,
        "game_name": "Άσκηση 2",  # keep stable for DB grouping
        "score": score,
        "time_seconds": time_seconds,
        "result": result
    }
    try:
        response = requests.post("http://127.0.0.1:5000/add_stat", json=data)
        if response.status_code == 200:
            print("✅ Stats sent to Flask")
        else:
            print(f"⚠️ Stats send error ({response.status_code}):", response.text)
    except Exception as e:
        print("⚠️ Stats send error:", e)


# ------------------------------------------------------------
# MediaPipe hands setup
# ------------------------------------------------------------
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# ------------------------------------------------------------
# Shape dimensions
# ------------------------------------------------------------
circle_radius = 50
cube_size = 70
rectangle_width = 100
rectangle_height = 60
trian_size = 80

# ------------------------------------------------------------
# Target area (x, y, width, height)
# ------------------------------------------------------------
target_area = {'x': 100, 'y': 100, 'width': 200, 'height': 200}

# Level targets: 10 → 15 → 20 shapes
levels = [10, 15, 20]

# Time limit per level (seconds)
time_limit = 60

# Buttons for mouse click detection (win/lose screen)
restart_btn = {'x': 250, 'y': 200, 'w': 120, 'h': 50}
exit_btn = {'x': 250, 'y': 300, 'w': 120, 'h': 50}

# Global state
shapes = []
level_index = 0
score = 0
start_time = time.time()
game_state = "playing"  # "playing", "win", "lose"
holding_shape = None

# Highlight effect when a shape is placed correctly
highlight_start = None
highlight_duration = 0.5  # seconds


def create_random_shape():
    """Create and return a random shape dict."""
    shape_type = random.choice(['cube', 'rectangle', 'circle', 'triangle'])
    x = random.randint(100, 500)
    y = random.randint(100, 400)
    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    return {'type': shape_type, 'x': x, 'y': y, 'color': color}


def reset_game():
    """Reset the game to the initial state."""
    global shapes, level_index, score, start_time, game_state, holding_shape, highlight_start

    shapes = [
        {'type': 'cube', 'x': 500, 'y': 100, 'color': (0, 255, 255)},
        {'type': 'rectangle', 'x': 500, 'y': 200, 'color': (255, 255, 0)},
        {'type': 'circle', 'x': 500, 'y': 300, 'color': (0, 0, 0)},
        {'type': 'triangle', 'x': 500, 'y': 400, 'color': (128, 128, 128)}
    ]

    level_index = 0
    score = 0
    start_time = time.time()
    game_state = "playing"
    holding_shape = None
    highlight_start = None

    # reset “send once” flag when restarting
    if hasattr(send_stats, "sent"):
        delattr(send_stats, "sent")


def is_inside_function(x, y, shape):
    """Check whether point (x, y) is inside the given shape."""
    if shape['type'] == 'cube':
        return shape['x'] < x < shape['x'] + cube_size and shape['y'] < y < shape['y'] + cube_size
    elif shape['type'] == 'rectangle':
        return shape['x'] < x < shape['x'] + rectangle_width and shape['y'] < y < shape['y'] + rectangle_height
    elif shape['type'] == 'triangle':
        return shape['x'] < x < shape['x'] + trian_size and shape['y'] < y < shape['y'] + trian_size
    elif shape['type'] == 'circle':
        center = np.array([shape['x'] + circle_radius, shape['y'] + circle_radius])
        return np.linalg.norm(np.array([x, y]) - center) < circle_radius
    return False


def is_inside_target(shape):
    """Check whether the shape center is inside the target rectangle."""
    sx, sy = shape['x'], shape['y']
    if shape['type'] == 'circle':
        sx += circle_radius
        sy += circle_radius
    return (
        target_area['x'] < sx < target_area['x'] + target_area['width'] and
        target_area['y'] < sy < target_area['y'] + target_area['height']
    )


def draw_round_button(img, btn, color):
    """Draw a pill-shaped button."""
    x, y, w, h = btn['x'], btn['y'], btn['w'], btn['h']
    radius = h // 2
    cv2.rectangle(img, (x + radius, y), (x + w - radius, y + h), color, -1)
    cv2.circle(img, (x + radius, y + radius), radius, color, -1)
    cv2.circle(img, (x + w - radius, y + radius), radius, color, -1)


def mouse_cb(event, mx, my, flags, param):
    """Detect clicks on Restart / Exit buttons when in win/lose state."""
    global game_state

    if event == cv2.EVENT_LBUTTONDOWN and game_state in ("win", "lose"):
        # Restart
        if (restart_btn['x'] < mx < restart_btn['x'] + restart_btn['w'] and
                restart_btn['y'] < my < restart_btn['y'] + restart_btn['h']):
            reset_game()

        # Exit
        if (exit_btn['x'] < mx < exit_btn['x'] + exit_btn['w'] and
                exit_btn['y'] < my < exit_btn['y'] + exit_btn['h']):
            cap.release()
            cv2.destroyAllWindows()
            exit()


# Create OpenCV window and set mouse callback
cv2.namedWindow("Game")
cv2.setMouseCallback("Game", mouse_cb)

# Initial setup
reset_game()
cap = cv2.VideoCapture(0)

with mp_hands.Hands(min_detection_confidence=0.5,
                    min_tracking_confidence=0.5) as hands:

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Mirror image and convert for MediaPipe
        img_rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        img_rgb.flags.writeable = False
        results = hands.process(img_rgb)
        img_rgb.flags.writeable = True

        # Convert back to BGR for drawing
        image = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        h, w, _ = image.shape

        # Hand processing and shape grabbing
        if game_state == "playing" and results.multi_hand_landmarks:
            for hand_lms in results.multi_hand_landmarks:
                tips = [4, 8, 12, 16, 20]
                finger_positions = [
                    (int(hand_lms.landmark[i].x * w), int(hand_lms.landmark[i].y * h))
                    for i in tips
                ]

                avg_x = sum(p[0] for p in finger_positions) // 5
                avg_y = sum(p[1] for p in finger_positions) // 5

                # Check “fist closed” based on distances between fingertips
                dists = [
                    np.linalg.norm(np.array(finger_positions[i]) - np.array(finger_positions[j]))
                    for i in range(5) for j in range(i + 1, 5)
                ]
                grabbing = np.all(np.array(dists) < 50)

                # Start/stop holding
                if grabbing and holding_shape is None:
                    for idx, shp in enumerate(shapes):
                        if is_inside_function(avg_x, avg_y, shp):
                            holding_shape = idx
                            break
                elif not grabbing:
                    holding_shape = None

                # Move held shape to follow hand center
                if holding_shape is not None:
                    shp = shapes[holding_shape]
                    if shp['type'] == 'cube':
                        shp['x'] = avg_x - cube_size // 2
                        shp['y'] = avg_y - cube_size // 2
                    elif shp['type'] == 'rectangle':
                        shp['x'] = avg_x - rectangle_width // 2
                        shp['y'] = avg_y - rectangle_height // 2
                    elif shp['type'] == 'circle':
                        shp['x'] = avg_x - circle_radius
                        shp['y'] = avg_y - circle_radius
                    elif shp['type'] == 'triangle':
                        shp['x'] = avg_x - trian_size // 2
                        shp['y'] = avg_y - trian_size // 2

        # Check if held shape is placed inside target
        if game_state == "playing" and holding_shape is not None:
            shp = shapes[holding_shape]
            if is_inside_target(shp):
                score += 1
                holding_shape = None
                shapes.pop(shapes.index(shp))
                shapes.append(create_random_shape())
                highlight_start = time.time()

        # Timer and level progression
        elapsed = time.time() - start_time
        remaining = max(0, int(time_limit - elapsed))

        if game_state == "playing":
            if score >= levels[level_index]:
                if level_index < len(levels) - 1:
                    level_index += 1
                    score = 0
                    start_time = time.time()
                else:
                    game_state = "win"
            elif remaining == 0:
                game_state = "lose"

        # Target area border highlight effect
        if highlight_start and time.time() - highlight_start < highlight_duration:
            border_color = (0, 255, 0)
            border_thickness = 6
        else:
            border_color = (0, 255, 0)
            border_thickness = 2

        cv2.rectangle(
            image,
            (target_area['x'], target_area['y']),
            (target_area['x'] + target_area['width'], target_area['y'] + target_area['height']),
            border_color,
            border_thickness
        )

        # Draw shapes
        for shp in shapes:
            x, y, c = shp['x'], shp['y'], shp['color']
            if shp['type'] == 'cube':
                cv2.rectangle(image, (x, y), (x + cube_size, y + cube_size), c, -1)
            elif shp['type'] == 'rectangle':
                cv2.rectangle(image, (x, y), (x + rectangle_width, y + rectangle_height), c, -1)
            elif shp['type'] == 'circle':
                cv2.circle(image, (x + circle_radius, y + circle_radius), circle_radius, c, -1)
            elif shp['type'] == 'triangle':
                pts = np.array([[x, y + trian_size],
                                [x + trian_size // 2, y],
                                [x + trian_size, y + trian_size]], np.int32)
                cv2.fillPoly(image, [pts], c)

        # ------------------------------------------------------------
        # ✅ HUD (i18n)
        # ------------------------------------------------------------
        hud_level = tr("game2_level", level=level_index + 1, score=score, goal=levels[level_index])
        hud_time = tr("game2_time", seconds=remaining)

        cv2.putText(image, hud_level, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(image, hud_time, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # ------------------------------------------------------------
        # ✅ Win/Lose screen (i18n)
        # ------------------------------------------------------------
        if game_state in ("win", "lose"):
            color = (0, 255, 0) if game_state == "win" else (0, 255, 255)
            text = tr("game2_win") if game_state == "win" else tr("game2_lose")
            cv2.putText(image, text, (180, 150), cv2.FONT_HERSHEY_DUPLEX, 2, color, 3)

            button_color = (128, 128, 128)
            draw_round_button(image, restart_btn, button_color)
            draw_round_button(image, exit_btn, button_color)

            cv2.putText(image, tr("game2_restart"),
                        (restart_btn['x'] + 10, restart_btn['y'] + 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            cv2.putText(image, tr("game2_exit"),
                        (exit_btn['x'] + 35, exit_btn['y'] + 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # ✅ Send stats only once when finishing
            if not hasattr(send_stats, "sent"):
                total_time = int(time.time() - start_time)
                send_stats(username, age, score, total_time, game_state)
                send_stats.sent = True

        # Show frame
        cv2.imshow("Game", image)

        # ESC to exit
        if cv2.waitKey(1) & 0xFF == 27:
            break

cap.release()
cv2.destroyAllWindows()
