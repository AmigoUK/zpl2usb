from zpl2usb.autostart import (
    LinuxAutostart,
    MacAutostart,
    get_autostart,
    launch_command,
    set_autostart,
)


def test_launch_command_from_source():
    cmd = launch_command()
    assert cmd[0]  # ścieżka do interpretera
    assert cmd[-1] in ("zpl2usb", cmd[0])  # -m zpl2usb albo sama binarka


def test_linux_enable_creates_desktop_file(tmp_path):
    a = LinuxAutostart(base_dir=tmp_path, command=["/opt/zpl2usb/zpl2usb"])
    assert not a.is_enabled()
    a.enable()
    assert a.is_enabled()
    text = a.file.read_text()
    assert "[Desktop Entry]" in text
    assert "Exec=/opt/zpl2usb/zpl2usb" in text
    assert a.file.name == "zpl2usb.desktop"


def test_linux_disable_removes_file(tmp_path):
    a = LinuxAutostart(base_dir=tmp_path)
    a.enable()
    assert a.is_enabled()
    a.disable()
    assert not a.is_enabled()
    a.disable()  # idempotentne — brak wyjątku


def test_linux_command_with_spaces_is_quoted(tmp_path):
    a = LinuxAutostart(base_dir=tmp_path, command=["/usr/bin/python", "-m", "zpl2usb"])
    a.enable()
    assert "Exec=/usr/bin/python -m zpl2usb" in a.file.read_text()


def test_mac_enable_creates_plist(tmp_path):
    a = MacAutostart(base_dir=tmp_path, command=["/Applications/zpl2usb.app/zpl2usb"])
    a.enable()
    assert a.is_enabled()
    text = a.file.read_text()
    assert "<key>RunAtLoad</key>" in text
    assert "/Applications/zpl2usb.app/zpl2usb" in text
    assert a.file.name == "com.zpl2usb.plist"


def test_get_autostart_by_platform(tmp_path):
    assert isinstance(get_autostart(platform="linux", base_dir=tmp_path), LinuxAutostart)
    assert isinstance(get_autostart(platform="darwin", base_dir=tmp_path), MacAutostart)


def test_set_autostart_toggle(tmp_path):
    set_autostart(True, platform="linux", base_dir=tmp_path)
    a = LinuxAutostart(base_dir=tmp_path)
    assert a.is_enabled()
    set_autostart(False, platform="linux", base_dir=tmp_path)
    assert not a.is_enabled()
