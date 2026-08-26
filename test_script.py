import unittest
from pathlib import Path

import script


class GetPlayCommandTests(unittest.TestCase):
    def test_get_play_command_darwin_uses_afplay(self):
        command = script.get_play_command(Path("/tmp/example.m4a"), "Darwin")
        self.assertEqual(command, ["afplay", "/tmp/example.m4a"])

    def test_get_play_command_windows_uses_powershell(self):
        command = script.get_play_command(Path("/tmp/example.m4a"), "Windows")
        self.assertEqual(command[0], "powershell.exe")
        self.assertEqual(command[5], "-Command")
        self.assertIn("MediaPlayer", command[6])


if __name__ == "__main__":
    unittest.main()
