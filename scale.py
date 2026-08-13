import time
import numpy as np
import xy

print("Generating 10,000,000 random points...")
n = 10_000_000
x = np.random.normal(size=n)
y = np.random.normal(size=n)

start_time = time.time()

# Build a scatter plot
chart = xy.scatter_chart(
    xy.scatter(x, y)
)

# Export to HTML
chart.to_html("10m.html")

elapsed = time.time() - start_time
print(f"Done in {elapsed:.2f} seconds!")
print("Open '10m.html' in your browser to inspect pan and zoom.")