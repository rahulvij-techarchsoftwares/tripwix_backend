from __future__ import annotations

import os
import types


def attrs_filter(frame: types.FrameType, event: str, arg: object) -> bool:
    """
    Ignore attrs generated code

    The attrs library constructs an artificial filename for generated
    class methods like __init__ and __hash__.

    It also uses a fake module without a path when creating a class.
    """
    filename = frame.f_code.co_filename
    if filename:
        return filename.startswith("<attrs generated")
    else:  # pragma: no cover
        previous = frame.f_back
        if previous is not None and previous.f_code.co_filename == "":
            previous = previous.f_back  # pragma: no cover
        return previous is not None and previous.f_code.co_filename.endswith(
            os.path.normpath("attr/_make.py")
        )
