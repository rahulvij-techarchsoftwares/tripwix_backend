import threading


def print_thread_debug_info():
    main_thread = threading.main_thread()
    current_thread = threading.current_thread()

    print(
        f"main_thread: {main_thread.name} ({main_thread.native_id})",
    )
    print(
        f"current_thread: {current_thread.name} ({current_thread.native_id})",
    )
    print("other threads:")
    for thread in threading.enumerate():
        if thread is not main_thread and thread is not current_thread:
            print(f"  {thread.name} ({thread.native_id})")


def get_thread_id(thread):
    native_id = getattr(thread, "native_id", None)
    ident = getattr(thread, "ident", None)

    if native_id:
        return f"native_{native_id}"
    elif ident:
        return f"ident_{ident}"
    else:
        print(f"Kolo warning: thread has no id: {getattr(thread, 'name', 'unknown')}")
        return "no_thread_id"
