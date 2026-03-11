import json
import os
import tkinter as tk
from json import JSONDecoder, JSONEncoder
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, Type

from pynput.keyboard import Key as SpecialKey
from pynput.keyboard import KeyCode, Listener

from wintoucher.controller.dots import Dots
from wintoucher.data.dot import FlickDot, PinchDot, PressDot, RotateDot
from wintoucher.gui.dot import FlickDotView, PinchDotView, RotateDotView
from wintoucher.gui.overlay import Overlay
from wintoucher.gui.tkutils import (
    WITHDRAWN,
    create_button,
    create_details,
    create_frame,
    grid_widget,
    toggle_state,
)
from wintoucher.gui.tray import TrayIcon
from wintoucher.util.json import JSONSerializableManager
from wintoucher.util.key import Key, is_special_key, is_valid_key, key_to_str
from wintoucher.util.touch import MAX_TOUCHES, TouchError, TouchManager, get_cursor_pos


class WintoucherApp:
    """
    Main class for the WinToucher application.

    Also responsible for the main GUI of the control panel.
    """

    overlay: "Overlay"
    dots: Dots
    tray_icon: TrayIcon
    touch_manager: TouchManager
    touch_task: str
    touch_update: bool
    keyboard: Listener
    keyboard_listening: bool
    json_encoder: Type[JSONEncoder]
    json_decoder: Type[JSONDecoder]

    APP_WIDTH = 520
    APP_HEIGHT = 650
    APP_NAME = "WinToucher"
    APP_VERSION = "v0.1.0"
    APP_ICO_NAME = "WinToucher.ico"

    def __init__(self, dots: Dots):
        APP_NAME_WITH_VERSION = f"{self.APP_NAME} {self.APP_VERSION}"

        self.root = tk.Tk()
        self.root.title(f"Control Panel - {APP_NAME_WITH_VERSION}")

        self.root.geometry(f"{self.APP_WIDTH}x{self.APP_HEIGHT}")
        self.root.minsize(self.APP_WIDTH, self.APP_HEIGHT)
        self.root.iconbitmap(self.APP_ICO_NAME)
        self.root.attributes("-topmost", True)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.bind("<Map>", self.unminimize)
        self.root.bind("<Unmap>", self.minimize)

        self.dots = dots
        self.overlay = Overlay(
            master=self.root,
            app_name=APP_NAME_WITH_VERSION,
            app_icon=self.APP_ICO_NAME,
            dots=self.dots,
            update_dot_detail=self.update_dot_detail,
        )
        self.keyboard = Listener(**self.keyboard_handlers())
        self.keyboard.start()
        self.keyboard_listening = False

        # JSON Serialization
        json_manager = JSONSerializableManager()
        json_manager.register(Dots)
        json_manager.register(PressDot)
        json_manager.register(FlickDot)
        json_manager.register(PinchDot)
        json_manager.register(RotateDot)
        json_manager.register_special(SpecialKey, ("name",))
        json_manager.add_decoder(SpecialKey, lambda obj: SpecialKey[obj["name"]])
        json_manager.register_special(KeyCode, ("vk", "char", "is_dead"))
        json_manager.add_decoder(
            KeyCode, lambda x: KeyCode(vk=x["vk"], char=x["char"], is_dead=x["is_dead"])
        )
        json_manager.register_special(tk.IntVar, ("IntVar",))
        json_manager.register_special(tk.StringVar, ("StringVar",))

        def tk_var_encoder(var: tk.Variable):
            return {var.__class__.__name__: var.get()}

        def tk_var_decoder_factory(var_type: Type[tk.Variable]):
            def tk_var_decoder(obj: Dict[str, Any]):
                return var_type(value=obj[var_type.__name__])

            return tk_var_decoder

        json_manager.add_encoder(tk.IntVar, tk_var_encoder)
        json_manager.add_encoder(tk.StringVar, tk_var_encoder)
        json_manager.add_decoder(tk.IntVar, tk_var_decoder_factory(tk.IntVar))
        json_manager.add_decoder(tk.StringVar, tk_var_decoder_factory(tk.StringVar))

        def dots_decoder(obj: Dict[str, Any]):
            dots = Dots()
            dots.dots = obj["dots"]
            for dot in dots:
                dots.add_view(dot)
            return dots

        json_manager.add_decoder(Dots, dots_decoder)

        self.json_encoder = json_manager.build_encoder()
        self.json_decoder = json_manager.build_decoder()

        # Control Frame
        self.control_frame = create_frame(self.root, "Global Control")
        grid_widget(self.control_frame, 0, 0, padx=10, pady=5)

        self.overlay_button = create_button(
            self.control_frame, "Toggle Overlay", self.toggle_overlay
        )
        grid_widget(self.overlay_button, 0, 0)

        self.listen_button = create_button(self.control_frame, "", self.toggle_listen)
        grid_widget(self.listen_button, 0, 1)
        self.toggle_listen(False)

        self.save_button = create_button(
            self.control_frame, "Save Dots", self.save_dots
        )
        grid_widget(self.save_button, 1, 0)

        self.load_button = create_button(
            self.control_frame, "Load Dots", self.load_dots
        )
        grid_widget(self.load_button, 1, 1)

        # Bindings Frame
        self.bindings_frame = create_frame(self.root, "Bindings", cols=4)
        grid_widget(self.bindings_frame, 1, 0, sticky="nsew", padx=10, pady=5)
        self.root.grid_rowconfigure(1, weight=1)

        columns = ("id", "type", "mode", "key", "params")
        self.bindings_tree = ttk.Treeview(
            self.bindings_frame, columns=columns, show="headings",
            height=6, selectmode="browse",
        )
        self.bindings_tree.heading("id", text="#")
        self.bindings_tree.heading("type", text="Type")
        self.bindings_tree.heading("mode", text="Mode")
        self.bindings_tree.heading("key", text="Key")
        self.bindings_tree.heading("params", text="Parameters")
        self.bindings_tree.column("id", width=30, stretch=False)
        self.bindings_tree.column("type", width=55, stretch=False)
        self.bindings_tree.column("mode", width=55, stretch=False)
        self.bindings_tree.column("key", width=55, stretch=False)
        self.bindings_tree.column("params", width=200)
        self.bindings_tree.grid(
            row=0, column=0, columnspan=4, sticky="nsew", padx=5, pady=2,
        )
        self.bindings_frame.grid_rowconfigure(0, weight=1)
        self.bindings_tree.bind("<<TreeviewSelect>>", self._on_binding_select)

        tree_scroll = ttk.Scrollbar(
            self.bindings_frame, orient=tk.VERTICAL,
            command=self.bindings_tree.yview,
        )
        self.bindings_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=0, column=4, sticky="ns")

        ttk.Label(self.bindings_frame, text="Type:").grid(row=1, column=0, padx=2)
        self.new_dot_type_combobox = ttk.Combobox(
            self.bindings_frame,
            textvariable=self.overlay.new_dot_type,
            values=list(Dots.TYPES.keys()),
            state="readonly",
            width=7,
        )
        self.new_dot_type_combobox.current(0)
        self.new_dot_type_combobox.grid(row=1, column=1, padx=2)

        self.new_dot_mode = tk.StringVar(value="overlay")
        ttk.Label(self.bindings_frame, text="Mode:").grid(row=1, column=2, padx=2)
        self.new_dot_mode_combobox = ttk.Combobox(
            self.bindings_frame,
            textvariable=self.new_dot_mode,
            values=["overlay", "cursor"],
            state="readonly",
            width=7,
        )
        self.new_dot_mode_combobox.current(0)
        self.new_dot_mode_combobox.grid(row=1, column=3, padx=2)

        self.add_binding_btn = create_button(
            self.bindings_frame, "Add Binding", self._add_binding,
        )
        self.add_binding_btn.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=2,
        )
        self.delete_binding_btn = create_button(
            self.bindings_frame, "Delete Binding", self._delete_binding,
        )
        self.delete_binding_btn.grid(
            row=2, column=2, columnspan=2, sticky="ew", padx=5, pady=2,
        )

        # Dot Frame
        self.dot_frame = create_frame(self.root, "Binding Detail")
        grid_widget(self.dot_frame, 2, 0, sticky="nsew", padx=10, pady=5)
        self.root.grid_rowconfigure(2, weight=1)

        # Key assignment state
        self._assigning_key = False
        self._key_target_dot = None

        # Touch
        self.touch_manager = TouchManager(MAX_TOUCHES)
        self.touch_task = ""
        self.touch()

        # Tray Icon
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.tray_icon = TrayIcon(APP_NAME_WITH_VERSION, self.APP_ICO_NAME)
        self.tray_icon.menu_builder.add_item(
            "Show Control Panel",
            lambda icon, item: self.show_from_tray(),
            default=True,
        )
        self.tray_icon.menu_builder.add_item(
            "Keyboard Listening",
            action=lambda icon, item: self.toggle_listen(),
            checked=lambda item: self.keyboard_listening,  # type: ignore
        )
        self.tray_icon.menu_builder.add_item("Exit", lambda icon, item: self.exit())
        self.tray_icon.create_icon()

    def exit(self):
        self.keyboard.stop()
        self.root.after_cancel(self.touch_task)
        self.tray_icon.stop()
        self.overlay.destroy()
        self.root.destroy()

    def hide_to_tray(self):
        self.tray_icon.notify("WinToucher has been hidden to tray.")
        self.overlay.withdraw()
        self.root.withdraw()

    def minimize(self, event: tk.Event):
        self.overlay.withdraw()

    def unminimize(self, event: tk.Event):
        if self.overlay.showing:
            self.overlay.deiconify()

    def show_from_tray(self):
        self.root.deiconify()
        if self.overlay.showing:
            self.overlay.deiconify()

    def save_dots(self):
        if len(self.dots) == 0:
            messagebox.showinfo(
                "Save Dots",
                "No dots to save.",
            )
            return
        path = filedialog.asksaveasfilename(
            title="Save Dots",
            filetypes=(("JSON files", "*.json"),),
            defaultextension="json",
            initialdir=os.getcwd(),
        )
        if path:
            json.dump(
                self.dots,
                open(path, "w", encoding="utf-8"),
                ensure_ascii=False,
                indent=4,
                cls=self.json_encoder,
            )

    def load_dots(self):
        if len(self.dots) > 0:
            if not messagebox.askyesno(
                "Load Dots",
                "Loading dots will overwrite the current dots.\n\nDo you want to continue?",
            ):
                return
        path = filedialog.askopenfilename(
            title="Load Dots",
            filetypes=(("JSON files", "*.json"),),
            initialdir=os.getcwd(),
        )
        if path:
            self.dots = json.load(
                open(path, "r", encoding="utf-8"),
                cls=self.json_decoder,
            )
            self.overlay.dots = self.dots
            self.overlay.update()
            self._refresh_bindings_list()

    def toggle_listen(self, notify: bool = False):
        listen_text = "resume" if self.keyboard_listening else "pause"
        if notify:
            self.tray_icon.notify(f"Keyboard listening {listen_text}d.")
        self.listen_button.config(
            text=f"{listen_text[0].upper()}{listen_text[1:]} Listen (Esc)"
        )

        self.keyboard_listening = not self.keyboard_listening

    def keyboard_handlers(self):
        def prehandler(func: Callable[[Key, bool], None]):
            def wrapped(key: Key, injected: bool):
                if not is_special_key(key):
                    key = self.keyboard.canonical(key)

                if self.keyboard_listening:
                    func(key, injected)

            return wrapped

        @prehandler
        def on_press(key: Key, injected: bool):
            if key == SpecialKey.esc:
                self.toggle_listen()
                return

            # Handle key assignment mode
            if self._assigning_key and self._key_target_dot and is_valid_key(key):
                self._key_target_dot.key = key
                self._assigning_key = False
                self._key_target_dot = None
                self.root.after(0, self._refresh_after_key_assign)
                return

            if self.overlay.state() == WITHDRAWN:
                # Inject touch
                if self.keyboard_listening and is_valid_key(key):
                    for dot in self.dots.get_dots_by_key(key):
                        if dot.mode == "cursor":
                            px, py = get_cursor_pos()
                        else:
                            px, py = dot.x, dot.y

                        if isinstance(dot, PressDot):
                            self.touch_manager.press(dot.id, px, py)
                        elif isinstance(dot, FlickDot):
                            view = self.dots.get_view_by_dot(dot)
                            assert isinstance(view, FlickDotView)
                            view.run(self.touch_manager, px, py)
                        elif isinstance(dot, PinchDot):
                            view = self.dots.get_view_by_dot(dot)
                            assert isinstance(view, PinchDotView)
                            view.run(self.touch_manager, px, py)
                        elif isinstance(dot, RotateDot):
                            view = self.dots.get_view_by_dot(dot)
                            assert isinstance(view, RotateDotView)
                            view.run(self.touch_manager, px, py)

        @prehandler
        def on_release(key: Key, injected: bool):
            if self.overlay.state() == WITHDRAWN:
                for dot in self.dots.get_dots_by_key(key):
                    self.touch_manager.up(dot.id)
                    if isinstance(dot, (PinchDot, RotateDot)):
                        self.touch_manager.up(dot.id2)
            else:
                # Assign key to dot
                if self.dots and is_valid_key(key):
                    for dot in (
                        self.dots.current_viewed_dot,
                        self.dots.last_operated_dot,
                    ):
                        if dot and dot.key is None:
                            dot.key = key
                            self.overlay.update()
                            break

        return {"on_press": on_press, "on_release": on_release}

    def toggle_overlay(self):
        if self.overlay.state() == WITHDRAWN:
            self.overlay.show()
            toggle_state(self.dot_frame)
            toggle_state(self.bindings_frame)
        else:
            self.overlay.hide()
            toggle_state(self.dot_frame, "disabled")
            toggle_state(self.bindings_frame, "disabled")

    def touch(self):
        if self.overlay.state() == WITHDRAWN:
            try:
                self.touch_manager.apply_touches()
            except TouchError as e:
                messagebox.showerror("Error", e.args[0])
                print(e)
                self.exit()
        self.touch_task = self.root.after(10, self.touch)

    def update_dot_detail(self):
        for widget in self.dot_frame.winfo_children():
            widget.destroy()
        if not getattr(self, "_in_selection_handler", False):
            self._refresh_bindings_list()
        dot = self.dots.current_viewed_dot
        if dot:
            view = self.dots.get_view_by_dot(dot)
            details = view.detail(self.overlay.draw_dots)
            create_details(self.dot_frame, details)

            row = len(details)

            # Set Key button
            key_text = key_to_str(dot.key) if dot.key else "(none)"
            assign_label = "Press key..." if self._assigning_key else f"Set Key: {key_text}"
            key_btn = ttk.Button(
                self.dot_frame, text=assign_label,
                command=lambda: self._start_key_assignment(dot),
            )
            key_btn.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
            row += 1

            # Position editing for overlay mode
            if dot.mode == "overlay":
                self._x_var = tk.IntVar(value=dot.x)
                self._y_var = tk.IntVar(value=dot.y)

                ttk.Label(self.dot_frame, text="X").grid(row=row, column=0, padx=5)
                x_spin = ttk.Spinbox(
                    self.dot_frame, from_=0, to=9999,
                    textvariable=self._x_var, width=8,
                    command=lambda: self._update_dot_position(dot),
                )
                x_spin.grid(row=row, column=1, sticky="ew", padx=5)
                row += 1

                ttk.Label(self.dot_frame, text="Y").grid(row=row, column=0, padx=5)
                y_spin = ttk.Spinbox(
                    self.dot_frame, from_=0, to=9999,
                    textvariable=self._y_var, width=8,
                    command=lambda: self._update_dot_position(dot),
                )
                y_spin.grid(row=row, column=1, sticky="ew", padx=5)

    def _start_key_assignment(self, dot):
        self._assigning_key = True
        self._key_target_dot = dot
        self.update_dot_detail()

    def _refresh_after_key_assign(self):
        self.update_dot_detail()
        self._refresh_bindings_list()
        self.overlay.draw_dots()

    def _update_dot_position(self, dot):
        dot.x = self._x_var.get()
        dot.y = self._y_var.get()
        self.overlay.draw_dots()
        self._refresh_bindings_list()

    def _get_dot_params_str(self, dot):
        if isinstance(dot, RotateDot):
            return f"angle={dot.rotation_angle.get()}\u00b0, r={dot.radius.get()}"
        if isinstance(dot, PinchDot):
            return f"from={dot.start_distance.get()}, to={dot.end_distance.get()}"
        if isinstance(dot, FlickDot):
            return f"angle={dot.angle.get()}\u00b0, dist={dot.distance.get()}"
        if isinstance(dot, PressDot) and dot.mode == "overlay":
            return f"({dot.x}, {dot.y})"
        return ""

    def _refresh_bindings_list(self):
        if not hasattr(self, "bindings_tree"):
            return
        self._refreshing_bindings = True
        current_dot = self.dots.current_viewed_dot
        for item in self.bindings_tree.get_children():
            self.bindings_tree.delete(item)
        for dot in self.dots:
            type_name = dot.__class__.__name__.replace("Dot", "")
            params = self._get_dot_params_str(dot)
            self.bindings_tree.insert(
                "", "end", iid=str(dot.id),
                values=(dot.id, type_name, dot.mode.capitalize(), key_to_str(dot.key), params),
            )
        if current_dot and self.bindings_tree.exists(str(current_dot.id)):
            self.bindings_tree.selection_set(str(current_dot.id))
        self._refreshing_bindings = False

    def _on_binding_select(self, event=None):
        if getattr(self, "_refreshing_bindings", False):
            return
        selection = self.bindings_tree.selection()
        if not selection:
            return
        try:
            dot_id = int(self.bindings_tree.item(selection[0])["values"][0])
        except (ValueError, IndexError):
            return
        for dot in self.dots:
            if dot.id == dot_id:
                self.dots.current_viewed_dot = dot
                self._in_selection_handler = True
                self.update_dot_detail()
                self._in_selection_handler = False
                break

    def _add_binding(self):
        if len(self.dots) >= MAX_TOUCHES:
            messagebox.showinfo("Add Binding", "Maximum number of bindings reached.")
            return

        dot_type = self.overlay.new_dot_type.get()
        mode = self.new_dot_mode.get()

        if mode == "cursor":
            self.dots.add(dot_type, 0, 0, mode=mode)
        else:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            self.dots.add(dot_type, screen_w // 2, screen_h // 2, mode=mode)

        self._refresh_bindings_list()
        self.overlay.draw_dots()

    def _delete_binding(self):
        selection = self.bindings_tree.selection()
        if not selection:
            return
        dot_id = int(self.bindings_tree.item(selection[0])["values"][0])
        for dot in self.dots:
            if dot.id == dot_id:
                self.dots.remove(dot)
                break
        self.dots.current_viewed_dot = None
        self.update_dot_detail()
        self._refresh_bindings_list()
        self.overlay.draw_dots()

    def run(self):
        self.root.mainloop()
