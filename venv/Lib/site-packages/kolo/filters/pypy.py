import types


def pypy_filter(frame: types.FrameType, event: str, arg: object) -> bool:
    return "<builtin>/" in frame.f_code.co_filename
