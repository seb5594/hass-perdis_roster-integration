"""Static checks that need no Home Assistant installation."""

import json
import re
import struct
import unittest

from support import COMPONENT, ROOT


def keys(tree, prefix=""):
    """Every key path of a nested dict, e.g. "entity/sensor/today/name"."""
    found = set()
    for key, value in tree.items():
        path = f"{prefix}/{key}"
        found.add(path)
        if isinstance(value, dict):
            found |= keys(value, path)
    return found


class IntegrationLayout(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((COMPONENT / "manifest.json").read_text())
        self.english = json.loads((COMPONENT / "translations/en.json").read_text())

    def test_manifest_domain_matches_folder_and_constants(self):
        self.assertEqual(self.manifest["domain"], COMPONENT.name)
        self.assertRegex((COMPONENT / "const.py").read_text(), rf'DOMAIN(: Final)? = "{COMPONENT.name}"')

    def test_no_requirements_keep_the_installation_small(self):
        self.assertEqual(self.manifest["requirements"], [])

    def test_version_is_a_calendar_version(self):
        self.assertRegex(self.manifest["version"], r"^\d{4}\.\d{1,2}\.\d{1,2}(\.\d+)?$")

    def test_hacs_zip_is_named_after_the_domain(self):
        hacs = json.loads((ROOT / "hacs.json").read_text())
        self.assertEqual(hacs["filename"], f"{COMPONENT.name}.zip")

    def test_translations_mirror_strings(self):
        strings = json.loads((COMPONENT / "strings.json").read_text())
        self.assertEqual(strings, self.english)

    def test_german_translation_has_the_same_keys(self):
        german = json.loads((COMPONENT / "translations/de.json").read_text())
        self.assertEqual(keys(german), keys(self.english))

    def test_every_entity_has_a_name_and_an_icon(self):
        icons = json.loads((COMPONENT / "icons.json").read_text())["entity"]
        for platform, entities in self.english["entity"].items():
            for key, texts in entities.items():
                self.assertIn("name", texts, f"{platform}.{key}")
                if platform != "binary_sensor" or key != "portal_online":  # device class brings its icon
                    self.assertIn(key, icons.get(platform, {}), f"{platform}.{key} has no icon")

    def test_every_described_entity_is_translated(self):
        for platform in ("sensor", "binary_sensor"):
            source = (COMPONENT / f"{platform}.py").read_text()
            for key in re.findall(r'key="([a-z_]+)"', source):
                self.assertIn(key, self.english["entity"][platform], f"{platform}.{key} has no translation")

    def test_device_triggers_are_translated(self):
        source = (COMPONENT / "const.py").read_text()
        block = source[source.index("class TimelineEvent"):]
        events = re.findall(r'^\s+[A-Z_]+ = "([a-z_]+)"', block, re.M)
        self.assertEqual(set(events), set(self.english["device_automation"]["trigger_type"]))

    def test_cards_carry_the_integration_version(self):
        script = (COMPONENT / "frontend/perdis-cards.js").read_text()
        self.assertIn(f'const VERSION = "{self.manifest["version"]}";', script)

    def test_brand_images_have_the_sizes_home_assistant_expects(self):
        def size(name):
            data = (COMPONENT / "brand" / name).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", name)
            return struct.unpack(">II", data[16:24])

        self.assertEqual(size("icon.png"), (256, 256))
        self.assertEqual(size("icon@2x.png"), (512, 512))
        self.assertTrue(128 <= min(size("logo.png")) <= 256)
        self.assertTrue(256 <= min(size("logo@2x.png")) <= 512)


if __name__ == "__main__":
    unittest.main()
