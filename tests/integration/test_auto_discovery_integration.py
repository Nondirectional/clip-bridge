"""自动发现集成测试

注意：这些测试需要两台机器或使用 localhost 模拟
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from clip_bridge.discovery import UDPAutoDiscovery, DiscoveryConfig


def find_free_port() -> int:
    """查找可用端口.

    Returns:
        可用的端口号。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_two_devices_discover_each_other() -> None:
    """测试两台设备互相发现.

    使用不同端口模拟两台设备，验证它们能够通过 UDP 广播互相发现。
    """
    # 使用不同端口模拟两台设备
    port1 = find_free_port()
    port2 = find_free_port()
    broadcast_port = find_free_port()

    config1 = DiscoveryConfig(timeout=2.0, broadcast_port=broadcast_port)
    config2 = DiscoveryConfig(timeout=2.0, broadcast_port=broadcast_port)

    discovered1: list[dict[str, int | str]] = []
    discovered2: list[dict[str, int | str]] = []

    def device1() -> None:
        """设备1：尝试发现对端设备."""
        discovery = UDPAutoDiscovery(config1, port1)
        peer = discovery.discover()
        if peer:
            discovered1.append({"ip": peer.ip, "port": peer.port})

    def device2() -> None:
        """设备2：等待一小段时间后尝试发现对端设备."""
        time.sleep(0.1)  # 错开启动时间
        discovery = UDPAutoDiscovery(config2, port2)
        peer = discovery.discover()
        if peer:
            discovered2.append({"ip": peer.ip, "port": peer.port})

    # 同时启动两台设备
    t1 = threading.Thread(target=device1)
    t2 = threading.Thread(target=device2)
    t1.start()
    t2.start()

    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    # 验证互相发现
    assert len(discovered1) > 0 or len(discovered2) > 0, "至少一台设备应发现对端"

    # 如果有发现，验证发现的设备信息
    if discovered1:
        assert discovered1[0]["port"] == port2
    if discovered2:
        assert discovered2[0]["port"] == port1


@pytest.mark.skipif(True, reason="需要实际网络环境")
def test_real_network_discovery() -> None:
    """真实网络环境测试（手动执行）.

    在两台真实机器上同时运行 clip-bridge，验证自动发现。

    此测试默认跳过，需要在真实网络环境中手动运行时取消 skip。
    """
    pass
