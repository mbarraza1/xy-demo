import xy
import numpy as np
import xy.pyplot as plt

###### API ######

# Create a fast line chart
chart = xy.line_chart(
    xy.line([1, 2, 3, 4, 5], [120, 180, 165, 240, 310], color="#7c3aed", width=3)
)

# Export options
chart.to_html("chart.html")
chart.to_png("chart.png")


###### PLOTLY ######

# Generate sample data
x = np.linspace(0, 10, 200)

# Matplotlib-standard syntax
fig, ax = plt.subplots()
ax.plot(x, np.sin(x), "r--", label="Sin Wave")
ax.plot(x, np.cos(x), "b-", label="Cos Wave")
ax.set_title("Matplotlib Syntax on XY Engine")
ax.legend()

# Displays the interactive window or renders in notebook
plt.show()


