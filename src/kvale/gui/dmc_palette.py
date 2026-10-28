from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from kvale.core.dmc import DmcColour, filter_dmc_colours

__all__ = ["ask_dmc_colour"]


def _contrasting_text_colour(colour: str) -> str:
    value = colour.lstrip("#")
    red, green, blue = (int(value[offset : offset + 2], 16) for offset in (0, 2, 4))
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return "#111111" if luminance > 160 else "#ffffff"


def ask_dmc_colour(
    parent: tk.Misc,
    initial_colour: str | None = None,
    *,
    title: str = "Velg DMC-farge",
) -> str | None:
    """Choose a DMC colour and return its approximate screen colour."""
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())
    dialog.geometry("620x520")
    dialog.minsize(520, 400)

    result: str | None = None
    selected: DmcColour | None = None
    search_var = tk.StringVar()
    detail_var = tk.StringVar(value="Velg en farge fra listen.")

    body = ttk.Frame(dialog, padding=12)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(body, text="Søk etter DMC-nummer eller fargenavn").pack(anchor=tk.W)
    search_entry = ttk.Entry(body, textvariable=search_var)
    search_entry.pack(fill=tk.X, pady=(4, 8))

    list_frame = ttk.Frame(body)
    list_frame.pack(fill=tk.BOTH, expand=True)
    tree = ttk.Treeview(
        list_frame,
        columns=("number", "name", "hex"),
        show="headings",
        selectmode="browse",
    )
    tree.heading("number", text="DMC")
    tree.heading("name", text="Fargenavn")
    tree.heading("hex", text="Skjermfarge")
    tree.column("number", width=72, minwidth=60, anchor=tk.CENTER, stretch=False)
    tree.column("name", width=330, minwidth=180)
    tree.column("hex", width=105, minwidth=90, anchor=tk.CENTER, stretch=False)
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    details = ttk.Frame(body)
    details.pack(fill=tk.X, pady=(10, 0))
    swatch = tk.Canvas(
        details,
        width=86,
        height=46,
        highlightthickness=1,
        highlightbackground="#666666",
    )
    swatch.pack(side=tk.LEFT)
    ttk.Label(details, textvariable=detail_var).pack(side=tk.LEFT, padx=(10, 0))

    ttk.Label(
        body,
        text=(
            "Skjermfarger er omtrentlige. Bruk et fysisk DMC-fargekart "
            "når nøyaktig trådfarge er viktig."
        ),
        wraplength=570,
    ).pack(fill=tk.X, pady=(10, 0))

    actions = ttk.Frame(body)
    actions.pack(anchor=tk.E, pady=(12, 0))
    choose_button = ttk.Button(actions, text="Velg", state=tk.DISABLED)
    choose_button.pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(actions, text="Avbryt", command=dialog.destroy).pack(side=tk.LEFT)

    visible_colours: list[DmcColour] = []

    def redraw_swatch() -> None:
        swatch.delete("all")
        if selected is None:
            return
        colour = selected.hex_colour
        swatch.create_rectangle(0, 0, 86, 46, fill=colour, outline=colour)
        swatch.create_text(
            43,
            23,
            text=selected.number,
            fill=_contrasting_text_colour(colour),
            font=("TkDefaultFont", 9, "bold"),
        )

    def refresh_list(*_args: object) -> None:
        nonlocal selected, visible_colours
        selected = None
        choose_button.configure(state=tk.DISABLED)
        detail_var.set("Velg en farge fra listen.")
        redraw_swatch()
        tree.delete(*tree.get_children())
        visible_colours = list(filter_dmc_colours(search_var.get()))
        for index, colour in enumerate(visible_colours):
            tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(colour.number, colour.name, colour.hex_colour.upper()),
            )

    def on_select(_event: tk.Event[tk.Misc] | None = None) -> None:
        nonlocal selected
        selection = tree.selection()
        if not selection:
            return
        selected = visible_colours[int(selection[0])]
        detail_var.set(
            f"DMC {selected.number} — {selected.name}\n"
            f"RGB {selected.red}, {selected.green}, {selected.blue}"
        )
        choose_button.configure(state=tk.NORMAL)
        redraw_swatch()

    def accept(_event: tk.Event[tk.Misc] | None = None) -> None:
        nonlocal result
        if selected is None:
            return
        result = selected.hex_colour
        dialog.destroy()

    choose_button.configure(command=accept)
    tree.bind("<<TreeviewSelect>>", on_select)
    tree.bind("<Double-Button-1>", accept)
    search_var.trace_add("write", refresh_list)
    search_entry.bind("<Down>", lambda _event: tree.focus_set())
    dialog.bind("<Escape>", lambda _event: dialog.destroy())
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    refresh_list()
    if initial_colour:
        target = initial_colour.casefold()
        for index, colour in enumerate(visible_colours):
            if colour.hex_colour.casefold() == target:
                tree.selection_set(str(index))
                tree.focus(str(index))
                tree.see(str(index))
                on_select()
                break

    search_entry.focus_set()
    dialog.update_idletasks()
    try:
        dialog.wait_visibility()
        dialog.grab_set()
    except tk.TclError:
        pass
    dialog.wait_window()
    return result
