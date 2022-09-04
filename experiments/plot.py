# importing the required module
import matplotlib.pyplot as plt


plt.close('all')

# x axis values
x = [1, 2, 3]
# corresponding y axis values
y = [2, 4, 1]

# plotting the points
#plot = plt.plot(x, y)
fig, ax = plt.subplots()  # Create a figure containing a single axes.
ax.plot([1, 2, 3, 4], [1, 4, 2, 3])  # Plot some data on the axes.

fig.supxlabel('focus_absolute')
fig.supylabel('sharpness')
fig.suptitle('Sharpness(focus_absolute)')

y = [2, 8, 1]
ax.clear()
ax.grid(True)
fig.tight_layout()


ax.plot(x, y)
plt.show()
