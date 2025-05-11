import os
import sys
import time
import logging
import queue
import json
import random
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox, simpledialog
import pandas as pd
import datetime
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pymongo import MongoClient
import socket
import webbrowser
from threading import Lock
import pymongo

# MongoDB connection details
MONGO_URI = "mongodb+srv://JHpRv89n2ml6gxns:JHpRv89n2ml6gxns@cluster0.e9lk1.mongodb.net/"
DATABASE_NAME = "email_automation"
LICENSES_COLLECTION = "licenses"
SETTINGS_COLLECTION = "settings"
EMAIL_CONFIG_COLLECTION = "email_config"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("email_automation.log")
    ]
)

logger = logging.getLogger(__name__)

# Custom logging handler to redirect logs to GUI
class QueueHandler(logging.Handler):
    """Custom handler to redirect logs to a queue"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        # Format the record as a string and add it to the queue
        msg = self.format(record)
        self.log_queue.put(msg)

def get_system_id():
    """Get a unique system ID based on hardware"""
    return str(uuid.getnode())  # Uses MAC address as a unique hardware identifier

def check_hardware_id_in_database():
    """Check if the current hardware ID exists in the database with a valid license"""
    try:
        # Get current system ID
        current_system_id = get_system_id()
        
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        collection = db[LICENSES_COLLECTION]
        
        # First check if hardware ID exists at all (regardless of active status)
        license_data = collection.find_one({"registered_system_id": current_system_id})
        
        # If no license found for this hardware ID
        if not license_data:
            return None, "No license found for this hardware ID"
        
        # At this point, we have a license. Check expiry
        if "expiryDate" in license_data and license_data["expiryDate"]:
            expiry_date = license_data["expiryDate"]
            if isinstance(expiry_date, str):
                expiry_date = datetime.datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
            
            now = datetime.datetime.now()
            
            # If expired
            if now > expiry_date:
                return None, "Your license has expired. Please contact the developer for renewal."
            
            # Calculate remaining time
            time_diff = expiry_date - now
            days_left = time_diff.days
            hours_left = time_diff.seconds // 3600
            
            remaining_time = f"{days_left} days, {hours_left} hours"
            license_data["remaining_time"] = remaining_time
        else:
            license_data["remaining_time"] = "Unlimited"
        
        return license_data, "License is valid"
        
    except Exception as e:
        logging.error(f"Error checking hardware ID in database: {str(e)}")
        return None, f"Error connecting to license server: {str(e)}"

def activate_license(license_code):
    """Activate a license by binding it to the current system"""
    try:
        system_id = get_system_id()
        
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        collection = db[LICENSES_COLLECTION]
        
        # Check if license exists
        license_data = collection.find_one({"License_Code": license_code})
        
        if not license_data:
            return False, "Invalid license code", None
            
        # Check if license is already used on another system
        if license_data.get("registered_system_id") and license_data.get("registered_system_id") != system_id:
            return False, "This license is already registered to a different computer. Licenses cannot be transferred between systems. Please contact the developer for assistance.", None
        
        # Check expiry date if it exists
        if "expiryDate" in license_data and license_data["expiryDate"]:
            expiry_date = license_data["expiryDate"]
            if isinstance(expiry_date, str):
                expiry_date = datetime.datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
            
            now = datetime.datetime.now()
            
            # If already expired, don't allow activation
            if now > expiry_date:
                return False, "License has expired and cannot be activated", None
            
            # Calculate and inform about remaining time
            days_left = (expiry_date.date() - now.date()).days
            
            if days_left == 0:
                # Calculate hours left when expiry is today
                hours_left = int((expiry_date - now).total_seconds() / 3600)
                if hours_left < 1:
                    return False, "License is about to expire", None
                
                time_remaining = f"{hours_left} hours"
                time_frame = f"{hours_left} hours"
            else:
                time_remaining = f"{days_left} days"
                time_frame = f"{days_left} days"
            
            # Update license with system ID and activation date
            activation_time = datetime.datetime.now()
            
            collection.update_one(
                {"License_Code": license_code},
                {"$set": {
                    "registered_system_id": system_id, 
                    "activationDate": activation_time,
                    "timeFrame": time_frame
                }}
            )
            
            license_data["remaining_time"] = time_remaining
            license_data["timeFrame"] = time_frame
            license_data["registered_system_id"] = system_id
            license_data["activationDate"] = activation_time
            
            return True, f"License activated successfully (Expires in {time_remaining})", license_data
        else:
            # No expiry date, unlimited license
            activation_time = datetime.datetime.now()
            collection.update_one(
                {"License_Code": license_code},
                {"$set": {
                    "registered_system_id": system_id, 
                    "activationDate": activation_time,
                    "timeFrame": "unlimited"
                }}
            )
            
            license_data["remaining_time"] = "Unlimited"
            license_data["timeFrame"] = "unlimited"
            license_data["registered_system_id"] = system_id
            license_data["activationDate"] = activation_time
            
            return True, "License activated successfully (No expiration date)", license_data
            
    except Exception as e:
        logger.error(f"Error activating license: {str(e)}")
        return False, f"Error: {str(e)}", None

class LicenseActivationWindow:
    """Window for license activation when no valid license is found"""
    def __init__(self, root, error_message=None):
        self.root = root
        self.root.title("License Activation")
        self.root.geometry("450x350")
        self.root.resizable(False, False)
        
        # Center the window
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 450) // 2
        y = (screen_height - 350) // 2
        self.root.geometry(f"450x350+{x}+{y}")

        # Create frame with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # Create UI elements
        ttk.Label(main_frame, text="Email Automation Pro", font=("Helvetica", 16, "bold")).pack(pady=5)
        ttk.Label(main_frame, text="License Activation Required", font=("Helvetica", 12)).pack(pady=5)
        
        # Show error message if provided
        if error_message:
            error_label = ttk.Label(
                main_frame, 
                text=error_message,
                foreground="red",
                wraplength=380,
                justify="center",
                font=("Helvetica", 10, "bold")
            )
            error_label.pack(pady=10)
        
        # License code entry
        ttk.Label(main_frame, text="Enter your license code:", font=("Helvetica", 9)).pack(pady=(10, 2))
        self.license_var = tk.StringVar()
        self.license_entry = ttk.Entry(main_frame, textvariable=self.license_var, width=40)
        self.license_entry.pack(pady=2)
        self.license_entry.focus()

        # System ID display
        system_id = get_system_id()
        ttk.Label(main_frame, text="Your Hardware ID:", font=("Helvetica", 9)).pack(pady=(10, 2))
        
        # Create a read-only entry field for the system ID (makes it easy to copy)
        system_id_var = tk.StringVar(value=system_id)
        system_id_entry = ttk.Entry(main_frame, textvariable=system_id_var, width=40, font=("Courier", 9))
        system_id_entry.pack(pady=2)
        system_id_entry.configure(state="readonly")  # Read-only but still copyable
        
        # Add a copy button for convenience
        def copy_system_id():
            self.root.clipboard_clear()
            self.root.clipboard_append(system_id)
            self.status_var.set("Hardware ID copied to clipboard!")
            self.root.update()
            
        ttk.Button(main_frame, text="Copy Hardware ID", command=copy_system_id).pack(pady=(5, 10))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=5)
        
        ttk.Button(button_frame, text="Activate License", command=self.validate_license).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Exit", command=self.root.destroy).pack(side="left", padx=5)
        
        # Status message
        self.status_var = tk.StringVar()
        self.status_var.set("Please enter your license code to activate")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(pady=5)
    
    def validate_license(self):
        """Validate and activate the license code"""
        license_code = self.license_var.get().strip()
        
        if not license_code:
            self.status_var.set("Please enter a license code")
            return
        
        # Update status
        self.status_var.set("Validating license...")
        self.root.update()
        
        # Attempt to activate the license
        success, message, license_data = activate_license(license_code)
        
        if success:
            self.status_var.set(message)
            self.root.update()
            
            # Show success message and proceed to main application
            messagebox.showinfo("License Activated", message)
            self.root.destroy()  # Close the license window
            
            # Show the main application
            show_main_application(license_data)
        else:
            self.status_var.set(message)

class SplashScreen:
    """Splash screen window shown at application startup"""
    def __init__(self, parent, license_data=None):
        # Create the splash screen toplevel window
        self.splash = tk.Toplevel(parent)
        self.splash.title("")
        self.parent = parent
        self.license_data = license_data
        
        # Remove window decorations
        self.splash.overrideredirect(True)
        
        # Calculate center position
        screen_width = parent.winfo_screenwidth()
        screen_height = parent.winfo_screenheight()
        splash_width = 600
        splash_height = 400
        x_position = (screen_width - splash_width) // 2
        y_position = (screen_height - splash_height) // 2
        
        # Set window size and position
        self.splash.geometry(f"{splash_width}x{splash_height}+{x_position}+{y_position}")
        
        # Make splash screen appear on top
        self.splash.attributes("-topmost", True)
        
        # Create container frame
        container = ttk.Frame(self.splash)
        container.pack(fill="both", expand=True)
        
        # Add background color
        container.configure(style="Splash.TFrame")
        
        # Add logo or banner
        try:
            # Add your logo path here
            logo_path = "logo.png"
            if os.path.exists(logo_path):
                logo = tk.PhotoImage(file=logo_path)
                logo_label = ttk.Label(container, image=logo)
                logo_label.image = logo  # Keep a reference
                logo_label.pack(pady=(50, 20))
        except Exception as e:
            logging.error(f"Error loading logo: {str(e)}")
        
        # Application name with large font
        app_name = ttk.Label(
            container, 
            text="Email Automation Pro",
            font=("Helvetica", 24, "bold"),
            style="SplashTitle.TLabel"
        )
        app_name.pack(pady=10)
        
        # Version info
        version_label = ttk.Label(
            container, 
            text="Version 1.0.0",
            style="SplashVersion.TLabel"
        )
        version_label.pack()
        
        # Progress bar
        self.progress = ttk.Progressbar(
            container,
            orient="horizontal",
            length=400,
            mode="determinate"
        )
        self.progress.pack(pady=30, padx=50)
        
        # Status message
        self.status_var = tk.StringVar()
        self.status_var.set("Initializing...")
        self.status_label = ttk.Label(
            container, 
            textvariable=self.status_var,
            style="SplashStatus.TLabel"
        )
        self.status_label.pack(pady=10)
        
        # Copyright info
        copyright_label = ttk.Label(
            container, 
            text=" 2025 DevSecure. All rights reserved.",
            style="SplashCopyright.TLabel"
        )
        copyright_label.pack(pady=(30, 0))
        
        # Center the window on screen
        self.splash.update_idletasks()
        self.splash.update()
    
    def start_progress(self, duration=2):
        """Animate progress bar for given duration in seconds, non-blocking"""
        steps = 20  # Reduced number of steps for faster animation
        increment = 100 / steps
        delay_ms = int((duration * 1000) / steps)
        
        self.progress_value = 0
        
        def update_progress(step):
            if step > steps or not hasattr(self, 'splash') or not self.splash.winfo_exists():
                return
                
            # Calculate progress value
            self.progress_value = min(step * increment, 100)
            
            # Update progress bar
            self.progress["value"] = self.progress_value
            
            # Update status message
            if step < 5:
                self.status_var.set("Initializing components...")
            elif step < 10:
                self.status_var.set("Loading database connection...")
            elif step < 15:
                self.status_var.set("Loading email templates...")
            else:
                self.status_var.set("Preparing dashboard...")
                
            # Schedule next update
            self.splash.after(delay_ms, lambda: update_progress(step + 1))
        
        # Start progress updates
        update_progress(1)
    
    def destroy(self):
        """Close the splash screen"""
        self.splash.destroy()

def show_main_application(license_data=None):
    """Show the main application window"""
    # Create and configure the main application window
    root = tk.Tk()
    root.title("Email Automation Pro")
    root.geometry("900x700")
    root.minsize(800, 600)
    
    # Configure window to appear centered
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - 900) // 2
    y = (screen_height - 700) // 2
    root.geometry(f"900x700+{x}+{y}")
    
    # Hide the main window temporarily
    root.withdraw()
    
    # Create a toplevel splash window
    splash = tk.Toplevel(root)
    splash.title("")
    splash.overrideredirect(True)  # Remove window decorations
    
    # Position splash window
    splash_width = 600
    splash_height = 400
    splash_x = (screen_width - splash_width) // 2
    splash_y = (screen_height - splash_height) // 2
    splash.geometry(f"{splash_width}x{splash_height}+{splash_x}+{splash_y}")
    splash.attributes("-topmost", True)
    
    # Apply styles to splash screen
    style = ttk.Style()
    style.configure("Splash.TFrame", background="#1a2633")  # Dark blue background
    style.configure("SplashTitle.TLabel", background="#1a2633", foreground="#ffffff", font=("Candara Light", 24, "bold"))
    style.configure("SplashVersion.TLabel", background="#1a2633", foreground="#aaaaaa", font=("Candara Light", 10))
    style.configure("SplashStatus.TLabel", background="#1a2633", foreground="#ffffff", font=("Candara Light", 9))
    style.configure("SplashCopyright.TLabel", background="#1a2633", foreground="#aaaaaa", font=("Candara Light", 8))
    style.configure("Horizontal.TProgressbar", background="#4a8dde", troughcolor="#2c3e50")
    
    # Create splash content
    container = ttk.Frame(splash, style="Splash.TFrame")
    container.pack(fill="both", expand=True)
    
    # App title
    ttk.Label(
        container, 
        text="Email Automation Pro",
        style="SplashTitle.TLabel"
    ).pack(pady=(80, 10))
    
    # Version info
    ttk.Label(
        container, 
        text="Version 1.0.0",
        style="SplashVersion.TLabel"
    ).pack()
    
    # Progress bar
    progress = ttk.Progressbar(
        container,
        orient="horizontal",
        length=400,
        mode="determinate",
        style="Horizontal.TProgressbar"
    )
    progress.pack(pady=30, padx=50)
    
    # Status message
    status_var = tk.StringVar()
    status_var.set("Initializing application...")
    status_label = ttk.Label(
        container, 
        textvariable=status_var,
        style="SplashStatus.TLabel"
    )
    status_label.pack(pady=10)
    
    # Copyright info
    ttk.Label(
        container, 
        text=" 2025 DevSecure. All rights reserved.",
        style="SplashCopyright.TLabel"
    ).pack(pady=(30, 0))
    
    # Update splash
    splash.update_idletasks()
    
    # Create app instance for storing initialization state
    app = None
    
    # Flag to track if initialization is complete
    init_complete = {"status": False, "success": False, "app": None}
    
    # Flag to determine offline mode
    offline_mode = {"enabled": False}
    
    # Update UI safely from main thread
    def safe_update_progress(value, text=None):
        if not splash.winfo_exists():
            return
        try:
            # Update progress and text
            progress["value"] = value
            if text:
                status_var.set(text)
            # Force update to prevent "not responding"
            splash.update_idletasks()
        except Exception as e:
            logging.error(f"Error updating progress: {str(e)}")
    
    # Function to initialize database in background thread
    def init_database():
        try:
            hardware_id = get_system_id()
            # Try to initialize MongoDB with very short timeout
            settings_manager = SettingsManager(hardware_id)
            if not settings_manager.initialized:
                offline_mode["enabled"] = True
                logging.warning("Database connection failed. Operating in offline mode.")
            return settings_manager
        except Exception as e:
            logging.error(f"Database initialization error: {str(e)}")
            offline_mode["enabled"] = True
            return None
    
    # Function to initialize the app but executed in chunks on the main thread
    def init_app_step(step):
        nonlocal app
        
        try:
            if step == 1:
                # Start database connection in background
                safe_update_progress(20, "Connecting to database...")
                db_thread = threading.Thread(target=lambda: init_database(), daemon=True)
                db_thread.start()
                
                # Create basic app instance without full initialization
                safe_update_progress(30, "Creating application instance...")
                app = EmailAutomationGUI(root, license_data, init_stage=1)
                
                # Wait 1 second max for database
                db_thread.join(1.0)
                if offline_mode["enabled"]:
                    safe_update_progress(40, "Database unavailable. Starting in offline mode...")
                else:
                    safe_update_progress(40, "Database connection established...")
                
                root.after(50, lambda: init_app_step(2))
            
            elif step == 2:
                # Initialize styles and critical UI components
                safe_update_progress(60, "Setting up user interface...")
                if app:
                    app.initialize_styles()
                    app.initialize_critical_ui()
                root.after(50, lambda: init_app_step(3))
            
            elif step == 3:
                # Complete initialization
                safe_update_progress(80, "Loading configurations...")
                if app:
                    # Pass offline mode status to app
                    app.offline_mode = offline_mode["enabled"]
                    app.complete_initialization()
                root.after(50, lambda: init_app_step(4))
            
            elif step == 4:
                # Finalize
                safe_update_progress(100, "Ready to launch!")
                init_complete["status"] = True
                init_complete["success"] = True
                init_complete["app"] = app
                root.after(200, finish_loading)
        
        except Exception as e:
            logging.error(f"Error in initialization step {step}: {str(e)}")
            init_complete["status"] = True
            init_complete["success"] = False
            root.after(10, finish_loading)
    
    # Function to close splash and show main app
    def finish_loading():
        try:
            if splash.winfo_exists():
                # Close splash screen
                splash.destroy()
            
            # Show main window if initialization was successful
            if init_complete["success"]:
                root.deiconify()
                root.lift()
                root.focus_force()
                
                # Show offline mode message if needed
                if offline_mode["enabled"] and app:
                    root.after(500, lambda: messagebox.showwarning(
                        "Offline Mode", 
                        "Unable to connect to the database. The application is running in offline mode.\n\n"
                        "Some features may be limited until the database connection is restored."
                    ))
            else:
                # Show error if app failed to initialize
                messagebox.showerror("Error", "Failed to initialize application. Please restart.")
                root.destroy()
        except Exception as e:
            logging.error(f"Error in finish_loading: {str(e)}")
            # Last resort - try to show the window anyway
            try:
                root.deiconify()
            except Exception as final_e:
                logging.error(f"Final error showing window: {str(final_e)}")
    
    # Start initialization after a brief delay
    root.after(100, lambda: init_app_step(1))
    
    # Start main loop
    root.mainloop()

class EmailAutomationGUI:
    """Main GUI class for the Email Automation application"""
    def __init__(self, root, license_data=None, init_stage=0):
        """Initialize the GUI with staged initialization"""
        self.root = root
        self.root.title("Email Automation Pro")
        
        # Store license data
        self.license_data = license_data
        
        # Flag for offline mode
        self.offline_mode = False
        
        # Initialize log queue
        self.log_queue = queue.Queue()
        
        # Initialize components with minimal defaults
        self.email_config = {}
        self.sender_thread = None
        self.active_threads = []
        self.shutdown_in_progress = False
        
        # Set up custom logging handler with minimal config
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(queue_handler)
        
        # If not using staged initialization, initialize everything at once
        if init_stage == 0:
            self.initialize_styles()
            self.initialize_critical_ui()
            self.complete_initialization()
    
    def initialize_styles(self):
        """Initialize styles for the application"""
        self._create_styles()
    
    def initialize_critical_ui(self):
        """Initialize critical UI components"""
        self._create_menu()
        self._create_main_frame()
        
        # Schedule log updates
        self.root.after(100, self._update_log)
    
    def complete_initialization(self):
        """Complete the initialization process"""
        # Add bottom bar
        self._add_bottom_bar()
        
        # Update status based on offline mode
        if self.offline_mode:
            self.add_log("Application started in offline mode. Database connection unavailable.")
            if hasattr(self, 'status_var'):
                self.status_var.set("OFFLINE MODE")
        
        # Schedule non-critical initialization tasks
        self.root.after(100, self._delayed_initialization)

    def _delayed_initialization(self):
        """Perform non-critical initialization after UI is visible"""
        try:
            # Load user settings if available (will use defaults if DB unavailable)
            self._load_user_settings()
            
            # Load SMTP settings if available (may be None in offline mode)
            self._load_smtp_settings()
            
            # Update the log
            self.add_log("Initialization complete")
            
        except Exception as e:
            logging.error(f"Error in delayed initialization: {str(e)}")
            
    def _load_user_settings(self):
        """Load user settings with fallback to defaults if offline"""
        try:
            # Get hardware ID
            hardware_id = get_system_id()
            
            # Try to get application settings
            if not self.offline_mode:
                app_settings = get_application_settings(hardware_id)
                if app_settings:
                    # Apply theme if specified
                    if 'theme' in app_settings:
                        self.apply_theme(app_settings.get('theme', 'darkblue'))
                    # Apply font size if specified
                    if 'font_size' in app_settings:
                        self._apply_font_size(app_settings.get('font_size', 'medium'))
            else:
                # Use defaults in offline mode
                self.apply_theme('darkblue')
        except Exception as e:
            logging.error(f"Error loading user settings: {str(e)}")
            # Use defaults on error
            self.apply_theme('darkblue')
    
    def _load_smtp_settings(self):
        """Load SMTP settings from database"""
        if not self.offline_mode:
            try:
                # Get SMTP settings from database
                smtp_settings = get_smtp_settings(get_system_id())
                
                # Update UI thread-safely
                if smtp_settings:
                    def update_config():
                        self.email_config = {
                            'email': smtp_settings.get('email', ''),
                            'password': smtp_settings.get('password', ''),
                            'smtp_server': smtp_settings.get('smtp_server', ''),
                            'smtp_port': smtp_settings.get('smtp_port', 587),
                            'use_tls': smtp_settings.get('use_tls', True),
                            'csv_path': smtp_settings.get('csv_path', '')
                        }
                        self.add_log(f"Loaded email configuration for {self.email_config['email']}")
                    
                    # Update in UI thread
                    self.root.after(0, update_config)
                else:
                    self.root.after(0, lambda: self.add_log("No saved email configuration found"))
            except Exception as e:
                self.root.after(0, lambda: self.add_log(f"Error loading configuration: {str(e)}"))
    
    def add_log(self, message):
        """Add a log message to the log display"""
        if hasattr(self, 'log_text'):
            self.log_text.configure(state='normal')
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state='disabled')
    
    def _update_log(self):
        """Check the log queue and update the log display"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.add_log(message)
        except queue.Empty:
            pass
        finally:
            # Schedule the next update
            self.root.after(100, self._update_log)
    
    def _create_email_config_tab(self, notebook):
        """Create the email configuration tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Email Setup")
        
        # Add a message about using the Settings tab
        note_frame = ttk.Frame(tab, padding=20)
        note_frame.pack(fill="both", expand=True)
        
        ttk.Label(
            note_frame, 
            text="Email configuration has moved to the Settings tab",
            font=("Helvetica", 14, "bold")
        ).pack(pady=20)
        
        message = ("To configure your email settings, please go to the Settings tab.\n\n"
                  "In the Settings tab, you can:\n"
                  "• Configure your email account and SMTP server details\n"
                  "• Set up application appearance preferences\n"
                  "• Configure advanced email settings like signatures\n\n"
                  "Your settings will be saved securely and associated with your license.")
        
        ttk.Label(
            note_frame, 
            text=message,
            wraplength=500,
            justify="left",
            font=("Helvetica", 11)
        ).pack(pady=20)
        
        button_frame = ttk.Frame(note_frame)
        button_frame.pack(pady=20)
        
        # Fix the navigation to Settings tab by using the parent notebook
        ttk.Button(
            button_frame,
            text="Go to Settings",
            command=lambda: self.notebook.select(2)  # Settings tab is the 3rd tab (index 2)
        ).pack(side="left", padx=10)
        
        return tab
    
    def _create_email_composer_tab(self, notebook):
        """Create the email composer tab with draft saving/loading functionality"""
        # Create main tab frame
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Compose Email")
        
        # Create a horizontal paned window to divide drafts sidebar and composer
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create drafts sidebar frame
        drafts_frame = ttk.LabelFrame(paned, text="Saved Drafts")
        paned.add(drafts_frame, weight=1)
        
        # Create drafts listbox with scrollbar
        drafts_container = ttk.Frame(drafts_frame)
        drafts_container.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        
        self.drafts_listbox = tk.Listbox(drafts_container, bg="#ffffff", fg="#000000", 
                                        selectbackground="#90EE90", selectforeground="#000000",
                                        font=("Candara Light", 9))
        
        scrollbar = ttk.Scrollbar(drafts_container, command=self.drafts_listbox.yview)
        self.drafts_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.drafts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.drafts_listbox.bind("<<ListboxSelect>>", self._on_draft_selected)
        
        # Add draft controls
        draft_buttons = ttk.Frame(drafts_frame)
        draft_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        # Create load draft button
        load_draft_btn = ttk.Button(draft_buttons, text="Load Selected", 
                                  command=self._load_selected_draft)
        load_draft_btn.pack(side=tk.LEFT, padx=2)
        
        # Create delete draft button
        delete_draft_btn = ttk.Button(draft_buttons, text="Delete Selected", 
                                    command=self._delete_selected_draft)
        delete_draft_btn.pack(side=tk.LEFT, padx=2)
        
        # Create composer frame
        composer_frame = ttk.Frame(paned)
        paned.add(composer_frame, weight=3)
        
        # Create toolbar for composer
        composer_toolbar = ttk.Frame(composer_frame)
        composer_toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # Campaign name field
        ttk.Label(composer_toolbar, text="Campaign Name:").pack(side=tk.LEFT, padx=5)
        self.campaign_name_var = tk.StringVar()
        ttk.Entry(composer_toolbar, textvariable=self.campaign_name_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # New, Save, Start buttons in the composer tab
        ttk.Button(composer_toolbar, text="New", 
                 command=self._new_campaign, 
                 style="Primary.TButton").pack(side=tk.LEFT, padx=2)
        
        ttk.Button(composer_toolbar, text="Save", 
                 command=self._save_campaign, 
                 style="Primary.TButton").pack(side=tk.LEFT, padx=2)
        
        ttk.Button(composer_toolbar, text="Start", 
                 command=self._start_campaign, 
                 style="Primary.TButton").pack(side=tk.LEFT, padx=2)
        
        # Create email form
        form_frame = ttk.Frame(composer_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Recipients
        recipient_frame = ttk.LabelFrame(form_frame, text="Recipients")
        recipient_frame.pack(fill=tk.X, padx=5, pady=5)
        
        recipient_controls = ttk.Frame(recipient_frame)
        recipient_controls.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(recipient_controls, text="To:").pack(side=tk.LEFT, padx=5)
        self.recipients_var = tk.StringVar()
        ttk.Entry(recipient_controls, textvariable=self.recipients_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(recipient_controls, text="Import List", 
                 command=self.import_email_list).pack(side=tk.LEFT, padx=5)
        
        # Email details
        details_frame = ttk.LabelFrame(form_frame, text="Email Details")
        details_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Subject
        subject_frame = ttk.Frame(details_frame)
        subject_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(subject_frame, text="Subject:").pack(side=tk.LEFT, padx=5)
        self.subject_var = tk.StringVar()
        ttk.Entry(subject_frame, textvariable=self.subject_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # SMTP settings shortcut
        smtp_frame = ttk.Frame(details_frame)
        smtp_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(smtp_frame, text="Email Provider:").pack(side=tk.LEFT, padx=5)
        
        # Provider dropdown
        self.provider_var = tk.StringVar(value="Gmail")
        providers = ["Gmail", "Outlook", "Yahoo", "Custom"]
        provider_dropdown = ttk.Combobox(smtp_frame, textvariable=self.provider_var, values=providers, width=15)
        provider_dropdown.pack(side=tk.LEFT, padx=5)
        provider_dropdown.bind("<<ComboboxSelected>>", self._on_provider_change)
        
        ttk.Button(smtp_frame, text="Configure SMTP", 
                 command=self.show_smtp_settings).pack(side=tk.LEFT, padx=5)
        
        # Content
        content_frame = ttk.LabelFrame(form_frame, text="Email Content")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Editor toolbar
        editor_toolbar = ttk.Frame(content_frame)
        editor_toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # HTML mode toggle
        self.html_mode_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(editor_toolbar, text="HTML Mode", 
                      variable=self.html_mode_var,
                      command=self._toggle_html_mode).pack(side=tk.LEFT, padx=5)
        
        # Text editor
        editor_frame = ttk.Frame(content_frame)
        editor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.email_content_text = scrolledtext.ScrolledText(editor_frame, wrap=tk.WORD, 
                                                        width=80, height=20,
                                                        bg="#ffffff", fg="#000000",
                                                        font=("Candara Light", 10))
        self.email_content_text.pack(fill=tk.BOTH, expand=True)
        
        # Sample HTML template
        html_template = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #4a6ea9; color: white; padding: 10px; text-align: center; }
        .content { padding: 20px; }
        .footer { font-size: small; color: #666; text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Your Email Title</h1>
    </div>
    <div class="content">
        <p>Hello {name},</p>
        <p>This is a sample email template. You can edit this content to create your own email.</p>
        <p>Use the {placeholders} to personalize your emails.</p>
        <p>Best regards,<br>Your Name</p>
    </div>
    <div class="footer">
        <p> 2025 Your Company. All rights reserved.</p>
        <p>To unsubscribe, click <a href="{unsubscribe_link}">here</a>.</p>
    </div>
</body>
</html>
"""
        # Initialize with template
        self.email_content_text.insert("1.0", html_template)
        
        # Load saved drafts if any
        self._load_drafts()
        
        return tab
    
    def _create_log_tab(self, notebook):
        """Create the logs tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Logs")
        
        # Create scrolled text widget for logs
        self.log_text = scrolledtext.ScrolledText(tab, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.configure(state='disabled')
        
        # Add initial log entry
        self.add_log("Log initialized. License active and valid.")
    
    def _create_settings_tab(self, notebook):
        """Create the settings tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Settings")
        
        # Get hardware ID
        hardware_id = get_system_id()
        
        # Create settings page
        settings_page = SettingsPage(tab, hardware_id)
        settings_page.pack(fill=tk.BOTH, expand=True)
        
        return tab
    
    def _create_about_tab(self, notebook):
        """Create the about tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="About")
        
        # Add content
        about_frame = ttk.Frame(tab, padding=20)
        about_frame.pack(fill=tk.BOTH, expand=True)
        
        # App title
        ttk.Label(
            about_frame, 
            text="Email Automation Pro",
            font=("Candara Light", 18, "bold")
        ).pack(pady=(0, 10))
        
        # Version
        ttk.Label(
            about_frame, 
            text="Version 1.0.0",
            font=("Candara Light", 10)
        ).pack(pady=(0, 20))
        
        # Description
        ttk.Label(
            about_frame, 
            text="A professional application for sending bulk emails with secure licensing and modern UI.",
            wraplength=500,
            justify="center",
            font=("Candara Light", 10)
        ).pack(pady=(0, 30))
        
        # Copyright
        ttk.Label(
            about_frame, 
            text=" 2025 All Rights Reserved",
            font=("Candara Light", 9)
        ).pack()
    
    def _save_config(self):
        """Save email configuration"""
        messagebox.showinfo("Save Configuration", "Configuration saved successfully")
    
    def _load_config(self):
        """Load email configuration"""
        messagebox.showinfo("Load Configuration", "Configuration loaded successfully")
    
    def _export_log(self):
        """Export logs to a file"""
        messagebox.showinfo("Export Logs", "Logs exported successfully")
    
    def _show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About Email Automation Pro",
            "Email Automation Pro\nVersion 1.0.0\n\nA professional application for sending bulk emails with secure licensing."
        )
    
    def _show_license_info(self):
        """Show dialog with detailed license information"""
        if self.license_data:
            expiry_date = self.license_data.get("expiryDate", "Unlimited")
            if expiry_date and expiry_date != "Unlimited":
                if isinstance(expiry_date, str):
                    expiry_date = datetime.datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
                expiry_date = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
            
            activation_date = self.license_data.get("activationDate", "Unknown")
            if activation_date and activation_date != "Unknown":
                if isinstance(activation_date, str):
                    activation_date = datetime.datetime.fromisoformat(activation_date.replace("Z", "+00:00"))
                activation_date = activation_date.strftime("%Y-%m-%d %H:%M:%S")
            
            license_code = self.license_data.get("License_Code", "Unknown")
            time_frame = self.license_data.get("timeFrame", "Unknown")
            remaining_time = self.license_data.get("remaining_time", "Unknown")
            
            message = (
                f"License Information:\n\n"
                f"License Code: {license_code}\n"
                f"Status: Active\n"
                f"Time Frame: {time_frame}\n"
                f"Remaining Time: {remaining_time}\n"
                f"Activation Date: {activation_date}\n"
                f"Expiry Date: {expiry_date}\n\n"
                f"System ID: {get_system_id()}"
            )
        else:
            message = (
                f"No valid license found.\n\n"
                f"Please contact support to obtain a license.\n"
                f"System ID: {get_system_id()}"
            )
        
        messagebox.showinfo("License Information", message)
    
    def _show_welcome_message(self):
        """Show welcome message with license information"""
        if self.license_data:
            remaining_time = self.license_data.get("remaining_time", "Unknown")
            messagebox.showinfo(
                "Welcome to Email Automation Pro",
                f"License is active and valid.\nTime remaining: {remaining_time}"
            )
    
    def _on_close(self):
        """Handle window close event"""
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            if self.sender_thread and self.sender_thread.is_alive():
                self.sender_thread.stop()
            self.root.destroy()
    
    def _create_menu(self):
        """Create the menu bar"""
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Configuration", command=self._save_config)
        file_menu.add_command(label="Load Configuration", command=self._load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Export Logs", command=self._export_log)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # License menu
        license_menu = tk.Menu(menubar, tearoff=0)
        license_menu.add_command(label="License Information", command=self._show_license_info)
        menubar.add_cascade(label="License", menu=license_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)
        
        # Create toolbar
        self.create_toolbar()
        
        return menubar
    
    def create_toolbar(self):
        """Create toolbar with common actions"""
        try:
            # Create toolbar frame with raised relief for better visibility
            toolbar_frame = tk.Frame(self.root, bg="#1a2633", bd=1, relief=tk.RAISED)
            toolbar_frame.pack(side=tk.TOP, fill=tk.X)
            
            # Style for toolbar buttons - special green style with black text
            toolbar_button_style = {
                'bg': '#90EE90',        # Light green
                'fg': '#000000',        # Black text
                'activebackground': '#7CCD7C',  # Darker green when active
                'activeforeground': '#000000',  # Keep text black when active
                'font': ('Arial', 9, 'bold'),
                'borderwidth': 1,
                'relief': 'raised',
                'padx': 8,
                'pady': 4,
                'width': 10
            }
            
            # New Campaign button
            tk.Button(toolbar_frame, text="New", command=self._new_campaign, **toolbar_button_style).pack(side=tk.LEFT, padx=2, pady=2)
            
            # Open Campaign button
            tk.Button(toolbar_frame, text="Open", command=self._load_config, **toolbar_button_style).pack(side=tk.LEFT, padx=2, pady=2)
            
            # Save Campaign button
            tk.Button(toolbar_frame, text="Save", command=self._save_config, **toolbar_button_style).pack(side=tk.LEFT, padx=2, pady=2)
            
            # Separator
            tk.Frame(toolbar_frame, width=2, height=24, bg="#3e78c2").pack(side=tk.LEFT, padx=5, pady=2)
            
            # Configure SMTP button
            tk.Button(toolbar_frame, text="Configure", command=self.show_smtp_settings, **toolbar_button_style).pack(side=tk.LEFT, padx=2, pady=2)
            
            # Import List button
            tk.Button(toolbar_frame, text="Import List", command=self.import_email_list, **toolbar_button_style).pack(side=tk.LEFT, padx=2, pady=2)
            
            # Save Log button
            tk.Button(toolbar_frame, text="Save Log", command=self.save_email_log, **toolbar_button_style).pack(side=tk.LEFT, padx=2, pady=2)
            
            # Separator
            tk.Frame(toolbar_frame, width=2, height=24, bg="#3e78c2").pack(side=tk.LEFT, padx=5, pady=2)
            
            # Send Test button
            tk.Button(toolbar_frame, text="Send Test", command=self._send_test_email, **toolbar_button_style).pack(side=tk.LEFT, padx=2, pady=2)
            
            # Start Campaign button
            start_button = tk.Button(toolbar_frame, text="Start Campaign", 
                               bg='#98FB98',        # More vibrant green
                               fg='#000000',        # Black text
                               activebackground='#74C274',
                               activeforeground='#000000',
                               font=('Arial', 10, 'bold'),
                               borderwidth=2,
                               relief='raised',
                               padx=10,
                               pady=4,
                               width=12)
            start_button.pack(side=tk.LEFT, padx=5, pady=2)
        except Exception as e:
            logging.error(f"Error creating toolbar: {str(e)}")
    
    def _new_campaign(self):
        """Create a new campaign"""
        # Placeholder for new campaign functionality
        messagebox.showinfo("New Campaign", "Creating a new campaign")
    
    def _send_test_email(self):
        """Send a test email"""
        # Placeholder for test email functionality
        messagebox.showinfo("Test Email", "Sending a test email")
    
    def import_email_list(self):
        """Import email list from a file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Import Email List",
                filetypes=[
                    ("CSV Files", "*.csv"),
                    ("Text Files", "*.txt"),
                    ("Excel Files", "*.xlsx"),
                    ("All Files", "*.*")
                ]
            )
            
            if not file_path:
                return  # User cancelled
                
            # Simple placeholder - in a real implementation, this would parse the file
            messagebox.showinfo("Import Success", f"Email list imported from: {file_path}")
            self.add_log(f"Imported email list from {file_path}")
            
        except Exception as e:
            logging.error(f"Error importing email list: {str(e)}")
            messagebox.showerror("Import Error", f"Failed to import email list: {str(e)}")
    
    def save_email_log(self):
        """Save the current email sending log to a file"""
        try:
            # Get the log content
            log_content = self.log_text.get("1.0", "end-1c")
            
            if not log_content.strip():
                messagebox.showinfo("Empty Log", "The log is empty. Nothing to save.")
                return
            
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                title="Save Email Log",
                defaultextension=".txt",
                filetypes=[
                    ("Text Files", "*.txt"),
                    ("Log Files", "*.log"),
                    ("All Files", "*.*")
                ]
            )
            
            if not file_path:
                return  # User cancelled
            
            # Save log content to file
            with open(file_path, 'w', encoding='utf-8') as f:
                # Add timestamp and header
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"Email Automation - Log Export\n")
                f.write(f"Generated: {timestamp}\n")
                f.write(f"{'-' * 50}\n\n")
                
                # Write actual log content
                f.write(log_content)
            
            # Show success message
            messagebox.showinfo("Log Saved", f"Log has been saved to:\n{file_path}")
            
            # Log the action
            self.add_log(f"Log exported to {file_path}")
                
        except Exception as e:
            logging.error(f"Error saving email log: {str(e)}")
            messagebox.showerror("Save Error", f"Failed to save log: {str(e)}")
    
    def export_logs(self):
        """Export logs to a file (alias for save_email_log)"""
        self.save_email_log()
    
    def show_smtp_settings(self, provider=None):
        """Show SMTP server configuration dialog with provider presets"""
        try:
            # Create a toplevel window
            smtp_window = tk.Toplevel(self.root)
            smtp_window.title("SMTP Configuration")
            smtp_window.geometry("600x650")
            smtp_window.minsize(600, 650)
            smtp_window.transient(self.root)  # Set as transient to main window
            smtp_window.grab_set()  # Make window modal
            
            # Apply current theme to window
            smtp_window.configure(bg="#1a2633")
            
            # Create frame for settings
            main_frame = ttk.Frame(smtp_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Title label
            ttk.Label(
                main_frame, 
                text="SMTP Server Configuration",
                style="Title.TLabel"
            ).pack(pady=(0, 15))
            
            # Provider selector
            provider_frame = ttk.Frame(main_frame)
            provider_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(provider_frame, text="Email Provider:").pack(side=tk.LEFT, padx=5)
            
            # Provider variable
            provider_var = tk.StringVar(value=provider if provider else "Custom")
            
            # Provider options
            providers = [
                "Gmail", 
                "Outlook", 
                "Yahoo", 
                "Custom"
            ]
            
            # Provider dropdown
            provider_combo = ttk.Combobox(provider_frame, 
                                       textvariable=provider_var, 
                                       values=providers,
                                       state="readonly",
                                       width=15)
            provider_combo.pack(side=tk.LEFT, padx=5)
            
            # Create form fields
            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill=tk.X, expand=True, pady=10)
            
            # Server settings fields
            ttk.Label(form_frame, text="SMTP Server:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            server_var = tk.StringVar()
            server_entry = ttk.Entry(form_frame, textvariable=server_var, width=30)
            server_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
            
            ttk.Label(form_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            port_var = tk.StringVar(value="587")
            port_entry = ttk.Entry(form_frame, textvariable=port_var, width=10)
            port_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
            
            # Security type
            ttk.Label(form_frame, text="Security:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
            security_var = tk.StringVar(value="TLS")
            security_frame = ttk.Frame(form_frame)
            security_frame.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
            
            ttk.Radiobutton(security_frame, text="TLS", variable=security_var, value="TLS").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Radiobutton(security_frame, text="SSL", variable=security_var, value="SSL").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Radiobutton(security_frame, text="None", variable=security_var, value="None").pack(side=tk.LEFT)
            
            ttk.Label(form_frame, text="Username:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
            username_var = tk.StringVar()
            username_entry = ttk.Entry(form_frame, textvariable=username_var, width=30)
            username_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
            
            ttk.Label(form_frame, text="Password:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
            password_var = tk.StringVar()
            password_entry = ttk.Entry(form_frame, textvariable=password_var, width=30, show="•")
            password_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
            
            # Show/hide password
            show_password_var = tk.BooleanVar(value=False)
            
            def toggle_password():
                if show_password_var.get():
                    password_entry.config(show="")
                else:
                    password_entry.config(show="•")
            
            ttk.Checkbutton(
                form_frame, 
                text="Show password", 
                variable=show_password_var,
                command=toggle_password
            ).grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
            
            # From email details
            ttk.Label(form_frame, text="From Name:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
            from_name_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=from_name_var, width=30).grid(row=6, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
            
            ttk.Label(form_frame, text="From Email:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
            from_email_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=from_email_var, width=30).grid(row=7, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
            
            # Set values based on provider
            def set_provider_defaults(event=None):
                selected_provider = provider_var.get()
                
                if selected_provider == "Gmail":
                    server_var.set("smtp.gmail.com")
                    port_var.set("587")
                    security_var.set("TLS")
                    # Update username hint if empty
                    if not username_var.get() or username_var.get() == "your_outlook_email@outlook.com" or username_var.get() == "your_yahoo_email@yahoo.com":
                        username_var.set("your_gmail@gmail.com")
                    # Set from email if empty
                    if not from_email_var.get():
                        from_email_var.set(username_var.get())
                    
                elif selected_provider == "Outlook":
                    server_var.set("smtp.office365.com")
                    port_var.set("587")
                    security_var.set("TLS")
                    # Update username hint if empty
                    if not username_var.get() or username_var.get() == "your_gmail@gmail.com" or username_var.get() == "your_yahoo_email@yahoo.com":
                        username_var.set("your_outlook_email@outlook.com")
                    # Set from email if empty
                    if not from_email_var.get():
                        from_email_var.set(username_var.get())
                    
                elif selected_provider == "Yahoo":
                    server_var.set("smtp.mail.yahoo.com")
                    port_var.set("587")
                    security_var.set("TLS")
                    # Update username hint if empty
                    if not username_var.get() or username_var.get() == "your_gmail@gmail.com" or username_var.get() == "your_outlook_email@outlook.com":
                        username_var.set("your_yahoo_email@yahoo.com")
                    # Set from email if empty
                    if not from_email_var.get():
                        from_email_var.set(username_var.get())
                
                # For Custom, don't change anything
                
            # Set initial values based on provider
            if provider:
                set_provider_defaults()
                
            # Bind provider change event
            provider_combo.bind("<<ComboboxSelected>>", set_provider_defaults)
            
            # Help text
            help_frame = ttk.Frame(main_frame)
            help_frame.pack(fill=tk.X, pady=10)
            
            help_text = """
Gmail and Yahoo require an App Password if you have 2-factor authentication enabled.
For Gmail: Go to your Google Account > Security > App passwords
For Outlook: Use your full email address as the username
            """
            
            help_label = ttk.Label(
                help_frame,
                text=help_text,
                wraplength=450,
                justify="left",
                foreground="#3e78c2"
            )
            help_label.pack(pady=5)
            
            # Gmail app password link
            if provider == "Gmail":
                gmail_link = ttk.Label(
                    help_frame,
                    text="Click here to learn about Google App Passwords",
                    foreground="#3e78c2",
                    cursor="hand2",
                    font=("Candara Light", 9, "underline")
                )
                gmail_link.pack(pady=5)
                gmail_link.bind("<Button-1>", lambda e: webbrowser.open("https://support.google.com/accounts/answer/185833"))
            
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, expand=True, pady=(15, 0))
            
            # Test connection function
            def test_connection():
                # Validate inputs
                if not server_var.get() or not port_var.get() or not username_var.get() or not password_var.get():
                    messagebox.showerror("Validation Error", "Please fill in all required fields")
                    return
                
                # Create progress window
                progress_window = tk.Toplevel(smtp_window)
                progress_window.title("Testing Connection")
                progress_window.geometry("300x100")
                progress_window.transient(smtp_window)
                progress_window.grab_set()
                
                ttk.Label(progress_window, text="Testing SMTP connection...").pack(pady=(15, 10))
                progress = ttk.Progressbar(progress_window, mode="indeterminate")
                progress.pack(fill=tk.X, padx=20)
                progress.start()
                
                # Function to run in background
                def run_test():
                    try:
                        import smtplib
                        
                        # Connect to server
                        if security_var.get() == "SSL":
                            server = smtplib.SMTP_SSL(server_var.get(), int(port_var.get()), timeout=10)
                        else:
                            server = smtplib.SMTP(server_var.get(), int(port_var.get()), timeout=10)
                        
                        # Start TLS if needed
                        if security_var.get() == "TLS":
                            server.starttls()
                        
                        # Login
                        server.login(username_var.get(), password_var.get())
                        
                        # Close connection
                        server.quit()
                        
                        # Show success
                        smtp_window.after(0, lambda: show_result(True, "Connection successful! SMTP settings are valid."))
                    except Exception as e:
                        # Show error
                        smtp_window.after(0, lambda: show_result(False, f"Connection failed: {str(e)}"))
                
                # Function to show result
                def show_result(success, message):
                    # Close progress window
                    progress_window.destroy()
                    
                    # Show result message
                    if success:
                        messagebox.showinfo("Connection Test", message)
                    else:
                        messagebox.showerror("Connection Test", message)
                
                # Start test in background
                threading.Thread(target=run_test, daemon=True).start()
            
            # Save settings function
            def save_settings():
                # Validate inputs
                if not server_var.get() or not port_var.get() or not username_var.get() or not from_email_var.get():
                    messagebox.showerror("Validation Error", "Please fill in all required fields")
                    return
                
                # Create settings dict
                smtp_settings = {
                    'server': server_var.get(),
                    'port': port_var.get(),
                    'security': security_var.get(),
                    'username': username_var.get(),
                    'password': password_var.get(),
                    'from_name': from_name_var.get(),
                    'from_email': from_email_var.get(),
                    'provider': provider_var.get()
                }
                
                try:
                    # In a real implementation, this would save to file or database
                    # For now, we'll just store it in a class variable
                    self.smtp_settings = smtp_settings
                    
                    # Show success
                    messagebox.showinfo("Settings Saved", "SMTP settings have been saved successfully.")
                    
                    # Close window
                    smtp_window.destroy()
                    
                    # Log action
                    self.add_log(f"Updated SMTP settings for {provider_var.get()}")
                    
                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to save settings: {str(e)}")
            
            # Test button
            test_button = ttk.Button(
                button_frame, 
                text="Test Connection", 
                style="Primary.TButton",
                command=test_connection
            )
            test_button.pack(side=tk.LEFT, padx=5)
            
            # Save button
            save_button = ttk.Button(
                button_frame, 
                text="Save Settings", 
                style="Primary.TButton",
                command=save_settings
            )
            save_button.pack(side=tk.LEFT, padx=5)
            
            # Cancel button
            cancel_button = ttk.Button(
                button_frame, 
                text="Cancel", 
                command=smtp_window.destroy
            )
            cancel_button.pack(side=tk.LEFT, padx=5)
            
            # Center the window
            smtp_window.update_idletasks()
            width = smtp_window.winfo_width()
            height = smtp_window.winfo_height()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
            smtp_window.geometry(f"+{x}+{y}")
            
        except Exception as e:
            logging.error(f"Error showing SMTP settings: {str(e)}")
            messagebox.showerror("Error", f"Failed to open SMTP settings: {str(e)}")
    
    def _add_bottom_bar(self):
        """Add bottom bar with license information and developer info"""
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        
        # License information display
        if self.license_data:
            remaining_time = self.license_data.get("remaining_time", "Unknown")
            
            if remaining_time == "Unlimited":
                license_text = f"License: Active (Unlimited)"
                style = "License.Valid.TLabel"
            elif "day" in remaining_time and int(remaining_time.split()[0]) <= 7:
                license_text = f"License: Active (Expires in {remaining_time})"
                style = "License.Expiring.TLabel"
            else:
                license_text = f"License: Active (Expires in {remaining_time})"
                style = "License.Valid.TLabel"
        else:
            license_text = "License: Unknown"
            style = "License.TLabel"
        
        license_label = ttk.Label(
            bottom_frame,
            text=license_text,
            style=style
        )
        license_label.pack(side=tk.LEFT)
        
        # Developer information
        dev_label = ttk.Label(
            bottom_frame, 
            text="Email Automation Pro v1.0.0 | Developed by Your Name",
            font=("Candara Light", 7),
            foreground="#999999"
        )
        dev_label.pack(side=tk.RIGHT)
    
    def _create_main_frame(self):
        """Create the main frame with tabs"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tabs - create them in order of importance for user
        # Most important tabs first for quicker perceived loading
        self._create_email_composer_tab(self.notebook)  # Email tab first (most used)
        self._create_email_config_tab(self.notebook)    # Config tab second
        self._create_settings_tab(self.notebook)        # Settings tab third
        self._create_log_tab(self.notebook)             # Logs tab fourth
        self._create_about_tab(self.notebook)           # About tab last (least important)
    
    def _create_styles(self):
        """Create custom ttk styles for a modern, VIP appearance with bubble buttons"""
        style = ttk.Style()
        
        # Define stylish fonts for the application
        title_font = "Verdana"  # Modern clean font for titles
        body_font = "Candara Light"  # Clean readable font for body text
        button_font = "Arial"   # Clean font for buttons
        accent_font = "Georgia" # Stylish font for accents
        
        # Standard font sizes
        base_size = 9
        title_size = 16
        subtitle_size = 12
        
        # Get current platform
        current_platform = style.theme_use()
        
        # Load application theme setting if available
        hardware_id = get_system_id()
        app_settings = get_application_settings(hardware_id)
        
        # Set theme based on settings or default to 'darkblue'
        theme_setting = "darkblue"  # Default to dark blue theme
        if app_settings and 'theme' in app_settings:
            theme_setting = app_settings.get('theme', 'darkblue')
        
        # Apply custom theme
        self.apply_theme(theme_setting)
    
    def apply_theme(self, theme_name="darkblue"):
        """Apply the specified theme to the application in a thread-safe manner"""
        # Only run on the main thread - schedule if called from another thread
        if threading.current_thread() is not threading.main_thread():
            logging.debug("Scheduling theme application on main thread")
            self.root.after(0, lambda: self.apply_theme(theme_name))
            return
            
        try:
            logging.info(f"Applying theme: {theme_name}")
            style = ttk.Style()
            
            # Define stylish fonts for the application
            title_font = "Verdana"  # Modern clean font for titles
            body_font = "Candara Light"  # Clean readable font for body text
            button_font = "Arial"   # Clean font for buttons
            accent_font = "Georgia" # Stylish font for accents
            
            # Standard font sizes
            base_size = 9
            title_size = 16
            subtitle_size = 12
            
            # Beautiful green button colors with low opacity effect
            button_bg = "#90EE90"        # Light green
            button_hover = "#7CCD7C"     # Slightly darker green for hover
            button_pressed = "#548B54"   # Darker green for pressed state
            button_text = "#000000"      # Bold black text
            
            if theme_name == "light":
                # Light theme
                bg_color = "#f5f5f5"
                fg_color = "#333333"
                accent_color = "#4a6ea9"  # Blue accent for light theme
                highlight_bg = "#ddeeff"
                tab_selected_bg = "#E0FFE0"  # Very light green for selected tabs
                tab_selected_fg = "#000000"  # Black text
                frame_bg = bg_color
                
            elif theme_name == "dark":
                # Dark theme
                bg_color = "#222222"
                fg_color = "#ffffff"
                accent_color = "#5d8cc9"  # Light blue accent for dark theme
                highlight_bg = "#334455"
                tab_selected_bg = "#3D5D3D"  # Darker green for selected tabs
                tab_selected_fg = "#FFFFFF"  # White text for contrast
                frame_bg = bg_color
                
            else:  # darkblue theme (default)
                # Dark blue VIP theme
                bg_color = "#1a2633"      # Dark blue background
                fg_color = "#ffffff"      # White text
                accent_color = "#3e78c2"  # Medium blue accent
                highlight_bg = "#264673"
                tab_selected_bg = "#385038"  # Dark green for selected tabs
                tab_selected_fg = "#FFFFFF"  # White text for contrast
                frame_bg = bg_color
            
            # Configure root window
            self.root.configure(bg=bg_color)
            
            # Configure main frame style with theme look
            style.configure("TFrame", background=frame_bg, font=(body_font, base_size))
            style.configure("TLabel", background=frame_bg, foreground=fg_color, font=(body_font, base_size))
            style.configure("TLabelframe", background=frame_bg, foreground=fg_color)
            style.configure("TLabelframe.Label", background=frame_bg, foreground=accent_color, font=(title_font, base_size, "bold"))
            
            # Configure notebook tabs with beautiful styling
            style.configure("TNotebook", background=bg_color, tabmargins=[2, 5, 2, 0])
            style.configure("TNotebook.Tab", 
                          background="#C1FFC1",        # Light green tabs
                          foreground="#000000",        # Black text on tabs
                          padding=[15, 5], 
                          font=(button_font, base_size, "bold"))
            
            style.map("TNotebook.Tab", 
                    background=[("selected", tab_selected_bg), ("active", "#A0E8A0")],
                    foreground=[("selected", "#000000"), ("active", "#000000")])  # Always black text when selected
            
            # Beautiful light green buttons with black text
            style.configure("TButton", 
                          background=button_bg,       # Light green background
                          foreground=button_text,     # Bold black text
                          padding=[15, 8], 
                          relief="raised",
                          font=(button_font, base_size, "bold"),
                          borderwidth=1)
            
            style.map("TButton",
                    background=[("active", button_hover), ("pressed", button_pressed)],
                    foreground=[("active", "#000000"), ("pressed", "#000000")],  # Always black text
                    relief=[("pressed", "sunken")])
            
            # Special primary button style
            style.configure("Primary.TButton", 
                          background="#98FB98",        # Slightly more vibrant light green
                          foreground="#000000",        # Black text
                          padding=[15, 8],
                          relief="raised",
                          font=(button_font, 10, "bold"),
                          borderwidth=1)
                          
            style.map("Primary.TButton",
                    background=[("active", "#8EE68E"), ("pressed", "#74C274")],
                    foreground=[("active", "#000000"), ("pressed", "#000000")],  # Always black text
                    relief=[("pressed", "sunken")])

            # Menubar style with green highlights and black text
            style.configure("TMenubutton", 
                          background=frame_bg,
                          foreground=fg_color,
                          relief="raised",
                          font=(body_font, base_size))
                          
            style.map("TMenubutton",
                    background=[("active", "#8EE68E"), ("pressed", "#74C274")],
                    foreground=[("active", "#000000"), ("pressed", "#000000")])  # Black text when active
            
            # Configure entry fields with light backgrounds for contrast
            style.configure("TEntry", 
                          fieldbackground="#ffffff", 
                          foreground="#333333", 
                          padding=5,
                          font=(body_font, base_size))
            
            # Configure checkbuttons with green accents
            style.configure("TCheckbutton", 
                          background=frame_bg, 
                          foreground=fg_color,
                          font=(body_font, base_size))
            
            style.map("TCheckbutton", 
                    background=[("active", frame_bg)],
                    foreground=[("active", "#2E8B57")])  # SeaGreen color on hover
            
            # Configure radio buttons with green accents
            style.configure("TRadiobutton", 
                          background=frame_bg, 
                          foreground=fg_color,
                          font=(body_font, base_size))
            
            style.map("TRadiobutton", 
                    background=[("active", frame_bg)],
                    foreground=[("active", "#2E8B57")])  # SeaGreen color on hover
            
            # Configure comboboxes with green accents
            style.configure("TCombobox", 
                          fieldbackground="#ffffff", 
                          background="#D0F0D0",  # Very light green background
                          foreground="#333333",
                          font=(body_font, base_size))
            
            # Configure progress bars with green accent
            style.configure("Horizontal.TProgressbar", 
                          background="#66CD00",     # Green progress bar
                          troughcolor=bg_color)     # Background color for trough
            
            # Special styles for specific widgets
            style.configure("Title.TLabel", font=(title_font, title_size, "bold"), foreground=accent_color)
            style.configure("Subtitle.TLabel", font=(accent_font, subtitle_size), foreground=accent_color)
            
            # Splash screen styles with green accents
            style.configure("Splash.TFrame", background="#1a2633")  # Dark blue background
            style.configure("SplashTitle.TLabel", background="#1a2633", foreground="#7CFC00", font=(title_font, 24, "bold"))
            style.configure("SplashVersion.TLabel", background="#1a2633", foreground="#aaaaaa", font=(body_font, 10))
            style.configure("SplashStatus.TLabel", background="#1a2633", foreground="#ffffff", font=(body_font, 9))
            style.configure("SplashCopyright.TLabel", background="#1a2633", foreground="#aaaaaa", font=(body_font, 8))
            
            # License status styles
            style.configure("License.TLabel", font=(body_font, 8))
            style.configure("License.Valid.TLabel", font=(body_font, 8), foreground="#00C957")  # Emerald green
            style.configure("License.Expiring.TLabel", font=(body_font, 8), foreground="#ffc107")
            
            # Text widget styling
            text_bg = "#FFFFFF" if theme_name == "light" else "#333333"
            text_fg = "#333333" if theme_name == "light" else "#FFFFFF"
            
            # Apply changes to any text widgets
            for widget in self.root.winfo_children():
                self._recursively_apply_text_style(widget, text_bg, text_fg, body_font)
            
            # Store current theme name
            self.current_theme = theme_name
            
            logging.info(f"Theme {theme_name} applied successfully")
        except Exception as e:
            logging.error(f"Error applying theme: {str(e)}")
    
    def _recursively_apply_text_style(self, widget, bg, fg, font_family):
        """Apply text styling recursively to all text widgets"""
        try:
            if widget.winfo_class() == 'Text':
                widget.configure(background=bg, foreground=fg, font=(font_family, 9))
            elif widget.winfo_class() == 'ScrolledText':
                widget.configure(background=bg, foreground=fg, font=(font_family, 9))
        except:
            pass
            
        # Process children widgets
        try:
            for child in widget.winfo_children():
                self._recursively_apply_text_style(child, bg, fg, font_family)
        except:
            pass
    
    def _apply_font_size(self, size):
        """Apply font size to the application in a thread-safe manner"""
        # Only run on the main thread - schedule if called from another thread
        if threading.current_thread() is not threading.main_thread():
            logging.debug("Scheduling font size application on main thread")
            self.root.after(0, lambda: self._apply_font_size(size))
            return
            
        try:
            logging.info(f"Applying font size: {size}")
            style = ttk.Style()
            
            # Define font sizes
            if size == "small":
                base_size = 8
                title_size = 14
                subtitle_size = 10
            elif size == "large":
                base_size = 11
                title_size = 18
                subtitle_size = 14
            else:  # medium (default)
                base_size = 9
                title_size = 16
                subtitle_size = 12
            
            # Update font sizes in styles
            style.configure("TLabel", font=("Candara Light", base_size))
            style.configure("TButton", font=("Candara Light", base_size, "bold"))
            style.configure("TCheckbutton", font=("Candara Light", base_size))
            style.configure("TRadiobutton", font=("Candara Light", base_size))
            style.configure("TLabelframe.Label", font=("Candara Light", base_size, "bold"))
            style.configure("TNotebook.Tab", font=("Candara Light", base_size, "bold"))
            
            # Update special styles
            style.configure("Title.TLabel", font=("Candara Light", title_size, "bold"))
            style.configure("Subtitle.TLabel", font=("Candara Light", subtitle_size))
            
            # Store the current font size
            self.current_font_size = size
            
            logging.info(f"Font size {size} applied successfully")
        except Exception as e:
            logging.error(f"Error applying font size: {str(e)}")
    
    def _toggle_html_mode(self):
        """Toggle between HTML and plain text mode"""
        if self.html_mode_var.get():
            messagebox.showinfo("HTML Mode", "HTML mode enabled. You can use HTML tags in your email.")
        else:
            messagebox.showinfo("Plain Text Mode", "Plain text mode enabled. HTML tags will be displayed as text.")

    def _on_provider_change(self, event=None):
        """Handle email provider change"""
        provider = self.provider_var.get()
        
        # Update SMTP settings based on provider
        if provider == "Gmail":
            messagebox.showinfo("Gmail Selected", 
                              "Gmail requires an App Password for sending emails.\n"
                              "Please configure your SMTP settings accordingly.")
            
        elif provider == "Outlook":
            messagebox.showinfo("Outlook Selected",
                              "Outlook SMTP settings will be configured automatically.\n"
                              "Make sure to use your full Outlook email and password.")
            
        elif provider == "Yahoo":
            messagebox.showinfo("Yahoo Selected",
                              "Yahoo requires an App Password for sending emails.\n"
                              "Please configure your SMTP settings accordingly.")
        
        # Show SMTP settings dialog with provider preset
        if provider != "Custom":
            self.show_smtp_settings(provider=provider)
            
    def _on_draft_selected(self, event=None):
        """Handle draft selection"""
        if not self.drafts_listbox.curselection():
            return
            
        # Ask user to save current campaign if modified
        if self._check_save_current():
            # User chose to save or discard changes
            index = self.drafts_listbox.curselection()[0]
            draft_name = self.drafts_listbox.get(index)
            self._load_draft(draft_name)
    
    def _check_save_current(self):
        """Check if current campaign needs to be saved"""
        # This would normally check if the campaign has been modified
        # For demo purposes, just ask the user
        if self.campaign_name_var.get():
            result = messagebox.askyesnocancel("Save Changes", 
                                            f"Do you want to save changes to {self.campaign_name_var.get()}?")
            if result is None:
                # Cancel was clicked
                return False
            elif result:
                # Yes was clicked
                self._save_campaign()
                
        return True
        
    def _load_drafts(self):
        """Load saved drafts from file"""
        # Clear listbox
        self.drafts_listbox.delete(0, tk.END)
        
        try:
            # Create drafts directory if it doesn't exist
            drafts_dir = os.path.join(os.path.expanduser("~"), ".email_automation", "drafts")
            if not os.path.exists(drafts_dir):
                os.makedirs(drafts_dir)
                
            # List all draft files
            draft_files = [f for f in os.listdir(drafts_dir) if f.endswith('.json')]
            
            # Add to listbox
            for draft_file in draft_files:
                # Remove .json extension for display
                draft_name = os.path.splitext(draft_file)[0]
                self.drafts_listbox.insert(tk.END, draft_name)
                
        except Exception as e:
            logging.error(f"Error loading drafts: {str(e)}")
            messagebox.showerror("Error", f"Failed to load drafts: {str(e)}")
    
    def _load_selected_draft(self):
        """Load the selected draft"""
        if not self.drafts_listbox.curselection():
            messagebox.showinfo("No Selection", "Please select a draft to load.")
            return
            
        # Get selected draft
        index = self.drafts_listbox.curselection()[0]
        draft_name = self.drafts_listbox.get(index)
        
        # Check if current campaign needs to be saved
        if self._check_save_current():
            self._load_draft(draft_name)
    
    def _load_draft(self, draft_name):
        """Load a draft by name"""
        try:
            # Construct draft file path
            draft_file = os.path.join(os.path.expanduser("~"), ".email_automation", "drafts", f"{draft_name}.json")
            
            if not os.path.exists(draft_file):
                messagebox.showerror("Error", f"Draft file not found: {draft_file}")
                return
                
            # Load draft data
            with open(draft_file, 'r', encoding='utf-8') as f:
                draft_data = json.load(f)
                
            # Update UI with draft data
            self.campaign_name_var.set(draft_data.get('campaign_name', ''))
            self.recipients_var.set(draft_data.get('recipients', ''))
            self.subject_var.set(draft_data.get('subject', ''))
            self.html_mode_var.set(draft_data.get('html_mode', True))
            
            # Update content
            self.email_content_text.delete("1.0", tk.END)
            self.email_content_text.insert("1.0", draft_data.get('content', ''))
            
            # Log action
            self.add_log(f"Loaded draft: {draft_name}")
            
            # Show success message
            messagebox.showinfo("Draft Loaded", f"Successfully loaded draft: {draft_name}")
            
        except Exception as e:
            logging.error(f"Error loading draft: {str(e)}")
            messagebox.showerror("Error", f"Failed to load draft: {str(e)}")
    
    def _delete_selected_draft(self):
        """Delete the selected draft"""
        if not self.drafts_listbox.curselection():
            messagebox.showinfo("No Selection", "Please select a draft to delete.")
            return
            
        # Get selected draft
        index = self.drafts_listbox.curselection()[0]
        draft_name = self.drafts_listbox.get(index)
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete draft: {draft_name}?"):
            return
            
        try:
            # Construct draft file path
            draft_file = os.path.join(os.path.expanduser("~"), ".email_automation", "drafts", f"{draft_name}.json")
            
            if os.path.exists(draft_file):
                os.remove(draft_file)
                
                # Remove from listbox
                self.drafts_listbox.delete(index)
                
                # Log action
                self.add_log(f"Deleted draft: {draft_name}")
                
                # Show success message
                messagebox.showinfo("Draft Deleted", f"Successfully deleted draft: {draft_name}")
            else:
                messagebox.showerror("Error", f"Draft file not found: {draft_file}")
                
        except Exception as e:
            logging.error(f"Error deleting draft: {str(e)}")
            messagebox.showerror("Error", f"Failed to delete draft: {str(e)}")
    
    def _new_campaign(self):
        """Create a new campaign"""
        # Check if current campaign needs to be saved
        if not self._check_save_current():
            return
            
        # Clear form
        self.campaign_name_var.set("")
        self.recipients_var.set("")
        self.subject_var.set("")
        self.html_mode_var.set(True)
        
        # Reset content to template
        self.email_content_text.delete("1.0", tk.END)
        self.email_content_text.insert("1.0", """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #4a6ea9; color: white; padding: 10px; text-align: center; }
        .content { padding: 20px; }
        .footer { font-size: small; color: #666; text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Your Email Title</h1>
    </div>
    <div class="content">
        <p>Hello {name},</p>
        <p>This is a sample email template. You can edit this content to create your own email.</p>
        <p>Use the {placeholders} to personalize your emails.</p>
        <p>Best regards,<br>Your Name</p>
    </div>
    <div class="footer">
        <p> 2025 Your Company. All rights reserved.</p>
        <p>To unsubscribe, click <a href="{unsubscribe_link}">here</a>.</p>
    </div>
</body>
</html>
""")
        
        # Log action
        self.add_log("Created new campaign")
        
        # Focus campaign name field
        self.root.after(100, lambda: self.root.focus_force())
    
    def _save_campaign(self):
        """Save the current campaign as a draft"""
        # Get campaign name
        campaign_name = self.campaign_name_var.get().strip()
        
        if not campaign_name:
            # Ask for campaign name
            campaign_name = simpledialog.askstring("Campaign Name", "Please enter a name for this campaign:")
            
            if not campaign_name:
                messagebox.showwarning("Save Cancelled", "Campaign not saved: No name provided.")
                return
                
            # Update campaign name field
            self.campaign_name_var.set(campaign_name)
        
        try:
            # Create drafts directory if it doesn't exist
            drafts_dir = os.path.join(os.path.expanduser("~"), ".email_automation", "drafts")
            if not os.path.exists(drafts_dir):
                os.makedirs(drafts_dir)
                
            # Create draft data
            draft_data = {
                'campaign_name': campaign_name,
                'recipients': self.recipients_var.get(),
                'subject': self.subject_var.get(),
                'html_mode': self.html_mode_var.get(),
                'content': self.email_content_text.get("1.0", tk.END),
                'saved_date': datetime.datetime.now().isoformat()
            }
            
            # Save to file
            draft_file = os.path.join(drafts_dir, f"{campaign_name}.json")
            with open(draft_file, 'w', encoding='utf-8') as f:
                json.dump(draft_data, f, indent=4)
                
            # Refresh drafts list
            self._load_drafts()
            
            # Log action
            self.add_log(f"Saved draft: {campaign_name}")
            
            # Show success message
            messagebox.showinfo("Draft Saved", f"Successfully saved draft: {campaign_name}")
            
        except Exception as e:
            logging.error(f"Error saving draft: {str(e)}")
            messagebox.showerror("Error", f"Failed to save draft: {str(e)}")
    
    def _start_campaign(self):
        """Start the email campaign"""
        # Check if required fields are filled
        if not self.campaign_name_var.get():
            messagebox.showwarning("Missing Information", "Please enter a campaign name.")
            return
            
        if not self.recipients_var.get():
            messagebox.showwarning("Missing Information", "Please enter recipients or import an email list.")
            return
            
        if not self.subject_var.get():
            messagebox.showwarning("Missing Information", "Please enter an email subject.")
            return
            
        content = self.email_content_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Missing Information", "Please enter email content.")
            return
            
        # Show confirmation dialog
        recipient_count = len(self.recipients_var.get().split(','))
        if not messagebox.askyesno("Confirm Send", 
                                 f"Are you sure you want to send this campaign to {recipient_count} recipients?"):
            return
            
        # Save campaign before sending
        self._save_campaign()
        
        # Here we would normally start the sending process
        messagebox.showinfo("Campaign Started", 
                         f"Campaign '{self.campaign_name_var.get()}' has been started.\n"
                         f"Sending to {recipient_count} recipients.")
        
        # Log action
        self.add_log(f"Started campaign: {self.campaign_name_var.get()} to {recipient_count} recipients")

class SettingsManager:
    """Manages application settings and saves them to MongoDB linked to hardware ID"""
    
    def __init__(self, hardware_id):
        """Initialize with hardware ID"""
        self.hardware_id = hardware_id
        self.client = None
        self.db = None
        self.collection = None
        self.initialized = False
        self.offline_mode = False
        
        # Create local settings directory for fallback
        self.local_settings_dir = os.path.join(os.path.expanduser("~"), ".email_automation")
        if not os.path.exists(self.local_settings_dir):
            try:
                os.makedirs(self.local_settings_dir)
            except Exception as e:
                logging.error(f"Failed to create local settings directory: {str(e)}")
        
        # Connect to MongoDB
        self._connect_to_db()
    
    def _connect_to_db(self):
        """Connect to MongoDB with reduced timeout"""
        try:
            # Use the improved MongoDB connection function
            client, error = get_mongodb_connection()
            
            if client is None:
                logging.warning(f"Failed to connect to MongoDB: {error}")
                self.initialized = False
                self.offline_mode = True
                return False
            
            self.client = client
            self.db = self.client[DATABASE_NAME]
            self.collection = self.db[SETTINGS_COLLECTION]
            
            logging.info("Connected to MongoDB successfully")
            self.initialized = True
            self.offline_mode = False
            return True
                
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {str(e)}")
            self.initialized = False
            self.offline_mode = True
            return False

class LocalSettingsManager:
    """Manages application settings locally in the user directory instead of database"""
    
    def __init__(self, hardware_id):
        """Initialize with hardware ID"""
        self.hardware_id = hardware_id
        self.settings_dir = os.path.join(os.path.expanduser("~"), ".email_automation")
        self.appearance_file = os.path.join(self.settings_dir, f"appearance_{hardware_id}.json")
        self.advanced_file = os.path.join(self.settings_dir, f"advanced_{hardware_id}.json")
        
        # Create settings directory if it doesn't exist
        if not os.path.exists(self.settings_dir):
            os.makedirs(self.settings_dir)
    
    def save_appearance_settings(self, settings):
        """Save appearance settings to local file"""
        try:
            with open(self.appearance_file, 'w') as f:
                json.dump(settings, f, indent=4)
            return True, "Appearance settings saved locally"
        except Exception as e:
            error_msg = f"Failed to save appearance settings locally: {str(e)}"
            logging.error(error_msg)
            return False, error_msg
    
    def load_appearance_settings(self):
        """Load appearance settings from local file"""
        try:
            if os.path.exists(self.appearance_file):
                with open(self.appearance_file, 'r') as f:
                    settings = json.load(f)
                return settings
            return None
        except Exception as e:
            logging.error(f"Failed to load appearance settings locally: {str(e)}")
            return None
    
    def save_advanced_settings(self, settings):
        """Save advanced settings to local file"""
        try:
            with open(self.advanced_file, 'w') as f:
                json.dump(settings, f, indent=4)
            return True, "Advanced settings saved locally"
        except Exception as e:
            error_msg = f"Failed to save advanced settings locally: {str(e)}"
            logging.error(error_msg)
            return False, error_msg
    
    def load_advanced_settings(self):
        """Load advanced settings from local file"""
        try:
            if os.path.exists(self.advanced_file):
                with open(self.advanced_file, 'r') as f:
                    settings = json.load(f)
                return settings
            return None
        except Exception as e:
            logging.error(f"Failed to load advanced settings locally: {str(e)}")
            return None

# Utility functions to get settings
def get_smtp_settings(hardware_id):
    """Get SMTP settings for this hardware ID"""
    settings_manager = SettingsManager(hardware_id)
    return settings_manager.load_smtp_settings()

def get_application_settings(hardware_id):
    """Get application settings for this hardware ID, now using local files for appearance/advanced"""
    try:
        # For appearance and advanced settings, use local files
        local_manager = LocalSettingsManager(hardware_id)
        appearance_settings = local_manager.load_appearance_settings() or {}
        advanced_settings = local_manager.load_advanced_settings() or {}
        
        # Combine settings
        combined_settings = {**appearance_settings, **advanced_settings}
        
        if combined_settings:
            return combined_settings
            
        # Fallback to database if no local settings found
        settings_manager = SettingsManager(hardware_id)
        app_settings = settings_manager.load_application_settings()
        return app_settings
    except Exception as e:
        logging.error(f"Error loading application settings: {str(e)}")
        return None

class SettingsPage(ttk.Frame):
    """Settings page UI component"""
    
    def __init__(self, parent, hardware_id):
        super().__init__(parent)
        self.parent = parent
        self.hardware_id = hardware_id
        
        try:
            self.settings_manager = SettingsManager(hardware_id)
            
            # Create notebook for settings tabs
            self.notebook = ttk.Notebook(self)
            self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create tabs
            self.smtp_tab = self.create_smtp_tab()
            self.appearance_tab = self.create_appearance_tab()
            self.advanced_tab = self.create_advanced_tab()
            
            # Add tabs to notebook
            self.notebook.add(self.smtp_tab, text="Email & SMTP")
            self.notebook.add(self.appearance_tab, text="Appearance")
            self.notebook.add(self.advanced_tab, text="Advanced")
            
            # Load saved settings
            self.load_settings()
        except Exception as e:
            # Handle initialization errors gracefully
            error_label = ttk.Label(
                self, 
                text=f"Error initializing settings: {str(e)}", 
                foreground="red",
                font=("Helvetica", 11, "bold"),
                wraplength=500,
                justify="center"
            )
            error_label.pack(pady=20)
            
            # Add more detailed message about possible causes
            detail_label = ttk.Label(
                self,
                text="This could be due to a connection issue with the database. "
                     "Please check your network connection and try again.",
                wraplength=500,
                justify="center"
            )
            detail_label.pack(pady=10)
            
            logging.error(f"Settings initialization error: {str(e)}")
    
    def create_smtp_tab(self):
        """Create SMTP settings tab"""
        tab = ttk.Frame(self.notebook, padding=20)
        
        # Email Provider Selection
        provider_frame = ttk.LabelFrame(tab, text="Email Provider")
        provider_frame.pack(fill="x", pady=10)
        
        self.provider_var = tk.StringVar()
        self.provider_var.trace_add("write", self.on_provider_change)
        
        ttk.Radiobutton(
            provider_frame, 
            text="Gmail (with App Password)", 
            value="gmail", 
            variable=self.provider_var
        ).pack(anchor="w", padx=10, pady=5)
        
        ttk.Radiobutton(
            provider_frame, 
            text="Outlook/Office 365", 
            value="outlook", 
            variable=self.provider_var
        ).pack(anchor="w", padx=10, pady=5)
        
        ttk.Radiobutton(
            provider_frame, 
            text="Yahoo", 
            value="yahoo", 
            variable=self.provider_var
        ).pack(anchor="w", padx=10, pady=5)
        
        ttk.Radiobutton(
            provider_frame, 
            text="Custom SMTP Server", 
            value="custom", 
            variable=self.provider_var
        ).pack(anchor="w", padx=10, pady=5)
        
        # Gmail Help Link
        self.gmail_help_label = ttk.Label(
            provider_frame, 
            text="Note: Gmail requires an App Password. Click here to learn how to set it up.",
            foreground="blue", 
            cursor="hand2"
        )
        self.gmail_help_label.pack(anchor="w", padx=10, pady=5)
        self.gmail_help_label.bind("<Button-1>", self.open_gmail_help)
        
        # SMTP Details Frame
        smtp_details = ttk.LabelFrame(tab, text="SMTP Server Details")
        smtp_details.pack(fill="x", pady=10)
        
        # Grid layout for form fields
        smtp_details.columnconfigure(1, weight=1)
        
        # Email Address
        ttk.Label(smtp_details, text="Email Address:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(smtp_details, textvariable=self.email_var, width=30).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # Password
        ttk.Label(smtp_details, text="Password:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(smtp_details, textvariable=self.password_var, width=30, show="*")
        self.password_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # Show/Hide Password
        self.show_password_var = tk.BooleanVar()
        self.show_password_var.trace_add("write", self.toggle_password_visibility)
        ttk.Checkbutton(
            smtp_details, 
            text="Show Password", 
            variable=self.show_password_var
        ).grid(row=1, column=2, padx=(0,10), pady=5)
        
        # SMTP Server
        ttk.Label(smtp_details, text="SMTP Server:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.smtp_server_var = tk.StringVar()
        ttk.Entry(smtp_details, textvariable=self.smtp_server_var, width=30).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # SMTP Port
        ttk.Label(smtp_details, text="SMTP Port:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.smtp_port_var = tk.StringVar(value="587")
        ttk.Entry(smtp_details, textvariable=self.smtp_port_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        
        # Use TLS/SSL
        self.use_tls_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            smtp_details, 
            text="Use TLS/SSL", 
            variable=self.use_tls_var
        ).grid(row=4, column=1, sticky="w", padx=10, pady=5)
        
        # Test Connection Button
        test_button = ttk.Button(smtp_details, text="Test Connection", command=self.test_smtp_connection)
        test_button.grid(row=5, column=0, columnspan=2, pady=10)
        
        # Default Recipients CSV
        csv_frame = ttk.LabelFrame(tab, text="Default Recipients List")
        csv_frame.pack(fill="x", pady=10)
        
        csv_frame.columnconfigure(1, weight=1)
        
        ttk.Label(csv_frame, text="CSV File:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.csv_path_var = tk.StringVar()
        ttk.Entry(csv_frame, textvariable=self.csv_path_var, width=30).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        ttk.Button(csv_frame, text="Browse...", command=self.browse_csv).grid(row=0, column=2, padx=10, pady=5)
        
        # Save Button
        save_frame = ttk.Frame(tab)
        save_frame.pack(fill="x", pady=20)
        
        self.status_var = tk.StringVar()
        status_label = ttk.Label(save_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(side="left", padx=10)
        
        save_button = ttk.Button(save_frame, text="Save Settings", command=self.save_smtp_settings)
        save_button.pack(side="right", padx=10)
        
        return tab
    
    def create_appearance_tab(self):
        """Create appearance settings tab"""
        tab = ttk.Frame(self.notebook, padding=20)
        
        # Theme Selection
        theme_frame = ttk.LabelFrame(tab, text="Application Theme")
        theme_frame.pack(fill="x", pady=10)
        
        self.theme_var = tk.StringVar(value="system")
        
        # Update theme immediately when option is selected
        def on_theme_change(*args):
            selected_theme = self.theme_var.get()
            if hasattr(self.parent, 'master') and hasattr(self.parent.master, 'apply_theme'):
                # Apply theme immediately
                self.parent.master.apply_theme(selected_theme)
        
        # Add trace to theme variable
        self.theme_var.trace_add("write", on_theme_change)
        
        # Create theme radio buttons
        ttk.Radiobutton(theme_frame, text="Light Theme", value="light", variable=self.theme_var).pack(anchor="w", padx=10, pady=5)
        ttk.Radiobutton(theme_frame, text="Dark Theme", value="dark", variable=self.theme_var).pack(anchor="w", padx=10, pady=5)
        ttk.Radiobutton(theme_frame, text="Dark Blue Theme", value="darkblue", variable=self.theme_var).pack(anchor="w", padx=10, pady=5)
        ttk.Radiobutton(theme_frame, text="System Default", value="system", variable=self.theme_var).pack(anchor="w", padx=10, pady=5)
        
        # Font Size
        font_frame = ttk.LabelFrame(tab, text="Font Size")
        font_frame.pack(fill="x", pady=10)
        
        self.font_size_var = tk.StringVar(value="medium")
        
        # Update font size immediately when option is selected
        def on_font_size_change(*args):
            selected_size = self.font_size_var.get()
            if hasattr(self.parent, 'master') and hasattr(self.parent.master, '_apply_font_size'):
                # Apply font size immediately
                self.parent.master._apply_font_size(selected_size)
        
        # Add trace to font size variable
        self.font_size_var.trace_add("write", on_font_size_change)
        
        # Create font size radio buttons
        ttk.Radiobutton(font_frame, text="Small", value="small", variable=self.font_size_var).pack(anchor="w", padx=10, pady=5)
        ttk.Radiobutton(font_frame, text="Medium", value="medium", variable=self.font_size_var).pack(anchor="w", padx=10, pady=5)
        ttk.Radiobutton(font_frame, text="Large", value="large", variable=self.font_size_var).pack(anchor="w", padx=10, pady=5)
        
        # Save Button
        save_frame = ttk.Frame(tab)
        save_frame.pack(fill="x", pady=20)
        
        ttk.Label(save_frame, text="Settings will be saved for future sessions").pack(side="left", padx=10)
        
        # Use Primary button style for better visibility
        save_button = ttk.Button(
            save_frame, 
            text="Save Appearance", 
            command=self.save_appearance_settings,
            style="Primary.TButton"
        )
        save_button.pack(side="right", padx=10)
        
        return tab
    
    def create_advanced_tab(self):
        """Create advanced settings tab"""
        tab = ttk.Frame(self.notebook, padding=20)
        
        # Email Settings
        email_frame = ttk.LabelFrame(tab, text="Advanced Email Settings")
        email_frame.pack(fill="x", pady=10)
        
        # Checkbox options
        self.add_signature_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            email_frame, 
            text="Add signature to all emails", 
            variable=self.add_signature_var
        ).pack(anchor="w", padx=10, pady=5)
        
        # Signature Text
        ttk.Label(email_frame, text="Signature:").pack(anchor="w", padx=10, pady=(5,0))
        self.signature_text = tk.Text(email_frame, height=4, width=50)
        self.signature_text.pack(fill="x", padx=10, pady=5)
        
        # Delay between emails
        delay_frame = ttk.Frame(email_frame)
        delay_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(delay_frame, text="Delay between emails (seconds):").pack(side="left")
        self.delay_var = tk.StringVar(value="2")
        ttk.Spinbox(delay_frame, from_=0, to=10, increment=0.5, textvariable=self.delay_var, width=5).pack(side="left", padx=5)
        
        # Logging Settings
        log_frame = ttk.LabelFrame(tab, text="Logging Settings")
        log_frame.pack(fill="x", pady=10)
        
        self.verbose_logging_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            log_frame, 
            text="Enable verbose logging", 
            variable=self.verbose_logging_var
        ).pack(anchor="w", padx=10, pady=5)
        
        # Save Button
        save_frame = ttk.Frame(tab)
        save_frame.pack(fill="x", pady=20)
        
        save_button = ttk.Button(save_frame, text="Save Advanced Settings", command=self.save_advanced_settings)
        save_button.pack(side="right", padx=10)
        
        return tab
    
    def on_provider_change(self, *args):
        """Handle provider change to set default SMTP settings"""
        provider = self.provider_var.get()
        
        if provider == "gmail":
            self.smtp_server_var.set("smtp.gmail.com")
            self.smtp_port_var.set("587")
            self.use_tls_var.set(True)
            self.gmail_help_label.pack(anchor="w", padx=10, pady=5)
        elif provider == "outlook":
            self.smtp_server_var.set("smtp.office365.com")
            self.smtp_port_var.set("587")
            self.use_tls_var.set(True)
            self.gmail_help_label.pack_forget()
        elif provider == "yahoo":
            self.smtp_server_var.set("smtp.mail.yahoo.com")
            self.smtp_port_var.set("587")
            self.use_tls_var.set(True)
            self.gmail_help_label.pack_forget()
        else:  # custom
            self.smtp_server_var.set("")
            self.smtp_port_var.set("")
            self.gmail_help_label.pack_forget()
    
    def toggle_password_visibility(self, *args):
        """Toggle password visibility"""
        if self.show_password_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")
    
    def open_gmail_help(self, event):
        """Open Gmail App Password help page"""
        webbrowser.open("https://support.google.com/accounts/answer/185833")
    
    def browse_csv(self):
        """Browse for a CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select Recipients CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if file_path:
            self.csv_path_var.set(file_path)
    
    def test_smtp_connection(self):
        """Test SMTP connection with current settings"""
        # Get current settings
        email = self.email_var.get()
        password = self.password_var.get()
        server = self.smtp_server_var.get()
        port = self.smtp_port_var.get()
        use_tls = self.use_tls_var.get()
        
        if not all([email, password, server, port]):
            self.status_var.set("Please fill in all SMTP fields")
            return
        
        self.status_var.set("Testing connection...")
        self.update_idletasks()
        
        try:
            # Try to connect
            with smtplib.SMTP(server, int(port)) as smtp:
                if use_tls:
                    smtp.starttls()
                smtp.login(email, password)
                
            self.status_var.set("SMTP connection successful!")
        except Exception as e:
            self.status_var.set(f"Connection failed: {str(e)}")
    
    def save_smtp_settings(self):
        """Save SMTP settings"""
        # Validate input fields
        email = self.email_var.get().strip()
        password = self.password_var.get()
        server = self.smtp_server_var.get().strip()
        port = self.smtp_port_var.get().strip()
        
        if not email:
            self.status_var.set("Email address is required")
            messagebox.showwarning("Missing Information", "Please enter your email address")
            return
            
        if not password:
            self.status_var.set("Password is required")
            messagebox.showwarning("Missing Information", "Please enter your password")
            return
            
        if not server:
            self.status_var.set("SMTP server is required")
            messagebox.showwarning("Missing Information", "Please enter the SMTP server address")
            return
            
        if not port:
            self.status_var.set("SMTP port is required")
            messagebox.showwarning("Missing Information", "Please enter the SMTP port")
            return
            
        try:
            # Validate port is a number
            port = int(port)
        except ValueError:
            self.status_var.set("Port must be a number")
            messagebox.showwarning("Invalid Input", "SMTP port must be a number")
            return
            
        # Prepare settings dictionary
        settings = {
            "setting_type": "smtp",
            "provider": self.provider_var.get(),
            "email": email,
            "password": password,
            "smtp_server": server,
            "smtp_port": port,
            "use_tls": self.use_tls_var.get(),
            "csv_path": self.csv_path_var.get()
        }
        
        # Show saving indicator
        self.status_var.set("Saving settings...")
        self.update_idletasks()
        
        # Save settings
        success, message = self.settings_manager.save_smtp_settings(settings)
        
        if success:
            self.status_var.set("Settings saved successfully")
            messagebox.showinfo("Success", "SMTP settings saved successfully")
            
            # Update the application's email configuration if it exists
            try:
                # This will update the main application's email config if it exists
                if hasattr(self.master, 'master') and hasattr(self.master.master, 'email_config'):
                    self.master.master.email_config = {
                        'email': email,
                        'password': password,
                        'smtp_server': server,
                        'smtp_port': port,
                        'use_tls': self.use_tls_var.get(),
                        'csv_path': self.csv_path_var.get()
                    }
                    logging.info(f"Updated application email configuration for {email}")
            except Exception as e:
                logging.error(f"Error updating application email config: {str(e)}")
        else:
            self.status_var.set(f"Error: {message}")
            messagebox.showerror("Error", f"Failed to save settings: {message}")
    
    def save_appearance_settings(self):
        """Save appearance settings and apply them immediately"""
        try:
            # Get selected theme and font size
            theme = self.theme_var.get()
            font_size = self.font_size_var.get()
            
            # Create settings dictionary
            settings = {
                "theme": theme,
                "font_size": font_size,
                "updated_at": str(datetime.datetime.now())
            }
            
            # Show saving status
            saving_popup = tk.Toplevel(self.parent)
            saving_popup.title("Saving")
            saving_popup.geometry("300x100")
            saving_popup.transient(self.parent)
            saving_popup.grab_set()
            
            ttk.Label(saving_popup, text="Saving appearance settings...").pack(pady=(15, 10))
            progress = ttk.Progressbar(saving_popup, mode="indeterminate")
            progress.pack(fill=tk.X, padx=20)
            progress.start()
            
            # Function to save in background
            def save_in_background():
                # Use local settings manager instead of database
                local_manager = LocalSettingsManager(self.hardware_id)
                success, message = local_manager.save_appearance_settings(settings)
                
                if success:
                    # Apply theme immediately if we have a reference to the main app
                    try:
                        if hasattr(self.parent, 'master') and hasattr(self.parent.master, 'apply_theme'):
                            # Get reference to main application
                            main_app = self.parent.master
                            # Apply the theme
                            main_app.apply_theme(theme)
                            # Apply font size
                            self._apply_font_size(font_size)
                    except Exception as e:
                        logging.error(f"Error applying theme: {str(e)}")
                
                # Update UI in main thread
                self.parent.after(0, lambda: self._finish_save(saving_popup, success, message))
            
            # Start saving in background
            threading.Thread(target=save_in_background, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save appearance settings: {str(e)}")
            
    def _finish_save(self, popup, success, message):
        """Finish the save operation and update UI"""
        popup.destroy()
        
        if success:
            messagebox.showinfo("Success", "Appearance settings saved successfully")
        else:
            messagebox.showerror("Error", f"Failed to save settings: {message}")
    
    def _apply_font_size(self, size):
        """Apply font size to the application"""
        style = ttk.Style()
        
        # Define font sizes
        if size == "small":
            base_size = 8
            title_size = 14
            subtitle_size = 10
        elif size == "large":
            base_size = 11
            title_size = 18
            subtitle_size = 14
        else:  # medium (default)
            base_size = 9
            title_size = 16
            subtitle_size = 12
        
        # Update font sizes in styles
        style.configure("TLabel", font=("Candara Light", base_size))
        style.configure("TButton", font=("Candara Light", base_size, "bold"))
        style.configure("TCheckbutton", font=("Candara Light", base_size))
        style.configure("TRadiobutton", font=("Candara Light", base_size))
        style.configure("TLabelframe.Label", font=("Candara Light", base_size, "bold"))
        style.configure("TNotebook.Tab", font=("Candara Light", base_size, "bold"))
        
        # Update special styles
        style.configure("Title.TLabel", font=("Candara Light", title_size, "bold"))
        style.configure("Subtitle.TLabel", font=("Candara Light", subtitle_size))
        
        # Store the current font size
        if hasattr(self.parent, 'master'):
            self.parent.master.current_font_size = size
    
    def save_advanced_settings(self):
        """Save advanced settings and apply them immediately"""
        try:
            # Get signature settings
            add_signature = self.add_signature_var.get()
            signature_text = self.signature_text.get("1.0", tk.END).strip()
            
            # Get delay setting
            try:
                delay = float(self.delay_var.get())
            except ValueError:
                delay = 2.0  # Default
            
            # Get logging setting
            verbose_logging = self.verbose_logging_var.get()
            
            # Create settings dictionary
            settings = {
                "add_signature": add_signature,
                "signature_text": signature_text,
                "email_delay": delay,
                "verbose_logging": verbose_logging,
                "updated_at": str(datetime.datetime.now())
            }
            
            # Show saving notification
            status_label = ttk.Label(
                self.parent,
                text="Saving settings...",
                foreground="#4a8dde"
            )
            status_label.pack(pady=10)
            self.parent.update_idletasks()
            
            # Save settings to database
            success, message = self.settings_manager.save_application_settings(settings)
            
            # Remove status label
            status_label.destroy()
            
            if success:
                # Apply settings immediately if we have a reference to the main app
                try:
                    if hasattr(self.parent, 'master'):
                        # Get reference to main application
                        main_app = self.parent.master
                        
                        # Apply logging level
                        if verbose_logging:
                            logging.getLogger().setLevel(logging.DEBUG)
                        else:
                            logging.getLogger().setLevel(logging.INFO)
                        
                        # Store email settings
                        main_app.email_settings = {
                            "add_signature": add_signature,
                            "signature_text": signature_text,
                            "email_delay": delay
                        }
                        
                        main_app.add_log("Advanced settings updated and applied")
                except Exception as e:
                    logging.error(f"Error applying advanced settings: {str(e)}")
                
                messagebox.showinfo("Success", "Advanced settings saved and applied successfully")
            else:
                messagebox.showerror("Error", f"Failed to save settings: {message}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save advanced settings: {str(e)}")
    
    def load_settings(self):
        """Load settings from local files"""
        try:
            # Load application settings from local files
            local_manager = LocalSettingsManager(self.hardware_id)
            
            # Load appearance settings
            appearance_settings = local_manager.load_appearance_settings()
            if appearance_settings:
                # Set theme if available
                if 'theme' in appearance_settings:
                    self.theme_var.set(appearance_settings['theme'])
                
                # Set font size if available
                if 'font_size' in appearance_settings:
                    self.font_size_var.set(appearance_settings['font_size'])
            
            # Load advanced settings
            advanced_settings = local_manager.load_advanced_settings()
            if advanced_settings:
                # Set signature settings if available
                if 'add_signature' in advanced_settings:
                    self.add_signature_var.set(advanced_settings.get('add_signature', False))
                
                if 'signature_text' in advanced_settings and advanced_settings['signature_text']:
                    self.signature_text.delete("1.0", tk.END)
                    self.signature_text.insert("1.0", advanced_settings['signature_text'])
                
                # Set delay if available
                if 'email_delay' in advanced_settings:
                    self.delay_var.set(str(advanced_settings['email_delay']))
                
                # Set logging level if available
                if 'verbose_logging' in advanced_settings:
                    self.verbose_logging_var.set(advanced_settings.get('verbose_logging', True))
        except Exception as e:
            logging.error(f"Error loading settings: {str(e)}")
            self.status_var.set(f"Error loading settings: {str(e)}")
            # If we have errors loading, we still want the UI to work with defaults

class EmailSenderThread(threading.Thread):
    """Thread for sending emails in the background"""
    
    def __init__(self, config, recipients, subject, content, is_html, callback=None):
        super().__init__()
        self.config = config
        self.recipients = recipients
        self.subject = subject
        self.content = content
        self.is_html = is_html
        self.callback = callback
        self.lock = Lock()
        self.progress = 0
        self.status = "Initializing"
        self.success_count = 0
        self.error_count = 0
        self.error_messages = []
        
    def run(self):
        try:
            # Connect to SMTP server
            with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                server.starttls()
                server.login(self.config['email'], self.config['password'])
                
                total = len(self.recipients)
                for i, recipient in enumerate(self.recipients, 1):
                    try:
                        # Create message
                        msg = MIMEMultipart()
                        msg['From'] = self.config['email']
                        msg['To'] = recipient
                        msg['Subject'] = self.subject
                        
                        # Attach content
                        content_type = 'html' if self.is_html else 'plain'
                        msg.attach(MIMEText(self.content, content_type))
                        
                        # Send email
                        with self.lock:
                            server.send_message(msg)
                        
                        # Log success
                        logging.info(f"Email sent successfully to {recipient}")
                        self.success_count += 1
                        self.status = f"Sent to {recipient}"
                        
                    except Exception as e:
                        # Log individual email errors but continue with others
                        error_msg = f"Failed to send to {recipient}: {str(e)}"
                        logging.error(error_msg)
                        self.error_count += 1
                        self.error_messages.append(error_msg)
                        self.status = error_msg
                    
                    # Update progress
                    self.progress = int((i / total) * 100)
                    
        except Exception as e:
            error_msg = f"SMTP Error: {str(e)}"
            logging.error(error_msg)
            self.error_messages.append(error_msg)
            self.status = error_msg
        
        # Call callback when complete if provided
        if self.callback:
            self.callback(self.progress, self.success_count, self.error_count, self.error_messages)

def get_mongodb_connection():
    """
    Get a MongoDB connection with improved error handling and connection parameters
    Returns a tuple of (client, error_message) where error_message is None on success
    """
    try:
        # MongoDB connection URL - prefer environment variable, fall back to constant
        connection_url = os.getenv("MONGODB_URL", MONGO_URI)
        
        # Connect to MongoDB with improved timeout settings
        client = pymongo.MongoClient(
            connection_url,
            serverSelectionTimeoutMS=5000,   # 5 seconds timeout for server selection
            connectTimeoutMS=5000,           # 5 seconds timeout for connection
            socketTimeoutMS=5000,            # 5 seconds timeout for socket operations
            retryWrites=True,                # Enable retry for write operations
            w=1                              # Wait for write acknowledgement
        )
        
        # Test the connection
        client.admin.command('ping', serverSelectionTimeoutMS=3000)
        
        # Connection successful
        logging.info("MongoDB connection established successfully")
        return client, None
        
    except pymongo.errors.ServerSelectionTimeoutError:
        error_msg = "MongoDB server selection timeout. Please check your internet connection."
        logging.error(error_msg)
        return None, error_msg
        
    except pymongo.errors.ConnectionFailure:
        error_msg = "MongoDB connection failure. Please check your internet connection."
        logging.error(error_msg)
        return None, error_msg
        
    except pymongo.errors.ConfigurationError:
        error_msg = "MongoDB configuration error. Please check your connection URL."
        logging.error(error_msg)
        return None, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error connecting to MongoDB: {str(e)}"
        logging.error(error_msg)
        return None, error_msg

def main():
    """Main entry point for the application"""
    # Check if hardware ID exists in the database with a valid license
    license_data, message = check_hardware_id_in_database()
    
    if license_data:
        # If hardware ID found in database with active license, show main application
        logger.info(f"Valid license found. {message}")
        show_main_application(license_data)
    else:
        # If no valid license found, show license activation window
        logger.warning(f"License check failed: {message}")
        root = tk.Tk()
        license_window = LicenseActivationWindow(root, error_message=message)
        root.mainloop()

if __name__ == '__main__':
    main()
