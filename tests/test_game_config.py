"""Pharaoh Gold's game.toml renders the values the kit's hooks expect."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "kit"

# The zero-filled section padding after .rsrc in the pinned Pharaoh.exe:
# mapped, never referenced by the game. Every unidentified hook and global
# lives in its last 512 bytes.
SENTINEL_LOW, SENTINEL_HIGH = 0x0126CE00, 0x0126D000


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, KIT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


game_config = load_module("game_config")
gen_game_config = load_module("gen_game_config")


class PharaohConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = game_config.load(ROOT)
        self.header = gen_game_config.render_header(self.cfg)

    def test_identity(self):
        self.assertEqual(self.cfg["game"]["id"], "pharaoh")
        self.assertEqual(self.cfg["game"]["executable"], "Pharaoh.exe")
        self.assertEqual(self.cfg["game"]["sha256"],
                         "b21b7d719491bb45dfb324ba95231a5b0960ab25fea1bf3fb21da65da7eca662")
        self.assertEqual(self.cfg["game"]["entry_point"], 0x00562FEA)
        self.assertEqual(self.cfg["game"]["image_base"], 0x00400000)
        self.assertEqual(self.cfg["game"]["heap_base"], 0x01400000)
        self.assertGreater(self.cfg["game"]["heap_base"], 0x0126D000)  # SizeOfImage end
        self.assertIn("#define RECOMP_HEAP_BASE 0x01400000u", self.header)
        self.assertEqual(self.cfg["translate"]["entry_points"], [0x004a98b0])
        for address in self.cfg["translate"]["entry_points"]:
            self.assertTrue(0x00401000 <= address < 0x0056e24d, hex(address))  # inside .text
        self.assertIn('#define RECOMP_APP_NAME "PharaohRecomp"', self.header)
        self.assertIn('#define RECOMP_EXECUTABLE "Pharaoh.exe"', self.header)
        self.assertIn('#define RECOMP_GUEST_ROOT "C:\\\\GOG Games\\\\Pharaoh Gold"', self.header)
        self.assertEqual(self.cfg["developer_exe_path"], (ROOT / "original/gog/app/Pharaoh.exe").resolve())
        self.assertEqual(self.cfg["listings_path"], (ROOT / "analysis/decompiled/Pharaoh.exe").resolve())

    def test_every_kit_macro_is_rendered(self):
        for macro in ("RECOMP_HOOK_FRAME_CLOCK_BEGIN", "RECOMP_HOOK_FRAME_CLOCK_WAIT",
                      "RECOMP_HOOK_FRAME_CLOCK_WAIT_CLAMP", "RECOMP_HOOK_FRAME_CLOCK_CLAMP_DEADLINE",
                      "RECOMP_HOOK_FRAME_CLOCK_WAIT_DEADLINE", "RECOMP_HOOK_CURSOR_SURFACE_PTRS_COUNT 2",
                      "RECOMP_HOOK_MOUSE_VTABLE", "RECOMP_HOOK_MOUSE_DEVICE_PTR", "RECOMP_HOOK_MOUSE_DEVICE_RIGHT",
                      "RECOMP_HOOK_CAMERA", "RECOMP_GLOBAL_SIMULATION_TURN_ADDR", "RECOMP_GLOBAL_COMMAND_FRAME_ADDR",
                      "RECOMP_GLOBAL_ENTITY_BASE_ADDR", "RECOMP_GLOBAL_ENTITY_BASE_STRIDE",
                      "RECOMP_GLOBAL_ENTITY_BASE_COUNT"):
            self.assertIn("#define " + macro, self.header)

    def test_unidentified_addresses_stay_in_the_sentinel_padding(self):
        """Until a hook is found, it must point where the game never looks."""
        addresses = [self.cfg["translate"]["animation_counter"]]
        for value in self.cfg["hooks"].values():
            addresses += value if isinstance(value, list) else [value]
        addresses += [entry["addr"] for entry in self.cfg["globals"].values()]
        for address in addresses:
            self.assertTrue(SENTINEL_LOW <= address < SENTINEL_HIGH, hex(address))
        self.assertEqual(len(addresses), len(set(addresses)), "sentinels must not alias one another")
        self.assertEqual(self.cfg["translate"]["volatile_reads"], [])

    def test_bundle_exclusions_and_setup(self):
        for pattern in ("__support", "*.dll", "*.DLL", "*.pdf", "*.M3D", "webcache.zip"):
            self.assertIn(pattern, self.cfg["bundle"]["exclude"])
        stage = load_module("stage_game_files")
        exclude = self.cfg["bundle"]["exclude"]
        self.assertNotIn("BINKS", exclude)
        # The executable, cinematics, data and the game's .txt model files stay in.
        for kept in ("Pharaoh.exe", "Pharaoh.ini", "Figure_model.txt", "Pharaoh_Text.eng",
                     "Data/Pharaoh_General.sg3", "AUDIO/Music/Egypt.mp3",
                     "Maps/Alexandria.map", "BINKS/High/intro_big.bik"):
            self.assertFalse(stage.excluded(Path(kept), exclude), kept)
        for dropped in ("mss32.dll", "BINKW32.DLL", "SMACKW32.DLL", "MSSEAX.M3D", "MP3DEC.ASI", "mssb16.tsk",
                        "goggame-1207659046.hashdb", "goggame-1207659046.info", "cleoicon.ico",
                        "Pharaoh - manual.pdf", "Readme.txt", "webcache.zip"):
            self.assertTrue(stage.excluded(Path(dropped), exclude), dropped)
        self.assertEqual(self.cfg["setup"]["required_dirs"], ["AUDIO", "BINKS", "Data", "Maps"])
        self.assertNotIn("annotations_url", self.cfg["setup"])


if __name__ == "__main__":
    unittest.main()
