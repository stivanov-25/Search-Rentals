import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(1400, 2900, 50)
y = 75 * (abs(2100 - x)/300.0)**2

plt.plot(x, y)
plt.xlabel('Price')
plt.ylabel('Score')
plt.title('Price Score Function')
plt.grid(True)
plt.show()
