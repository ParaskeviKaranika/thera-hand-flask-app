import cv2  # Import OpenCV library for image processing and webcam access
import mediapipe as mp  # Import MediaPipe library for hand tracking and landmark detection
import numpy as np  # Import NumPy library for numerical operations, such as calculating distances

class HandTracker:
    def __init__(self, mode=False, num_hands=1, tracking_conf=0.7, detection_conf=0.7):
     #    Initialize the HandTracker class with MediaPipe Hands.
        #:param mode: If True, treats input as static images. If False, treats input as video stream.
       # :param num_hands: Maximum number of hands to detect.
       # :param tracking_conf: Minimum confidence value ([0,1]) for the hand tracking to be considered successful.
       # :param detection_conf: Minimum confidence value ([0,1]) for the initial hand detection.
       # """



        self.mode = mode
        self.num_hands = num_hands
        self.tracking_conf = float(tracking_conf)
        self.detection_conf = float(detection_conf)
        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.num_hands,
            min_tracking_confidence=self.tracking_conf,
            min_detection_confidence=self.detection_conf
        )
        self.mpDraw = mp.solutions.drawing_utils

    def find_hands(self, image, draw=True):
        #Detect hands in an image and optionally draw landmarks.
        #:param image: The input frame (BGR format).
       # :param draw: Whether to draw detected hand landmarks on the image.
        #:return: The processed image and the results object from MediaPipe.

        # Convert the image from BGR (OpenCV format) to RGB (MediaPipe format)
        imageRGB = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
          # Process the RGB image to detect hands
        results = self.hands.process(imageRGB)
         # If hands are detected and drawing is enabled, draw landmarks
        if draw and results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mpDraw.draw_landmarks(image, hand_landmarks, self.mpHands.HAND_CONNECTIONS)
        return image, results

    def findPosition(self, image, results, handNo=0):
        #Get the landmark positions of the detected hand.
        #:param image: The input frame (used for size reference).
        #:param results: The results object from MediaPipe containing landmarks.
        #:param handNo: Index of the hand (0 = first hand, 1 = second hand, etc.).
        #:return: List of (id, x, y) tuples for each landmark.
        lmList = []
        if results.multi_hand_landmarks:
            # Select the specified hand (if multiple hands are detected)
            hand = results.multi_hand_landmarks[handNo]
            h, w, _ = image.shape# Get image dimensions
            # Iterate over each landmark and convert normalized coords to pixel coords
            for id, lm in enumerate(hand.landmark):
                cx, cy = int(lm.x * w), int(lm.y * h)# Convert to pixel coordinates
                lmList.append((id, cx, cy)) # Append (landmark_id, x, y)
        return lmList

    def fingersClosed(self, lmList):

        #Check if the thumb and index finger are close together (pinch gesture).
        #:param lmList: List of landmarks [(id, x, y), ...].
        #:return: True if thumb tip and index finger tip are close, otherwise False.
        if len(lmList) < 9: # Ensure enough landmarks exist
            return False
        # Thumb tip coordinates (id = 4)
        tx, ty = lmList[4][1], lmList[4][2]   # Thumb tip
         # Index finger tip coordinates (id = 8)
        ix, iy = lmList[8][1], lmList[8][2]   # Index tip

        # Calculate Euclidean distance between thumb and index finger tips
        distance = np.linalg.norm([ix - tx, iy - ty])
         # Return True if distance is below threshold (fingers are "closed")

        return distance < 50  
