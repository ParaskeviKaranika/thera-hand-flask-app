import cv2
import mediapipe as mp
import time
import numpy as np
import random
from PIL import ImageFont, ImageDraw, Image
import os
import requests
import sys

# ------------------------------------------------------------
# ✅ Make project root importable (so we can import translations.py next to app.py)
# File: hand_exercises/last_game/last_game.py
# Root: .../Front-pwa (where app.py + translations.py are)
# ------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from translations import TRANSLATIONS  # shared translations with Flask
import hand_exercises  # your module with gesture logic

# ------------------------------------------------------------
# ✅ Args from Flask: username, age, lang
# subprocess.Popen(["python", game_path, username, str(age), lang])
# ------------------------------------------------------------
username = sys.argv[1] if len(sys.argv) > 1 else "Guest"
age = int(sys.argv[2]) if len(sys.argv) > 2 else 0
lang_arg = sys.argv[3] if len(sys.argv) > 3 else "el"
if lang_arg not in ("el", "en"):
    lang_arg = "el"


def tr(key: str, **kwargs) -> str:
    """Translation helper using TRANSLATIONS dict from Flask."""
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
    """
    Send stats to Flask.
    IMPORTANT:
    - game_name should be CANONICAL (stable) so Flask can translate it for UI.
      Use "exercise_4" instead of "Άσκηση 4" / "Exercise 4".
    - result should be CANONICAL: win/lose/completed/exit/game_over
      Flask will translate it for UI based on selected language.
    """
    data = {
        "username": username,
        "age": age,
        "game_name": "exercise_4",  # ✅ canonical (stable for DB grouping)
        "score": score,
        "time_seconds": time_seconds,
        "result": result,           # ✅ canonical (translated in Flask)
    }
    try:
        response = requests.post("http://127.0.0.1:5000/add_stat", json=data)
        if response.status_code == 200:
            print("✅ Stats sent to Flask")
        else:
            print(f"⚠️ Stats send error ({response.status_code}):", response.text)
    except Exception as e:
        print("⚠️ Stats send error:", e)


base_path = os.path.dirname(__file__)


def safe_imread(path: str):
    """Read an image safely even with non-ascii paths (Windows)."""
    with open(path, "rb") as f:
        data = np.frombuffer(f.read(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def put_text_pil(frame, text, position, font_size=32, color=(255, 255, 255)):
    """
    Draw text using PIL (supports Greek/Unicode better than cv2.putText).
    - Converts OpenCV BGR -> PIL RGB
    - Draws text with a TrueType font if available
    - Converts back to OpenCV BGR
    """
    frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    font_paths = [
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except Exception:
            continue

    if font is None:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(frame_pil)
    draw.text(position, text, font=font, fill=color)

    return cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)


# ------------------------------------------------------------
# ✅ Exercise definitions using IDs (not Greek strings)
# ------------------------------------------------------------
EXERCISES = [
    {
        "id": "close_all_fingers",
        "label_key": "game4_ex_close_all_fingers",
        "image": os.path.join(base_path, "hand_gesture_images", "close_all_fingers_fist.jpeg"),
        "detector": hand_exercises.detect_all_fingers_closed,
    },
    {
        "id": "open_only_thumb",
        "label_key": "game4_ex_open_only_thumb",
        "image": os.path.join(base_path, "hand_gesture_images", "open_thumb.jpeg"),
        "detector": hand_exercises.detect_only_thumb_open,
    },
    {
        "id": "close_index_thumb",
        "label_key": "game4_ex_close_index_thumb",
        "image": os.path.join(base_path, "hand_gesture_images", "close_index_thumb.jpeg"),
        "detector": lambda l: (
            (not hand_exercises.get_finger_states(l)["index"])
            and (not hand_exercises.get_finger_states(l)["thumb"])
            and all(hand_exercises.get_finger_states(l)[f] for f in ["middle", "ring", "pinky"])
        ),
    },
    {
        "id": "close_thumb_index_middle",
        "label_key": "game4_ex_close_thumb_index_middle",
        "image": os.path.join(base_path, "hand_gesture_images", "close_index_thumb_middle.jpeg"),
        "detector": lambda l: (
            (not hand_exercises.get_finger_states(l)["thumb"])
            and (not hand_exercises.get_finger_states(l)["index"])
            and (not hand_exercises.get_finger_states(l)["middle"])
            and all(hand_exercises.get_finger_states(l)[f] for f in ["ring", "pinky"])
        ),
    },
    {
        "id": "close_only_thumb",
        "label_key": "game4_ex_close_only_thumb",
        "image": os.path.join(base_path, "hand_gesture_images", "close_thumb.jpeg"),
        "detector": lambda l: (
            (not hand_exercises.get_finger_states(l)["thumb"])
            and all(hand_exercises.get_finger_states(l)[f] for f in ["index", "middle", "ring", "pinky"])
        ),
    },
]

# Preload images
for ex in EXERCISES:
    ex["image_data"] = safe_imread(ex["image"])


# ------------------------------------------------------------
# ✅ Parameters / progression
# ------------------------------------------------------------
rep_levels = [5, 10, 15, 20, 25]
current_level_index = 0

# Shuffle exercise order (use indices)
exercise_indices = list(range(len(EXERCISES)))
random.shuffle(exercise_indices)
current_exercise_pos = 0

score = 0
reps = 0
completed = False
restart_requested = False
exit_requested = False
start_time = time.time()

# Buttons: (x1, y1, x2, y2)
BUTTON_RESTART = (10, 10, 160, 60)
BUTTON_EXIT = (170, 10, 320, 60)

# ✅ Send stats only once per session (avoid duplicates on different exits)
stats_sent = False


def on_mouse(event, x, y, flags, param):
    global restart_requested, exit_requested
    if event == cv2.EVENT_LBUTTONDOWN:
        if BUTTON_RESTART[0] <= x <= BUTTON_RESTART[2] and BUTTON_RESTART[1] <= y <= BUTTON_RESTART[3]:
            restart_requested = True
        elif BUTTON_EXIT[0] <= x <= BUTTON_EXIT[2] and BUTTON_EXIT[1] <= y <= BUTTON_EXIT[3]:
            exit_requested = True


def reset_state():
    """Reset the full game state."""
    global current_level_index, current_exercise_pos, exercise_indices
    global score, reps, completed, restart_requested, exit_requested, start_time
    global stats_sent

    current_level_index = 0
    current_exercise_pos = 0
    exercise_indices = list(range(len(EXERCISES)))
    random.shuffle(exercise_indices)

    score = 0
    reps = 0
    completed = False
    restart_requested = False
    exit_requested = False
    start_time = time.time()

    # allow stats to be sent again after restart
    stats_sent = False


def maybe_send_stats(result: str):
    """Send stats once, with canonical result."""
    global stats_sent
    if stats_sent:
        return
    total_time = int(time.time() - start_time)
    send_stats(username, age, score, total_time, result)
    stats_sent = True


# ------------------------------------------------------------
# OpenCV window initialization
# ------------------------------------------------------------
cap = cv2.VideoCapture(0)
cv2.namedWindow("Last game", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Last game", on_mouse)

# MediaPipe setup
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

reset_state()

with mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
) as hands:

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            # Camera read failed -> treat as exit
            maybe_send_stats("exit")
            break

        # Mirror view
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # MediaPipe expects RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)

        # Convert back to BGR for OpenCV display
        frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        # ------------------------------------------------------------
        # ✅ End condition: all levels completed
        # ------------------------------------------------------------
        if current_level_index >= len(rep_levels):
            msg = tr("game4_all_done")
            frame = put_text_pil(frame, msg, (w // 6, h // 2), font_size=28, color=(0, 255, 255))
            cv2.imshow("Last game", frame)
            cv2.waitKey(5000)

            # ✅ canonical result
            maybe_send_stats("completed")
            break

        # Current exercise & target reps
        current_ex = EXERCISES[exercise_indices[current_exercise_pos]]
        target_reps = rep_levels[current_level_index]
        detector = current_ex["detector"]

        # Show exercise image
        target_image = cv2.resize(current_ex["image_data"], (200, 200))
        frame[70:270, 10:210] = target_image

        # ------------------------------------------------------------
        # ✅ HUD (i18n)
        # ------------------------------------------------------------
        elapsed_time = int(time.time() - start_time)
        frame = put_text_pil(frame, tr("game4_time", seconds=elapsed_time), (w - 260, 30), font_size=24)
        frame = put_text_pil(frame, tr("game4_reps", reps=reps, target=target_reps), (w - 260, 70), font_size=24)

        # Buttons
        cv2.rectangle(frame, BUTTON_RESTART[:2], BUTTON_RESTART[2:], (128, 128, 128), -1)
        cv2.rectangle(frame, BUTTON_EXIT[:2], BUTTON_EXIT[2:], (128, 128, 128), -1)
        frame = put_text_pil(frame, tr("game4_restart"), (BUTTON_RESTART[0] + 10, BUTTON_RESTART[1] + 10), font_size=20)
        frame = put_text_pil(frame, tr("game4_exit"), (BUTTON_EXIT[0] + 45, BUTTON_EXIT[1] + 10), font_size=20)

        # ------------------------------------------------------------
        # Hand gesture detection
        # ------------------------------------------------------------
        if (not completed) and results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw landmarks
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # If gesture matches, count repetition
                if detector(hand_landmarks):
                    reps += 1
                    time.sleep(0.5)  # prevent too-fast counting

        # ------------------------------------------------------------
        # If reps target reached -> move forward
        # ------------------------------------------------------------
        if reps >= target_reps:
            completed = True

            frame = put_text_pil(frame, tr("game4_ex_completed"), (w // 3, h // 2 - 30), font_size=28, color=(0, 255, 0))
            cv2.imshow("Last game", frame)
            cv2.waitKey(2000)

            # score system (your rule)
            score += 10

            # reset for next exercise
            reps = 0
            completed = False
            current_exercise_pos += 1

            # if all exercises in this level done -> next level
            if current_exercise_pos >= len(exercise_indices):
                current_exercise_pos = 0
                current_level_index += 1
                if current_level_index < len(rep_levels):
                    random.shuffle(exercise_indices)
                start_time = time.time()

            continue

        # ------------------------------------------------------------
        # Instruction bar at bottom (i18n)
        # ------------------------------------------------------------
        cv2.rectangle(frame, (0, h - 60), (w, h), (0, 0, 0), -1)
        instruction = tr("game4_instruction", instruction=tr(current_ex["label_key"]))
        frame = put_text_pil(frame, instruction, (10, h - 45), font_size=28)

        # ------------------------------------------------------------
        # Exit handling (button)
        # ------------------------------------------------------------
        if exit_requested:
            frame = put_text_pil(frame, tr("game4_exit_msg"), (w // 3, h // 2), font_size=30, color=(0, 0, 255))
            cv2.imshow("Last game", frame)
            cv2.waitKey(2000)

            # ✅ canonical exit result
            maybe_send_stats("exit")
            break

        # ------------------------------------------------------------
        # Restart handling
        # ------------------------------------------------------------
        if restart_requested:
            reset_state()
            continue

        # Show final frame
        cv2.imshow("Last game", frame)

        # Optional: press q to quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            # ✅ canonical exit result
            maybe_send_stats("exit")
            break

# Cleanup
cap.release()
cv2.destroyAllWindows()
