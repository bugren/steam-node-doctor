"""引擎单元测试：不联网，全部基于临时 hosts 文件。"""

import os
import tempfile
import unittest
from unittest import mock

from steamfix import engine


class HostsTests(unittest.TestCase):
    def setUp(self):
        fd, self.hosts = tempfile.mkstemp(prefix="hosts-test-")
        os.close(fd)
        with open(self.hosts, "w", encoding="utf-8") as f:
            f.write(
                "127.0.0.1 localhost\n"
                "127.0.0.1 store.steampowered.com\n"
                "127.0.0.1 api.steampowered.com\n"
                "104.83.198.104 store.steampowered.com\n"
                "example.com 1.2.3.4\n"
            )
        self.patch = mock.patch.object(engine, "HOSTS_PATH", self.hosts)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        for suffix in ("", ".steamfix.bak"):
            try:
                os.unlink(self.hosts + suffix)
            except OSError:
                pass

    def test_scan_hosts_finds_hijack(self):
        lines = engine.scan_hosts()
        self.assertEqual(len(lines), 2)
        self.assertTrue(any("store.steampowered.com" in l for l in lines))

    def test_pinned_ips(self):
        store, community = engine.pinned_ips()
        self.assertEqual(store, "104.83.198.104")
        self.assertEqual(community, "")

    def test_apply_fix_cleans_and_writes_block(self):
        res = engine.apply_fix(store_ip="23.15.142.182")
        self.assertEqual(res["store_ip"], "23.15.142.182")

        with open(self.hosts, encoding="utf-8") as f:
            text = f.read()

        # 劫持行和旧的裸固定行都应消失
        self.assertNotIn("127.0.0.1 store.steampowered.com", text)
        self.assertNotIn("127.0.0.1 api.steampowered.com", text)
        self.assertEqual(text.count("store.steampowered.com"), 1)
        # 标记块存在
        self.assertIn(engine.MARK_BEGIN, text)
        self.assertIn(engine.MARK_END, text)
        self.assertIn("23.15.142.182 store.steampowered.com", text)
        # 无关行保留
        self.assertIn("example.com 1.2.3.4", text)
        # 备份存在
        self.assertTrue(os.path.exists(self.hosts + ".steamfix.bak"))

    def test_apply_fix_is_idempotent(self):
        engine.apply_fix(store_ip="23.15.142.182")
        engine.apply_fix(store_ip="23.41.38.92")
        with open(self.hosts, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(text.count(engine.MARK_BEGIN), 1)
        self.assertEqual(text.count("store.steampowered.com"), 1)
        self.assertIn("23.41.38.92", text)

    def test_best_of_prefers_ok_and_fastest(self):
        probes = [
            engine.Probe("1.1.1.1", 0, 0.0, "pool"),
            engine.Probe("2.2.2.2", 200, 0.9, "pool"),
            engine.Probe("3.3.3.3", 200, 0.4, "pool"),
        ]
        self.assertEqual(engine.best_of(probes), "3.3.3.3")

    def test_best_of_empty(self):
        self.assertEqual(engine.best_of([]), "")


if __name__ == "__main__":
    unittest.main()
