import requests
import json
import tkinter as tk
from tkinter import scrolledtext
import threading
import re
import time

# Base URL for your LM Studio instance (replace with actual address)
BASE_URL = "http://localhost:1234"  # Example - check LM Studio's documentation

# Dark theme colors
BG_COLOR = "#1e1e1e"
FG_COLOR = "#ffffff"
BUTTON_COLOR = "#6000BF"
BUTTON_FG = "#ffffff"
TEXT_BG = "#2d2d2d"
TEXT_FG = "#ffffff"
CODE_BG = "#1a1a1a"
CODE_FG = "#0088ff"
HEADING_FG = "#00ffaa"

# API Key
API_KEY = "sk-lm-J6JKbAiq:eq3B92fGGwdIneldysVH"

# Store raw content for toggling
response_content = {"left": "", "right": ""}
show_formatted = {"left": True, "right": True}
loaded_models = {"left": None, "right": None}
selected_models = {"left": 2, "right": 1}  # Track selections separately (left: gpt-oss, right: deepseek)
model_instances = {"left": None, "right": None}  # Track model instance IDs

available_models = [
    "google/gemma-3-12b",
    "deepseek/deepseek-r1-0528-qwen3-8b",
    "openai/gpt-oss-20b"
]

def get_loaded_models():
    """Get list of currently loaded models."""
    endpoint = f"{BASE_URL}/api/v1/models"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except requests.exceptions.RequestException as e:
        print(f"Error getting loaded models: {e}")
        return []

def load_model(model_name):
    """Load a model in LM Studio."""
    endpoint = f"{BASE_URL}/api/v1/models/load"
    
    # Check for and unload any duplicate instances first
    current_models = get_loaded_models()
    for model in current_models:
        model_id = model.get("id") or model.get("model")
        if model_id and model_id.startswith(model_name + ":"):
            # Found a duplicate, unload it
            print(f"Unloading duplicate instance: {model_id}")
            unload_model(model_name, specific_instance=model_id)
    
    data = {
        "model": model_name,
        "flash_attention": True
    }
    
    try:
        response = requests.post(endpoint, json=data)
        response.raise_for_status()
        result = response.json()
        print(f"Model {model_name} loaded successfully")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error loading model {model_name}: {e}")
        return None

def unload_model(model_name, specific_instance=None):
    """Unload a model in LM Studio.
    
    Args:
        model_name (str): The name of the model to unload.
        specific_instance (str, optional): The specific instance ID (e.g., 'model:2') to unload.
                                          If None, unloads the base model.
    """
    endpoint = f"{BASE_URL}/api/v1/models/unload"
    
    # Use specific instance if provided, otherwise use base model name
    unload_target = specific_instance if specific_instance else model_name
    
    data = {
        "model": unload_target
    }
    
    try:
        response = requests.post(endpoint, json=data)
        response.raise_for_status()
        print(f"Model {unload_target} unloaded successfully")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error unloading model {unload_target}: {e}")
        return False

def remove_duplicate_instances(model_name, keep=1):
    """Unload duplicate loaded instances of a model, keeping only `keep` instances.

    This scans currently loaded models for instance ids that start with
    "{model_name}:" and unloads extras.
    """
    current_models = get_loaded_models()
    instances = []
    for m in current_models:
        model_id = m.get("id") or m.get("model")
        if model_id and model_id.startswith(model_name + ":"):
            instances.append(model_id)

    # If there are more instances than desired, unload the extras
    if len(instances) > keep:
        # Keep the first `keep` instances and unload the rest
        to_unload = instances[keep:]
        for inst in to_unload:
            print(f"Found duplicate instance for {model_name}: {inst} - unloading")
            unload_model(model_name, specific_instance=inst)

def ensure_model_loaded(model_name, side):
    """Ensure the specified model is loaded."""
    current_models = get_loaded_models()
    current_model_ids = [m.get("id") or m.get("model") for m in current_models]
    
    # Check if the model is already loaded
    if model_name in current_model_ids:
        # Model is already loaded, just update our tracking
        loaded_models[side] = model_name
        model_instances[side] = model_name
    else:
        # Model not loaded at all, load it
        load_result = load_model(model_name)
        if load_result:
            loaded_models[side] = model_name
            # Extract model instance ID from response
            model_instances[side] = load_result.get("id") or load_result.get("model_id") or model_name
        else:
            loaded_models[side] = model_name
            model_instances[side] = model_name

def generate_text(model_name, prompt):
    """
    Generates text using a specified LLM model in LM Studio.

    Args:
        model_name (str): The name of the model to use (e.g., "Llama-2-7b-Chat").
        prompt (str): The input prompt for the model.

    Returns:
        tuple: (generated_text, model_instance_id) or (None, None) if an error occurred.
    """

    endpoint = f"{BASE_URL}/api/v1/chat"  # Assumed endpoint - check LM Studio docs

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
        # Add any authentication headers here if required by LM Studio
    }

    data = {
        "model": model_name,
        "input": prompt,
        "temperature": 0.7, # Adjust for creativity vs. determinism
        # Add other parameters supported by LM Studio's API (e.g., top_p, frequency_penalty)
    }

    response = requests.post(endpoint, headers=headers, data=json.dumps(data))
    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

    response_json = response.json()
    # Extract the message content from the 'output' array
    message_content = None
    model_id = response_json.get("model_id") or response_json.get("id") or model_name

    try:
        for output in response_json["output"]:
            if output["type"] == "message":
                message_content = output["content"]
                break  # Stop after finding the first "message" type
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Error parsing response: {e}. Check LM Studio's API response format.")

    # Extract stats if present
    stats = response_json.get("stats") or response_json.get("metrics") or None

    return message_content, model_id, stats

def format_markdown(text_widget, content):
    """Format and display markdown content in the text widget."""
    text_widget.config(state=tk.NORMAL)
    text_widget.delete(1.0, tk.END)
    
    # Configure tags for markdown styling
    text_widget.tag_config("heading1", font=("Arial", 16, "bold"), foreground=HEADING_FG)
    text_widget.tag_config("heading2", font=("Arial", 14, "bold"), foreground=HEADING_FG)
    text_widget.tag_config("heading3", font=("Arial", 12, "bold"), foreground=HEADING_FG)
    text_widget.tag_config("bold", font=("Arial", 10, "bold"), foreground=TEXT_FG)
    text_widget.tag_config("italic", font=("Arial", 10, "italic"), foreground=TEXT_FG)
    text_widget.tag_config("bolditalic", font=("Arial", 10, "bold italic"), foreground=TEXT_FG)
    text_widget.tag_config("code", font=("Courier", 10), background=CODE_BG, foreground=CODE_FG)
    text_widget.tag_config("codeblock", font=("Courier", 10), background=CODE_BG, foreground=CODE_FG)
    text_widget.tag_config("separator", foreground="#666666")
    
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Separator
        if line.strip().startswith("---"):
            text_widget.insert(tk.END, "─" * 50 + "\n", "separator")
            i += 1
        # Headings
        elif line.startswith("# "):
            text_widget.insert(tk.END, line[2:] + "\n", "heading1")
            i += 1
        elif line.startswith("## "):
            text_widget.insert(tk.END, line[3:] + "\n", "heading2")
            i += 1
        elif line.startswith("### "):
            text_widget.insert(tk.END, line[4:] + "\n", "heading3")
            i += 1
        # Bullet points - check if line starts with optional whitespace then -
        elif re.match(r'^\s*-\s+', line):
            bullet_text = re.sub(r'^\s*-\s+', '', line)
            text_widget.insert(tk.END, "  • " + bullet_text + "\n")
            i += 1
        # Code blocks
        elif line.strip().startswith("```"):
            text_widget.insert(tk.END, "\n")
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                text_widget.insert(tk.END, lines[i] + "\n", "codeblock")
                i += 1
            if i < len(lines):
                i += 1  # Skip closing ```
            text_widget.insert(tk.END, "\n")
        # Regular lines with inline formatting
        else:
            j = 0
            while j < len(line):
                # Bold italic (***text***)
                bolditalic_match = re.match(r'\*\*\*(.+?)\*\*\*', line[j:])
                if bolditalic_match:
                    text_widget.insert(tk.END, bolditalic_match.group(1), "bolditalic")
                    j += len(bolditalic_match.group(0))
                # Bold - match **text**
                elif re.match(r'\*\*(.+?)\*\*', line[j:]):
                    bold_match = re.match(r'\*\*(.+?)\*\*', line[j:])
                    text_widget.insert(tk.END, bold_match.group(1), "bold")
                    j += len(bold_match.group(0))
                # Inline code - match `text`
                elif line[j] == '`':
                    code_match = re.match(r'`(.+?)`', line[j:])
                    if code_match:
                        text_widget.insert(tk.END, code_match.group(1), "code")
                        j += len(code_match.group(0))
                    else:
                        text_widget.insert(tk.END, line[j])
                        j += 1
                # Italic - match *text* (but not ** which is bold)
                elif line[j] == '*' and j + 1 < len(line) and line[j + 1] != '*':
                    italic_match = re.match(r'\*(.+?)\*', line[j:])
                    if italic_match and '**' not in italic_match.group(0):
                        text_widget.insert(tk.END, italic_match.group(1), "italic")
                        j += len(italic_match.group(0))
                    else:
                        text_widget.insert(tk.END, line[j])
                        j += 1
                else:
                    text_widget.insert(tk.END, line[j])
                    j += 1
            text_widget.insert(tk.END, "\n")
            i += 1
    
    text_widget.config(state=tk.DISABLED)


def _set_widget_message(text_widget, message, side=None, error=False):
    """Helper to set message into a widget and optionally format it.

    If `side` is provided and `error` is False, the message is stored in
    `response_content` and formatted for display. For errors, it simply
    inserts the message.
    """
    text_widget.config(state=tk.NORMAL)
    text_widget.delete(1.0, tk.END)
    text_widget.insert(tk.END, message)
    text_widget.config(state=tk.DISABLED)

    if side and not error:
        response_content[side] = message
        show_formatted[side] = True
        button = button_left if side == "left" else button_right
        button.config(text="Show Raw")
        format_markdown(text_widget, message)

def toggle_view(side):
    """Toggle between formatted and raw markdown view."""
    show_formatted[side] = not show_formatted[side]
    text_widget = text_left if side == "left" else text_right
    button = button_left if side == "left" else button_right
    
    button.config(text="Show Raw" if show_formatted[side] else "Show Formatted")
    
    if show_formatted[side]:
        format_markdown(text_widget, response_content[side])
    else:
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        text_widget.insert(tk.END, response_content[side])
        text_widget.config(state=tk.DISABLED)

def generate_for_model(model_name, prompt_text, text_widget, side, expected_model_id):
    """Generate text for a single model and update the UI."""
    # Send the prompt immediately (fast path) and only pivot to loading/unloading on error
    try:
        generated_text, model_id, stats = generate_text(model_name, prompt_text)
    except (requests.exceptions.RequestException, ValueError) as first_err:
        # First attempt failed; pivot to ensure model is loaded and remove duplicates, then retry
        print(f"Initial request failed for {model_name}: {first_err}. Pivoting to load/unload flow.")

        # Start duplicate watcher while we attempt recovery and retry
        stop_event = threading.Event()
        def _duplicate_watcher():
            while not stop_event.is_set():
                try:
                    remove_duplicate_instances(model_name, keep=1)
                except Exception:
                    pass
                time.sleep(0.5)

        watcher = threading.Thread(target=_duplicate_watcher, daemon=True)
        watcher.start()

        try:
            # Ensure model is loaded (this will attempt to load if missing)
            ensure_model_loaded(model_name, side)

            # Try one more time after recovery steps
            try:
                generated_text, model_id, stats = generate_text(model_name, prompt_text)
            except Exception as retry_err:
                stop_event.set()
                watcher.join(timeout=1.0)
                _set_widget_message(text_widget, f"Error after recovery attempt: {retry_err}", side=side, error=True)
                return

            # Stop watcher on success
            stop_event.set()
            watcher.join(timeout=1.0)

        except Exception as e:
            stop_event.set()
            watcher.join(timeout=1.0)
            print(f"Recovery failed for {model_name}: {e}")
            _set_widget_message(text_widget, f"Error during recovery: {e}", side=side, error=True)
            return

    # At this point we have generated_text/model_id (or generated_text may be None)
    # Verify the response came from the correct model
    if model_id != expected_model_id:
        msg = f"Error: Response mismatch. Expected {expected_model_id}, got {model_id}"
        print(f"Warning: Response for {side} came from {model_id}, expected {expected_model_id}")
        _set_widget_message(text_widget, msg, side=side, error=True)
        return

    if generated_text:
        # Append stats if available
        try:
            if stats:
                stats_block = "\n\n**Stats**:\n```json\n" + json.dumps(stats, indent=2) + "\n```\n"
                display_text = (generated_text or "") + stats_block
            else:
                display_text = generated_text
        except Exception:
            display_text = generated_text

        _set_widget_message(text_widget, display_text, side=side, error=False)
    else:
        _set_widget_message(text_widget, f"Error: No response from {model_name}", side=side, error=True)

def on_dropdown_left_change(value):
    """Handle left dropdown selection."""
    selected_models["left"] = available_models.index(dropdown_left_var.get())

def on_dropdown_right_change(value):
    """Handle right dropdown selection."""
    selected_models["right"] = available_models.index(dropdown_right_var.get())

def main(event=None):
    model1_name = available_models[selected_models["left"]]
    model2_name = available_models[selected_models["right"]]
    
    prompt_text = prompt_entry.get(1.0, tk.END).strip()
    if not prompt_text:
        print("Please enter a prompt")
        return
    
    # Clear previous outputs
    text_left.config(state=tk.NORMAL)
    text_right.config(state=tk.NORMAL)
    text_left.delete(1.0, tk.END)
    text_right.delete(1.0, tk.END)
    text_left.insert(tk.END, "Generating...\n")
    text_right.insert(tk.END, "Generating...\n")
    text_left.config(state=tk.DISABLED)
    text_right.config(state=tk.DISABLED)
    
    # Clear input field
    prompt_entry.delete(1.0, tk.END)
    
    # Do not pre-check or load models here — workers will send the prompt
    # immediately and only pivot to loading/unloading on errors.
    model1_id = model_instances["left"] or model1_name
    model2_id = model_instances["right"] or model2_name
    
    # Create threads for both LLMs to run simultaneously
    thread1 = threading.Thread(target=generate_for_model, args=(model1_name, prompt_text, text_left, "left", model1_id))
    thread2 = threading.Thread(target=generate_for_model, args=(model2_name, prompt_text, text_right, "right", model2_id))
    
    thread1.start()
    thread2.start()

root = tk.Tk()
root.title("Dual LLM Text Generation")
root.minsize(600, 600)
root.maxsize(1980, 1080)
root.geometry("1000x700+50+50")
root.config(bg=BG_COLOR)

# Input section
input_frame = tk.Frame(root, bg=BG_COLOR)
input_frame.pack(fill=tk.BOTH, padx=10, pady=10)

tk.Label(input_frame, text="Enter your prompt: ", bg=BG_COLOR, fg=FG_COLOR).pack(anchor=tk.NW)
prompt_entry = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, bg=TEXT_BG, fg=TEXT_FG, insertbackground=FG_COLOR, height=6, relief=tk.FLAT, bd=8)
prompt_entry.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
prompt_entry.bind("<Control-Return>", main)

generate_button = tk.Button(input_frame, text="Generate Text", command=main, bg=BUTTON_COLOR, fg=BUTTON_FG, activebackground="#1565c0", relief=tk.FLAT, bd=0, padx=16, pady=8)
generate_button.pack()

# Model selection and output section
content_frame = tk.Frame(root, bg=BG_COLOR)
content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Configure equal weights for left and right frames
content_frame.grid_columnconfigure(0, weight=1)
content_frame.grid_columnconfigure(1, weight=1)
content_frame.grid_rowconfigure(0, weight=1)

# Left side
left_frame = tk.Frame(content_frame, bg=BG_COLOR)
left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

tk.Label(left_frame, text="Select Model (Left):", bg=BG_COLOR, fg=FG_COLOR).pack(anchor=tk.NW)
dropdown_left_var = tk.StringVar(value=available_models[2])
dropdown_left = tk.OptionMenu(left_frame, dropdown_left_var, *available_models, command=on_dropdown_left_change)
dropdown_left.config(bg=BUTTON_COLOR, fg=BUTTON_FG, activebackground="#1565c0", activeforeground=BUTTON_FG, relief=tk.FLAT, bd=0, highlightthickness=0, padx=8, pady=6)
dropdown_left.pack(fill=tk.X, pady=(0, 10))
selected_models["left"] = 2

left_output_frame = tk.Frame(left_frame, bg=BG_COLOR)
left_output_frame.pack(fill=tk.BOTH, expand=True)

left_header = tk.Frame(left_output_frame, bg=BG_COLOR)
left_header.pack(fill=tk.X, pady=(0, 5))
tk.Label(left_header, text="Output", font=("Arial", 10, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(side=tk.LEFT)
button_left = tk.Button(left_header, text="Show Raw", command=lambda: toggle_view("left"), bg=BUTTON_COLOR, fg=BUTTON_FG, activebackground="#1565c0", font=("Arial", 9), relief=tk.FLAT, bd=0, padx=12, pady=4)
button_left.pack(side=tk.RIGHT)

text_left = scrolledtext.ScrolledText(left_output_frame, wrap=tk.WORD, state=tk.DISABLED, bg=TEXT_BG, fg=TEXT_FG, insertbackground=FG_COLOR, relief=tk.FLAT, bd=8)
text_left.pack(fill=tk.BOTH, expand=True)

# Right side
right_frame = tk.Frame(content_frame, bg=BG_COLOR)
right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

tk.Label(right_frame, text="Select Model (Right):", bg=BG_COLOR, fg=FG_COLOR).pack(anchor=tk.NW)
dropdown_right_var = tk.StringVar(value=available_models[1])
dropdown_right = tk.OptionMenu(right_frame, dropdown_right_var, *available_models, command=on_dropdown_right_change)
dropdown_right.config(bg=BUTTON_COLOR, fg=BUTTON_FG, activebackground="#1565c0", activeforeground=BUTTON_FG, relief=tk.FLAT, bd=0, highlightthickness=0, padx=8, pady=6)
dropdown_right.pack(fill=tk.X, pady=(0, 10))
selected_models["right"] = 1

right_output_frame = tk.Frame(right_frame, bg=BG_COLOR)
right_output_frame.pack(fill=tk.BOTH, expand=True)

right_header = tk.Frame(right_output_frame, bg=BG_COLOR)
right_header.pack(fill=tk.X, pady=(0, 5))
tk.Label(right_header, text="Output", font=("Arial", 10, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(side=tk.LEFT)
button_right = tk.Button(right_header, text="Show Raw", command=lambda: toggle_view("right"), bg=BUTTON_COLOR, fg=BUTTON_FG, activebackground="#1565c0", font=("Arial", 9), relief=tk.FLAT, bd=0, padx=12, pady=4)
button_right.pack(side=tk.RIGHT)

text_right = scrolledtext.ScrolledText(right_output_frame, wrap=tk.WORD, state=tk.DISABLED, bg=TEXT_BG, fg=TEXT_FG, insertbackground=FG_COLOR, relief=tk.FLAT, bd=8)
text_right.pack(fill=tk.BOTH, expand=True)

root.mainloop()
