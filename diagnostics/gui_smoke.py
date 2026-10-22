"""Exercise the desktop's actual open -> validate -> run -> plot path."""
from __future__ import annotations

import sys
import tempfile
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from velch.gui import VelchWorkbench  # noqa: E402


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="velch_gui_smoke_") as directory:
        root = tk.Tk()
        root.withdraw()
        app = VelchWorkbench(root, project / "examples" / "vehicle_v2" / "case.json")
        app.selected_path = ("wheels", 0, "profile", "file")
        app.preview_profile()
        assert app.profile_plot.points, "GUI did not preview a wheel profile"
        output = Path(directory) / "output"
        app.output_var.set(str(output))
        app.run_case()
        state = {"timed_out": False}

        def check() -> None:
            if app.running:
                root.after(100, check)
            else:
                root.quit()

        def timeout() -> None:
            state["timed_out"] = True
            app.stop_run()
            root.quit()

        root.after(100, check)
        root.after(60000, timeout)
        root.mainloop()
        assert not state["timed_out"], "GUI solver path timed out"
        assert (output / "history.csv").is_file(), "GUI did not produce history.csv"
        assert (output / "manifest.json").is_file(), "GUI did not produce manifest.json"
        assert app.result_path is not None and app.result_path.samefile(output / "history.csv"), (
            f"GUI did not load its result: {app.result_path!r} != {(output / 'history.csv')!r}; "
            f"{app.status_var.get()}\n{app.log.get('1.0', 'end')}"
        )
        assert app.plot.points, "GUI did not draw a result curve"
        print("GUI smoke passed: open, profile preview, validate, run, result load, plot")
        root.destroy()


if __name__ == "__main__":
    main()
