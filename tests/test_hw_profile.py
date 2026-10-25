"""Unit tests for the hardware profiler's parsing functions.

Every parser takes command output as text, so these run anywhere — no Linux
target hardware, no Windows, no subprocesses.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "bench"))

from hw_profile import (  # noqa: E402
    build_fields,
    bytes_to_gib,
    parse_glxinfo_b,
    parse_lscpu,
    parse_lspci_display,
    parse_meminfo,
    parse_os_release,
    parse_power_profile,
    parse_powershell_cim,
    parse_vram_bytes,
    parse_xrandr,
    render_table,
)

LSPCI_SAMPLE = """\
00:02.0 VGA compatible controller [0300]: Intel Corporation HD Graphics 5500 [8086:1616] (rev 09)
\tDeviceName: 512
\tSubsystem: Hewlett-Packard Company ZBook 15u G2 Mobile Workstation [103c:2216]
\tKernel driver in use: i915
--
04:00.0 VGA compatible controller [0300]: AMD/ATI Opal PRO [Radeon R7 M260X] [1002:6605]
\tSubsystem: Hewlett-Packard Company FirePro M4150 [103c:2259]
\tKernel driver in use: amdgpu
\tKernel modules: radeon, amdgpu
--
08:00.0 Network controller [0280]: Intel Corporation Wireless 7265 [8086:095a] (rev 59)
\tSubsystem: Intel Corporation Dual Band Wireless-AC 7265 [8086:5010]
\tKernel driver in use: iwlwifi
"""

GLX_SAMPLE = """\
name of display: :0
display: :0  screen: 0
direct rendering: Yes
Extended renderer info (GLX_MESA_query_renderer):
    Vendor: Intel (0x8086)
    Device: Mesa Intel(R) HD Graphics 5500 (BDW GT2) (0x1616)
    Version: 26.0.8
    Accelerated: yes
    Video memory: 14879MB
    Unified memory: yes
    Preferred profile: core (0x1)
"""

XRANDR_SAMPLE = """\
Screen 0: minimum 16 x 16, current 1366 x 768, maximum 32767 x 32767
eDP-1 connected primary 1366x768+0+0 (normal left inverted right x axis y axis) 310mm x 170mm
   1366x768      59.80*+
   1024x768      59.92
HDMI-A-1 disconnected (normal left inverted right x axis y axis)
"""

LSCPU_SAMPLE = """\
Architecture:                            x86_64
CPU(s):                                  4
On-line CPU(s) list:                     0-3
Vendor ID:                               GenuineIntel
Model name:                              Intel(R) Core(TM) i7-5600U CPU @ 2.60GHz
Thread(s) per core:                      2
Core(s) per socket:                      2
Socket(s):                               1
CPU max MHz:                             3200.0000
"""


class OsReleaseTests(unittest.TestCase):
    def test_parses_quoted_values(self):
        parsed = parse_os_release('PRETTY_NAME="Ubuntu 26.04.1 LTS"\nVERSION_ID="26.04"\nID=ubuntu\n')
        self.assertEqual(parsed["PRETTY_NAME"], "Ubuntu 26.04.1 LTS")
        self.assertEqual(parsed["VERSION_ID"], "26.04")
        self.assertEqual(parsed["ID"], "ubuntu")

    def test_ignores_comments_and_blank_lines(self):
        parsed = parse_os_release("# comment\n\nA=1\n")
        self.assertEqual(parsed, {"A": "1"})

    def test_empty_input(self):
        self.assertEqual(parse_os_release(""), {})


class LscpuTests(unittest.TestCase):
    def test_extracts_model_and_counts(self):
        parsed = parse_lscpu(LSCPU_SAMPLE)
        self.assertEqual(parsed["model"], "Intel(R) Core(TM) i7-5600U CPU @ 2.60GHz")
        self.assertEqual(parsed["cpus"], 4)
        self.assertEqual(parsed["cores_per_socket"], 2)
        self.assertEqual(parsed["threads_per_core"], 2)
        self.assertEqual(parsed["sockets"], 1)

    def test_missing_fields_are_none(self):
        parsed = parse_lscpu("Architecture: x86_64\n")
        self.assertIsNone(parsed["model"])
        self.assertIsNone(parsed["cpus"])

    def test_garbage_numbers_do_not_crash(self):
        parsed = parse_lscpu("CPU(s): lots\n")
        self.assertIsNone(parsed["cpus"])


class MeminfoTests(unittest.TestCase):
    def test_converts_kib_to_gib(self):
        parsed = parse_meminfo("MemTotal:       15236760 kB\nMemFree:  100 kB\n")
        self.assertEqual(parsed["total_kib"], 15236760)
        self.assertAlmostEqual(parsed["total_gib"], 14.5, places=1)

    def test_missing_memtotal(self):
        parsed = parse_meminfo("MemFree: 1 kB\n")
        self.assertIsNone(parsed["total_gib"])


class LspciTests(unittest.TestCase):
    def test_finds_both_display_devices_with_their_own_drivers(self):
        devices = parse_lspci_display(LSPCI_SAMPLE)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["pci_id"], "8086:1616")
        self.assertEqual(devices[0]["driver"], "i915")
        self.assertEqual(devices[1]["pci_id"], "1002:6605")
        self.assertEqual(devices[1]["driver"], "amdgpu")

    def test_ignores_non_display_devices(self):
        descriptions = [d["description"] for d in parse_lspci_display(LSPCI_SAMPLE)]
        self.assertFalse(any("Wireless" in d for d in descriptions))

    def test_driver_does_not_bleed_from_a_later_device(self):
        # Regression: the network controller's "Kernel driver in use: iwlwifi"
        # used to be attributed to the AMD GPU.
        for device in parse_lspci_display(LSPCI_SAMPLE):
            self.assertNotEqual(device["driver"], "iwlwifi")

    def test_empty_input(self):
        self.assertEqual(parse_lspci_display(""), [])


class GlxinfoTests(unittest.TestCase):
    def test_extracts_renderer_identity(self):
        parsed = parse_glxinfo_b(GLX_SAMPLE)
        self.assertEqual(parsed["vendor"], "Intel (0x8086)")
        self.assertIn("HD Graphics 5500", parsed["device"])
        self.assertEqual(parsed["video_memory_mb"], 14879)
        self.assertTrue(parsed["unified_memory"])
        self.assertTrue(parsed["direct_rendering"])

    def test_missing_fields_are_none(self):
        parsed = parse_glxinfo_b("")
        self.assertIsNone(parsed["device"])
        self.assertIsNone(parsed["video_memory_mb"])
        self.assertIsNone(parsed["unified_memory"])


class XrandrTests(unittest.TestCase):
    def test_reads_connected_output_refresh(self):
        outputs = parse_xrandr(XRANDR_SAMPLE)
        self.assertEqual(outputs[0]["output"], "eDP-1")
        self.assertTrue(outputs[0]["primary"])
        self.assertEqual(outputs[0]["resolution"], "1366x768")
        self.assertAlmostEqual(outputs[0]["refresh_hz"], 59.80)

    def test_records_disconnection(self):
        outputs = parse_xrandr(XRANDR_SAMPLE)
        hdmi = [o for o in outputs if o["output"] == "HDMI-A-1"][0]
        self.assertFalse(hdmi["connected"])
        self.assertIsNone(hdmi["resolution"])


class PowerAndVramTests(unittest.TestCase):
    def test_power_profile_first_line(self):
        self.assertEqual(parse_power_profile("balanced\n"), "balanced")
        self.assertEqual(parse_power_profile("performance"), "performance")

    def test_power_profile_empty(self):
        self.assertIsNone(parse_power_profile(""))
        self.assertIsNone(parse_power_profile("\n"))

    def test_vram_bytes(self):
        self.assertEqual(parse_vram_bytes("1073741824\n"), 1073741824)
        self.assertIsNone(parse_vram_bytes(""))
        self.assertIsNone(parse_vram_bytes("n/a"))

    def test_bytes_to_gib(self):
        self.assertEqual(bytes_to_gib(1073741824), 1.0)
        self.assertIsNone(bytes_to_gib(0))
        self.assertIsNone(bytes_to_gib(None))
        self.assertIsNone(bytes_to_gib("lots"))


class PowerShellTests(unittest.TestCase):
    def test_parses_single_object(self):
        payload = json.dumps({
            "Model": "ASUS V16",
            "OS": "Microsoft Windows 11 Pro 10.0.22631",
            "CPU": "Intel Core Ultra 7",
            "RAMBytes": 34359738368,
            "GPUs": [{"Name": "NVIDIA RTX 5070", "Driver": "1.2.3",
                      "VRAM": 8589934592, "Width": 1920, "Height": 1080, "Refresh": 144}],
        })
        parsed = parse_powershell_cim(payload)
        self.assertEqual(parsed["model"], "ASUS V16")
        self.assertEqual(parsed["cpu"], "Intel Core Ultra 7")
        self.assertEqual(parsed["ram_gib"], 32.0)
        self.assertEqual(parsed["gpus"][0]["Name"], "NVIDIA RTX 5070")

    def test_accepts_a_list(self):
        payload = json.dumps([{"CPU": "X", "RAMBytes": 1073741824}])
        parsed = parse_powershell_cim(payload)
        self.assertEqual(parsed["cpu"], "X")
        self.assertEqual(parsed["ram_gib"], 1.0)

    def test_bad_or_empty_json_is_tolerated(self):
        self.assertEqual(parse_powershell_cim("not json"), {})
        self.assertEqual(parse_powershell_cim(""), {})


class BuildFieldsTests(unittest.TestCase):
    def _linux_facts(self):
        return {
            "platform": "linux",
            "os_release": {"PRETTY_NAME": "Ubuntu 26.04.1 LTS", "VERSION_ID": "26.04"},
            "dmi": {"Vendor": "Hewlett-Packard", "Model": "HP ZBook 14 G2", "Board": "2216"},
            "cpu": {"model": "Intel(R) Core(TM) i7-5600U", "cores_per_socket": 2,
                    "threads_per_core": 2, "sockets": 1, "architecture": "x86_64"},
            "memory": {"total_kib": 15236760, "total_gib": 14.5},
            "pci_display": parse_lspci_display(LSPCI_SAMPLE),
            "glx": parse_glxinfo_b(GLX_SAMPLE),
            "xrandr": parse_xrandr(XRANDR_SAMPLE),
            "power_profile": "balanced",
            "vram_nodes": [{"node": "/sys/class/drm/card0/device/mem_info_vram_total",
                            "bytes": 1073741824, "gib": 1.0}],
            "storage": {"total_gib": 56.1, "free_gib": 38.6},
        }

    def test_core_rows_present(self):
        fields = dict(build_fields(self._linux_facts()))
        self.assertIn("HP ZBook 14 G2", fields["Model"])
        self.assertIn("2 cores / 4 threads", fields["CPU"])
        self.assertIn("i7-5600U", fields["CPU"])
        self.assertIn("14.5 GiB", fields["RAM"])
        self.assertIn("1366x768", fields["Display res/refresh"])
        self.assertEqual(fields["Power mode used for tests"], "balanced")

    def test_installed_gpus_are_listed_with_drivers(self):
        fields = dict(build_fields(self._linux_facts()))
        self.assertIn("HD Graphics 5500", fields["GPU (dedicated/iGPU) + driver"])
        self.assertIn("Radeon R7 M260X", fields["GPU (dedicated/iGPU) + driver"])
        self.assertIn("amdgpu", fields["GPU (dedicated/iGPU) + driver"])

    def test_vram_states_dedicated_and_shared_separately(self):
        fields = dict(build_fields(self._linux_facts()))
        self.assertIn("1.0 GiB dedicated", fields["VRAM / shared"])
        self.assertIn("unified memory", fields["VRAM / shared"])

    def test_gpu_actually_used_is_not_claimed_without_a_measurement(self):
        fields = dict(build_fields(self._linux_facts()))
        self.assertIn("not measured", fields["GPU used by UPBGE (measured)"])

    def test_bench_result_supplies_the_measured_renderer(self):
        facts = self._linux_facts()
        bench = {"gpu_renderer": "Mesa Intel(R) HD Graphics 5500 (BDW GT2)"}
        fields = dict(build_fields(facts, bench=bench))
        self.assertEqual(fields["GPU used by UPBGE (measured)"],
                         "Mesa Intel(R) HD Graphics 5500 (BDW GT2)")

    def test_missing_values_are_not_invented(self):
        facts = self._linux_facts()
        facts["vram_nodes"] = []
        facts["glx"] = {}
        fields = dict(build_fields(facts))
        self.assertEqual(fields["VRAM / shared"], "not reported")

    def test_windows_rows(self):
        facts = {
            "platform": "windows",
            "model": "ASUS V16",
            "os": "Microsoft Windows 11 Pro",
            "cpu": "Intel Core Ultra 7",
            "ram_gib": 32.0,
            "gpus": [{"Name": "NVIDIA RTX 5070", "Driver": "1.2.3", "VRAM": 8589934592,
                      "Width": 1920, "Height": 1080, "Refresh": 144}],
        }
        fields = dict(build_fields(facts, tier="A"))
        self.assertEqual(fields["Tier"], "A")
        self.assertIn("RTX 5070", fields["GPU (dedicated/iGPU) + driver"])
        self.assertIn("1920x1080", fields["Display res/refresh"])
        self.assertIn("32.0 GiB", fields["RAM"])

    def test_render_table_is_markdown(self):
        table = render_table([("Model", "X"), ("RAM", "1 GiB")])
        lines = table.splitlines()
        self.assertTrue(lines[0].startswith("| Field"))
        self.assertIn("| Model", table)
        self.assertIn("| RAM", table)


if __name__ == "__main__":
    unittest.main()
