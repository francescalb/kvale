import importlib.util

# The GUI tests need Tkinter, which some Python builds leave out.
collect_ignore = [] if importlib.util.find_spec("tkinter") else ["test_gui.py"]
