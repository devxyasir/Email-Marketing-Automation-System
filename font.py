import tkinter as tk
from tkinter import font

root = tk.Tk()
available_fonts = list(font.families())  # Get the list of available fonts
root.destroy()

# Print the fonts
for f in sorted(available_fonts):
    print(f)
    with open('fonts.txt', 'w') as s:
        s.write(f + '\n' + f)
