import tkinter as tk
import requests

def fetch_data():
    try:
        response = requests.get('http://localhost:5000/get-data')
        if response.status_code == 200:
            data = response.json()
            label.config(text=f"Received from Flask: {data['message']}")
    except Exception as e:
        label.config(text=f"Error fetching data: {e}")

# Create Tkinter window
root = tk.Tk()
root.title("Tkinter GUI")

label = tk.Label(root, text="Waiting for data...", font=("Arial", 16))
label.pack(pady=20)

button = tk.Button(root, text="Fetch Data from Flask", command=fetch_data)
button.pack(pady=10)

root.mainloop()
