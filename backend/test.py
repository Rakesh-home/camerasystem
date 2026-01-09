import cv2
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

# Try to disable autofocus
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

# Try to set focus
result = cap.set(cv2.CAP_PROP_FOCUS, 100)
print(f"Set focus result: {result}")

# Read it back
focus = cap.get(cv2.CAP_PROP_FOCUS)
print(f"Current focus: {focus}")

cap.release()