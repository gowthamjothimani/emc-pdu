from pathlib import Path
import importlib.util


def load_reference_emc_board():
    root = Path(__file__).resolve().parents[1]
    reference_file = root / "PDU_DEV_extracted" / "PDU_DEV" / "dev" / "app" / "emc_board.py"
    if not reference_file.exists():
        return None

    spec = importlib.util.spec_from_file_location("reference_emc_board", reference_file)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "EMC_Board", None)


ReferenceEMCBoard = load_reference_emc_board()


class EMC_Board:
    def __init__(self):
        if ReferenceEMCBoard is not None:
            self.impl = ReferenceEMCBoard()
        else:
            self.impl = None
        self.last_error = None

    def turn_off_all(self):
        if self.impl is None:
            self.last_error = "Reference EMC_Board unavailable"
            return False
        try:
            result = self.impl.turn_off_all()
            self.last_error = getattr(self.impl, "last_error", None)
            return result
        except Exception as exc:
            self.last_error = str(exc)
            return False
