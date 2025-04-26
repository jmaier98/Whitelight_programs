import ESP_driver as stage
import time

stage.rotate(0)
print("moved_z")
time.sleep(1)
stage.moveX(5)
print("moved_x")
time.sleep(1)
stage.moveY(5)
print("moved_y")
time.sleep(1)
