"""The thread picker: ``<dialog id="thread-dialog">``.

A brand selector ("Thread brand: DMC"; Anchor and Madeira listed but disabled
as "coming later"), search within the brand ("DMC 321" finds the same as
"321"), colour family chips, the list, and "Own colour …". Brands and
threads come from ``kvale.core.threads``; the search state is
``colour_model.PickerState``.

Other panels call ``ThreadPicker.open(current, on_choose)``: ``current`` is
the thread reference to start from (or None) and ``on_choose(hex, ref)`` gets
the chosen screen colour and reference (None for an own colour).
"""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from kvale.core.threads import BRANDS, FAMILIES, FAMILY_CHIP, brand_name, thread_ref
from kvale_web.dom import Bindings, by_id
from kvale_web.i18n import t
from kvale_web.panels.colour_model import PickerState, colour_info
from kvale_web.panels.labels import code_text
from kvale_web.state import LANGUAGE, AppState

OnChoose = Callable[[str, "str | None"], None]


class ThreadPicker:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.dialog = by_id("thread-dialog")
        self.system = by_id("thread-system")
        self.search = by_id("thread-search")
        self.families = by_id("thread-families")
        self.count = by_id("thread-count")
        self.list = by_id("thread-list")
        self.big = by_id("thread-big")
        self.detail = by_id("thread-detail")
        self.choose = by_id("thread-choose")
        self.own = by_id("thread-own")
        self.own_chip = by_id("thread-own-chip")
        self.picker = PickerState()
        self.on_choose: OnChoose | None = None

        self.bindings = Bindings()
        self.bindings.on(self.system, "change", self.on_system)
        self.bindings.on(self.search, "input", self.on_search)
        self.bindings.on(self.search, "keydown", self.on_search_key)
        self.bindings.on(self.families, "click", self.on_family)
        self.bindings.on(self.list, "click", self.on_row)
        self.bindings.on(self.list, "dblclick", self.on_row_double)
        self.bindings.on(self.own, "input", self.on_own_input)
        self.bindings.on(self.own, "change", self.on_own_change)
        self.bindings.on(self.dialog, "close", self.on_close)
        state.subscribe(lambda _topic: self.render() if self.dialog.open else None, LANGUAGE)
        self.own_chip.style.background = str(self.own.value)

    def open(self, current: str | None, on_choose: OnChoose) -> None:
        """Show the picker, starting from thread ``current`` (a reference) if it is one."""
        self.on_choose = on_choose
        self.picker.reset(current)
        self.search.value = ""
        self.dialog.returnValue = ""
        self.dialog.showModal()
        self.render(scroll=True)
        self.search.focus()

    # Events ------------------------------------------------------------

    def on_system(self, _event: Any) -> None:
        if not self.picker.set_brand(str(self.system.value)):
            self.system.value = self.picker.brand
        self.render()

    def on_search(self, _event: Any) -> None:
        self.picker.set_query(str(self.search.value))
        self.render()

    def on_search_key(self, event: Any) -> None:
        # Enter in the search box chooses the only match, and never submits the form.
        if event.key == "Enter":
            event.preventDefault()
            if len(self.picker.results) == 1:
                self.picker.selected = self.picker.results[0].ref
                self.dialog.close("ok")

    def on_family(self, event: Any) -> None:
        button = event.target.closest("[data-family]")
        if button is not None:
            self.picker.set_family(str(button.dataset.family))
            self.render()

    def _row_ref(self, event: Any) -> str | None:
        row = event.target.closest("[data-code]")
        return None if row is None else thread_ref(self.picker.brand, str(row.dataset.code))

    def on_row(self, event: Any) -> None:
        ref = self._row_ref(event)
        if ref is not None:
            self.picker.selected = ref
            self.render()

    def on_row_double(self, event: Any) -> None:
        ref = self._row_ref(event)
        if ref is not None:
            self.picker.selected = ref
            self.dialog.close("ok")

    def on_own_input(self, _event: Any) -> None:
        self.own_chip.style.background = str(self.own.value)

    def on_own_change(self, _event: Any) -> None:
        colour = str(self.own.value).lower()
        callback = self.on_choose
        self.on_choose = None
        self.dialog.close("cancel")
        if callback is not None:
            callback(colour, None)

    def on_close(self, _event: Any) -> None:
        callback = self.on_choose
        self.on_choose = None
        thread = self.picker.chosen
        if self.dialog.returnValue == "ok" and thread is not None and callback is not None:
            callback(thread.hex_colour, thread.ref)

    # Drawing -----------------------------------------------------------

    def render(self, *, scroll: bool = False) -> None:
        picker = self.picker
        name = brand_name(picker.brand)
        options = []
        for brand in BRANDS:
            label = brand.name if brand.available else t("thread.system.soon", name=brand.name)
            disabled = "" if brand.available else " disabled"
            selected = " selected" if brand.id == picker.brand else ""
            options.append(
                f'<option value="{html.escape(brand.id)}"{disabled}{selected}>{html.escape(label)}</option>'
            )
        self.system.innerHTML = "".join(options)
        by_id("thread-system-note").textContent = t("thread.system.hint", system=name)
        by_id("thread-names-note").textContent = t("thread.namesNote", system=name)
        self.search.placeholder = t("thread.search.placeholder", system=name)

        chips = []
        for family in FAMILIES:
            dot = "" if family == "all" else f'<i style="background:{FAMILY_CHIP[family]}"></i>'
            pressed = "true" if family == picker.family else "false"
            chips.append(
                f'<button type="button" class="chipbtn" data-family="{family}" aria-pressed="{pressed}">'
                f"{dot}{html.escape(t('thread.family.' + family))}</button>"
            )
        self.families.innerHTML = "".join(chips)

        results = picker.results
        self.count.textContent = t("thread.count", n=len(results), system=name)
        if results:
            rows = []
            for item in results:
                chosen = "true" if item.ref == picker.selected else "false"
                code = html.escape(code_text(colour_info(item.hex_colour, item.ref)))
                rows.append(
                    f'<button type="button" class="dmc-row" role="option" '
                    f'data-code="{html.escape(item.code)}" aria-pressed="{chosen}" aria-selected="{chosen}">'
                    f'<span class="dmc-sw" style="background:{item.hex_colour}"></span>'
                    f'<span class="dmc-num">{code}</span><span>{html.escape(item.name)}</span></button>'
                )
            self.list.innerHTML = "".join(rows)
        else:
            self.list.innerHTML = f'<p class="dmc-empty">{html.escape(t("thread.none", system=name))}</p>'

        thread = picker.chosen
        if thread is None:
            self.big.style.background = ""
            self.detail.textContent = t("thread.pickPrompt")
        else:
            self.big.style.background = thread.hex_colour
            code = html.escape(code_text(colour_info(thread.hex_colour, thread.ref)))
            self.detail.innerHTML = f"<strong>{code}</strong> – {html.escape(thread.name)}"
        self.choose.disabled = thread is None

        if scroll and thread is not None:
            # Scroll the list only, so the brand selector stays in view.
            row = self.list.querySelector(f'[data-code="{thread.code}"]')
            if row is not None:
                self.list.scrollTop = row.offsetTop - (self.list.clientHeight - row.offsetHeight) / 2
