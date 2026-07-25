import backend, tempfile, os, time

with tempfile.TemporaryDirectory() as tmp:
    fake = os.path.join(tmp, "tray.py")
    with open(fake, "w") as f:
        f.write("import time\ntime.sleep(30)\n")

    print("running before:", backend.is_tray_running())
    ok = backend.start_tray(app_dir=tmp)
    time.sleep(0.5)
    print("start_tray ok:", ok)
    print("running after start:", backend.is_tray_running())

    ok2 = backend.start_tray(app_dir=tmp)
    print("second start_tray (no-op expected) ok:", ok2)

    backend.stop_tray()
    time.sleep(0.5)
    print("running after stop:", backend.is_tray_running())
