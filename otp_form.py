# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from datetime import datetime


def show_otp_verbose_form(otp_code, email, email_password, created_emails_list=None, theme_config=None, current_theme="light"):
    """
    Professional OTP verbose form with email list display
    
    Args:
        otp_code: OTP code from email
        email: Current mail.tm email
        email_password: Password of mail.tm email
        created_emails_list: List of created emails
        theme_config: THEMES dictionary from account_v2.py
        current_theme: Current active theme ("light" or "dark")
    
    Returns:
        (confirmed, email, password, window)
    """
    if created_emails_list is None:
        created_emails_list = []
    
    # Default theme if not provided
    if theme_config is None:
        theme_config = {
            "light": {
                "bg": "#ffffff",
                "fg": "#2c3e50",
                "primary": "#ecf0f1",
                "secondary": "#d5dbdb",
                "accent": "#27ae60",
                "success": "#27ae60",
                "error": "#e74c3c",
                "warning": "#f39c12",
                "info": "#3498db"
            },
            "dark": {
                "bg": "#0a0e27",
                "fg": "#ffffff",
                "primary": "#1a1f3a",
                "secondary": "#2a2f4a",
                "accent": "#00ff88",
                "success": "#00ff88",
                "error": "#ff4444",
                "warning": "#ffaa00",
                "info": "#00aaff"
            }
        }
    
    theme = theme_config.get(current_theme, theme_config["light"])
    form_result = {"confirmed": False, "email": email, "password": email_password}
    
    # Create main window
    form_window = tk.Toplevel()
    form_window.title("🔐 OTP Verification - Vieon Account Creator")
    form_window.geometry("1000x600")
    form_window.configure(bg=theme["bg"])
    
    # Make window stay on top
    try:
        form_window.transient()
        form_window.grab_set()
    except Exception:
        pass  # Fallback if transient fails
    
    # ==================== MAIN CONTAINER ====================
    main_container = tk.Frame(form_window, bg=theme["bg"])
    main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
    
    # ==================== HEADER ====================
    header_frame = tk.Frame(main_container, bg=theme["primary"], relief=tk.RAISED, bd=1)
    header_frame.pack(fill=tk.X, pady=(0, 15))
    
    title = tk.Label(header_frame, text="🔐 OTP VERIFICATION", font=("Segoe UI", 16, "bold"), 
                     bg=theme["primary"], fg=theme["accent"], padx=20, pady=15)
    title.pack(anchor=tk.W)
    
    subtitle = tk.Label(header_frame, text="Verify OTP to complete account creation", 
                        font=("Segoe UI", 10), bg=theme["primary"], fg=theme["info"], padx=20, pady=(0, 10))
    subtitle.pack(anchor=tk.W)
    
    # ==================== CONTENT - TWO COLUMNS ====================
    content_frame = tk.Frame(main_container, bg=theme["bg"])
    content_frame.pack(fill=tk.BOTH, expand=True)
    
    # LEFT COLUMN - OTP & Forms
    left_frame = tk.Frame(content_frame, bg=theme["bg"], width=400)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10), anchor=tk.NW)
    left_frame.pack_propagate(False)
    
    # ---- OTP Display Box ----
    otp_box = tk.Frame(left_frame, bg=theme["primary"], relief=tk.SUNKEN, bd=2)
    otp_box.pack(fill=tk.X, pady=(0, 15))
    
    otp_label = tk.Label(otp_box, text="📬 OTP Code from Email:", font=("Segoe UI", 10, "bold"), 
                         bg=theme["primary"], fg=theme["fg"], padx=15, pady=(10, 5))
    otp_label.pack(anchor=tk.W)
    
    otp_display = tk.Label(otp_box, text=otp_code, font=("Courier New", 24, "bold"), 
                           bg=theme["primary"], fg=theme["accent"], padx=15, pady=15)
    otp_display.pack(anchor=tk.CENTER)
    
    # Copy button
    def copy_otp():
        form_window.clipboard_clear()
        form_window.clipboard_append(otp_code)
        messagebox.showinfo("Success", "OTP copied to clipboard!", parent=form_window)
    
    copy_btn = tk.Button(otp_box, text="📋 Copy OTP", font=("Segoe UI", 9),
                        bg=theme["secondary"], fg=theme["accent"], padx=10, pady=5, relief=tk.FLAT,
                        command=copy_otp, activebackground=theme["primary"], cursor="hand2", highlightthickness=0)
    copy_btn.pack(pady=(0, 10))
    
    # ---- Email Info ----
    email_box = tk.Frame(left_frame, bg=theme["secondary"], relief=tk.FLAT, bd=0)
    email_box.pack(fill=tk.X, pady=(0, 15), padx=10, ipady=10)
    
    tk.Label(email_box, text="📧 Current Email:", font=("Segoe UI", 10, "bold"), 
             bg=theme["secondary"], fg=theme["fg"]).pack(anchor=tk.W, padx=10)
    tk.Label(email_box, text=email, font=("Segoe UI", 10), 
             bg=theme["secondary"], fg=theme["warning"], wraplength=360).pack(anchor=tk.W, padx=10, pady=(5, 0))
    
    # ---- Credentials Form ----
    form_box = tk.LabelFrame(left_frame, text="📝 Account Details", font=("Segoe UI", 11, "bold"),
                             bg=theme["primary"], fg=theme["accent"], padx=15, pady=15, relief=tk.RAISED, bd=1)
    form_box.pack(fill=tk.X, pady=(0, 15))
    
    # Password
    tk.Label(form_box, text="🔑 Password:", font=("Segoe UI", 10), bg=theme["primary"], fg=theme["fg"]).pack(anchor=tk.W, pady=(0, 3))
    password_var = tk.StringVar(value=email_password)
    password_entry = tk.Entry(form_box, textvariable=password_var, font=("Segoe UI", 10),
                              bg=theme["secondary"], fg=theme["fg"], relief=tk.FLAT, bd=1, show="•")
    
    password_frame = tk.Frame(form_box, bg=theme["primary"])
    password_frame.pack(fill=tk.X, pady=(0, 12), ipady=8)
    password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    # Show password toggle
    show_pass_var = tk.BooleanVar()
    def toggle_password():
        password_entry.config(show="" if show_pass_var.get() else "•")
    
    show_btn = tk.Checkbutton(password_frame, text="👁 Show", variable=show_pass_var,
                              command=toggle_password, bg=theme["primary"], fg=theme["accent"],
                              activebackground=theme["primary"], activeforeground=theme["accent"],
                              selectcolor=theme["primary"], relief=tk.FLAT, bd=0, padx=10)
    show_btn.pack(side=tk.LEFT, padx=(5, 0))
    
    # ==================== RIGHT COLUMN - EMAIL LIST & LOGS ====================
    right_frame = tk.Frame(content_frame, bg=theme["bg"])
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
    
    # ---- Tabs for Email List and Logs ----
    notebook = ttk.Notebook(right_frame)
    notebook.pack(fill=tk.BOTH, expand=True)
    
    # Style for tabs
    style = ttk.Style()
    style.configure("TNotebook", background=theme["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=[20, 10])
    
    # TAB 1: Email List
    email_tab = tk.Frame(notebook, bg=theme["primary"])
    notebook.add(email_tab, text="📧 Email List")
    
    if created_emails_list:
        email_list_frame = tk.Frame(email_tab, bg=theme["primary"])
        email_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollable email list
        email_canvas = tk.Canvas(email_list_frame, bg=theme["bg"], highlightthickness=0, height=300)
        email_scrollbar = ttk.Scrollbar(email_list_frame, orient=tk.VERTICAL, command=email_canvas.yview)
        email_scrollable_frame = tk.Frame(email_canvas, bg=theme["bg"])
        
        email_scrollable_frame.bind(
            "<Configure>",
            lambda e: email_canvas.configure(scrollregion=email_canvas.bbox("all"))
        )
        
        email_canvas.create_window((0, 0), window=email_scrollable_frame, anchor="nw")
        email_canvas.configure(yscrollcommand=email_scrollbar.set)
        
        # Add each email to list
        for idx, email_item in enumerate(created_emails_list, 1):
            email_addr = email_item.get('email', 'N/A')
            email_pwd = email_item.get('password', 'N/A')
            
            item_frame = tk.Frame(email_scrollable_frame, bg=theme["secondary"], relief=tk.RAISED, bd=1)
            item_frame.pack(fill=tk.X, pady=5, padx=5)
            
            header_label = tk.Label(item_frame, text=f"#{idx} {email_addr}", font=("Segoe UI", 9, "bold"),
                                   bg=theme["secondary"], fg=theme["accent"], padx=10, pady=(6, 2))
            header_label.pack(anchor=tk.W)
            
            pwd_label = tk.Label(item_frame, text=f"Password: {email_pwd}", font=("Segoe UI", 8),
                                bg=theme["secondary"], fg=theme["fg"], padx=10, pady=(0, 6))
            pwd_label.pack(anchor=tk.W)
        
        email_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        email_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    else:
        no_email_label = tk.Label(email_tab, text="No emails created yet",
                                 font=("Segoe UI", 12), bg=theme["primary"], fg="#666666")
        no_email_label.pack(expand=True)
    
    # TAB 2: Logs
    log_tab = tk.Frame(notebook, bg=theme["primary"])
    notebook.add(log_tab, text="📋 Logs")
    
    # Log text widget
    log_text = scrolledtext.ScrolledText(log_tab, font=("Courier New", 8), bg=theme["bg"], fg=theme["fg"],
                                         relief=tk.FLAT, bd=0, wrap=tk.WORD, padx=10, pady=10)
    log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    log_text.config(state=tk.DISABLED)
    
    # Configure log tags
    log_text.tag_config("SUCCESS", foreground=theme["success"], font=("Courier New", 8, "bold"))
    log_text.tag_config("ERROR", foreground=theme["error"], font=("Courier New", 8, "bold"))
    log_text.tag_config("WARNING", foreground=theme["warning"])
    log_text.tag_config("INFO", foreground=theme["info"])
    
    def log_to_form(msg, level="INFO"):
        """Log message to the form"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {msg}\n"
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, log_entry, level)
        log_text.see(tk.END)
        log_text.config(state=tk.DISABLED)
        form_window.update()
    
    # Initial log
    log_to_form("✓ Form initialized", "SUCCESS")
    log_to_form(f"OTP Code: {otp_code}", "INFO")
    log_to_form(f"Email: {email}", "INFO")
    
    # Store log function in window
    form_window.log_to_form = log_to_form
    
    # ==================== BUTTON SECTION ====================
    button_frame = tk.Frame(main_container, bg=theme["bg"])
    button_frame.pack(fill=tk.X, pady=(15, 0))
    
    def confirm_form():
        pwd = password_var.get().strip()
        
        if not pwd:
            messagebox.showerror("Error", "Password cannot be empty!", parent=form_window)
            return
        
        form_result["confirmed"] = True
        form_result["password"] = pwd
        
        log_to_form("✓ Form confirmed - continuing", "SUCCESS")
        form_window.after(500, form_window.destroy)
    
    def cancel_form():
        form_result["confirmed"] = False
        form_window.destroy()
    
    # Confirm button
    confirm_btn = tk.Button(button_frame, text="✅ CONFIRM & CONTINUE", font=("Segoe UI", 11, "bold"),
                           bg=theme["success"], fg=theme["bg"], padx=30, pady=12, relief=tk.FLAT, bd=0,
                           command=confirm_form, activebackground="#229954" if current_theme == "dark" else "#1e8449",
                           activeforeground=theme["bg"], cursor="hand2", highlightthickness=0)
    confirm_btn.pack(side=tk.LEFT, padx=5)
    
    # Cancel button
    cancel_btn = tk.Button(button_frame, text="❌ CANCEL", font=("Segoe UI", 11, "bold"),
                          bg=theme["error"], fg=theme["bg"], padx=30, pady=12, relief=tk.FLAT, bd=0,
                          command=cancel_form, activebackground="#c0392b" if current_theme == "dark" else "#a93226",
                          activeforeground=theme["bg"], cursor="hand2", highlightthickness=0)
    cancel_btn.pack(side=tk.LEFT, padx=5)
    
    # Bind Enter key
    password_entry.bind("<Return>", lambda e: confirm_form())
    
    # Focus on password entry
    password_entry.focus()
    password_entry.select_range(0, tk.END)
    
    # Wait for form
    form_window.wait_window()
    
    return form_result["confirmed"], form_result["email"], form_result["password"], form_window
    
    # Make window stay on top
    try:
        form_window.transient()
        form_window.grab_set()
    except Exception:
        pass  # Fallback if transient fails
    
    # ==================== MAIN CONTAINER ====================
    main_container = tk.Frame(form_window, bg=theme["bg"])
    main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

