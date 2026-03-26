from textual.widgets import OptionList


class CommandPalette(OptionList):
    def __init__(self, matches=None, **kwargs):
        super().__init__(id="command-palette", **kwargs)
        self._matches = list(matches or [])

    def on_mount(self) -> None:
        self.display = False

    def set_matches(self, matches) -> None:
        self._matches = list(matches)
        self.clear_options()
        if self._matches:
            self.add_options([match.label or f"/{match.name}" for match in self._matches])
            self.highlighted = 0
            self.display = True
            return
        self.display = False

    def current_match(self):
        if not self._matches:
            return None
        highlighted = self.highlighted or 0
        highlighted = max(0, min(highlighted, len(self._matches) - 1))
        return self._matches[highlighted]
