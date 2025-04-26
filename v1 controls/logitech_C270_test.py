import cv2

# Open the default camera (usually the first camera)
# If you have multiple cameras, you can specify the camera index (e.g., 0, 1, 2, ...)
camera_index = 0  # Change this if you have multiple cameras

# Open the camera
cap = cv2.VideoCapture(camera_index)

# Check if the camera opened successfully
if not cap.isOpened():
    print("Error: Could not open camera.")
else:
    print("Camera opened successfully.")

# Start capturing frames
while True:
    ret, frame = cap.read()
    
    if not ret:
        print("Error: Failed to capture frame.")
        break

    # Display the frame
    cv2.imshow("Logitech Camera", frame)

    # Wait for the 'q' key to exit the loop
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the camera and close any OpenCV windows
cap.release()
cv2.destroyAllWindows()
