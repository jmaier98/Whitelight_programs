import ESP_driver as esp
import lockin_driver as lockin
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

# Create a figure and axis
fig, ax = plt.subplots()
xdata, ydata = [], []
ln, = plt.plot([], [], 'r-', animated=True)

# Set the limits of the axes


x0 = -10
x1 = 10
y0 = -15
y1 = -15.5
X = np.linspace(x0,x1,30)
Y = np.linspace(y0,y1,30)
wait_time = .5

ax.set_xlim(x0, x1)
ax.set_ylim(-1, 1)
window_size = 50
esp.moveY(y1)
def init():
    ln.set_data([], [])
    return ln,

def update(frame):
    esp.moveX(X[frame])
    time.sleep(wait_time)
    xdata.append(X[frame])
    ydata.append(lockin.readx3())
    if len(xdata) > window_size:
        xdata.pop(0)
        ydata.pop(0)
    ln.set_data(xdata, ydata)
    ax.set_ylim(0, max(ydata)*1.2)
    return ln,

# Create the animation object
ani = animation.FuncAnimation(
    fig, update, frames=np.arange(0, 30), init_func=init, blit=True, interval=100
)

plt.show()
