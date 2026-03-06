# 自动发现功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 添加 UDP 广播自动发现功能，使 Clip Bridge 设备能在局域网内自动发现彼此并建立连接。

**架构:** 使用 UDP 广播协议 `CLIP-HELLO:<port>`，设备启动时广播自身存在并监听他人广播，发现对端后更新配置并建立 TCP 连接。

**技术栈:**
- Python 3.12 标准库 `socket` (UDP)
- pytest (测试)
- unittest.mock (测试用 UDP socket 模拟)

---

### Task 1: 配置扩展 - 添加自动发现选项

**Files:**
- Modify: `clip_bridge/config.py`

**Step 1: 阅读现有配置结构**

读取 `clip_bridge/config.py`，了解 `Config` dataclass 的当前定义。

**Step 2: 添加自动发现配置字段**

在 `Config` dataclass 中添加新字段：

```python
@dataclass
class Config:
    # 现有字段...
    auto_discover: bool = True          # 是否启用自动发现
    discovery_timeout: float = 3.0      # 发现超时时间（秒）
    broadcast_port: int = 9997          # 广播监听端口
```

**Step 3: 运行现有测试确保无破坏**

```bash
pytest tests/ -v
```

预期: 所有现有测试通过

**Step 4: 提交**

```bash
git add clip_bridge/config.py
git commit -m "feat(config): add auto-discovery configuration options

- Add auto_discover bool (default True)
- Add discovery_timeout float (default 3.0)
- Add broadcast_port int (default 9997)"
```

---

### Task 2: 发现模块 - 基础结构和数据类

**Files:**
- Create: `clip_bridge/discovery.py`

**Step 1: 编写数据类测试**

创建 `tests/test_discovery.py`:

```python
import pytest
from clip_bridge.discovery import PeerDevice, DiscoveryConfig


def test_peer_device_creation():
    """测试 PeerDevice 数据类创建"""
    peer = PeerDevice(ip="192.168.1.100", port=9998, last_seen=1234567890.0)
    assert peer.ip == "192.168.1.100"
    assert peer.port == 9998
    assert peer.last_seen == 1234567890.0


def test_discovery_config_defaults():
    """测试 DiscoveryConfig 默认值"""
    config = DiscoveryConfig()
    assert config.broadcast_port == 9997
    assert config.timeout == 3.0
    assert config.broadcast_interval == 0.5


def test_discovery_config_custom():
    """测试 DiscoveryConfig 自定义值"""
    config = DiscoveryConfig(broadcast_port=9996, timeout=5.0, broadcast_interval=1.0)
    assert config.broadcast_port == 9996
    assert config.timeout == 5.0
    assert config.broadcast_interval == 1.0
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_discovery.py::test_peer_device_creation -v
```

预期: FAIL - `ModuleNotFoundError: No module named 'clip_bridge.discovery'`

**Step 3: 实现数据类**

创建 `clip_bridge/discovery.py`:

```python
"""UDP 广播自动发现模块"""

from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryConfig:
    """自动发现配置"""
    broadcast_port: int = 9997      # 广播监听端口
    timeout: float = 3.0            # 发现超时时间（秒）
    broadcast_interval: float = 0.5 # 广播间隔（秒）


@dataclass
class PeerDevice:
    """发现的对端设备信息"""
    ip: str          # 设备 IP 地址
    port: int        # 设备监听端口
    last_seen: float # 最后发现时间（Unix 时间戳）
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_discovery.py -v
```

预期: PASS (3 tests)

**Step 5: 提交**

```bash
git add clip_bridge/discovery.py tests/test_discovery.py
git commit -m "feat(discovery): add base data structures

- Add DiscoveryConfig dataclass with defaults
- Add PeerDevice dataclass for discovered devices"
```

---

### Task 3: 发现模块 - 广播协议编码/解码

**Files:**
- Modify: `clip_bridge/discovery.py`
- Modify: `tests/test_discovery.py`

**Step 1: 编编码/解码测试**

在 `tests/test_discovery.py` 中添加:

```python
from clip_bridge.discovery import encode_broadcast, decode_broadcast, BROADCAST_PREFIX


def test_encode_broadcast():
    """测试广播消息编码"""
    message = encode_broadcast(9999)
    assert message == b"CLIP-HELLO:9999"


def test_encode_broadcast_different_port():
    """测试不同端口的编码"""
    message = encode_broadcast(9998)
    assert message == b"CLIP-HELLO:9998"


def test_decode_broadcast_valid():
    """测试解码有效广播消息"""
    message = b"CLIP-HELLO:9998"
    port = decode_broadcast(message)
    assert port == 9998


def test_decode_broadcast_invalid_prefix():
    """测试解码无效前缀"""
    message = b"INVALID:9998"
    with pytest.raises(ValueError, match="Invalid broadcast prefix"):
        decode_broadcast(message)


def test_decode_broadcast_invalid_format():
    """测试解码无效格式"""
    message = b"CLIP-HELLO:abc"
    with pytest.raises(ValueError, match="Invalid port format"):
        decode_broadcast(message)


def test_decode_broadcast_empty_port():
    """测试空端口"""
    message = b"CLIP-HELLO:"
    with pytest.raises(ValueError, match="Empty port"):
        decode_broadcast(message)
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_discovery.py::test_encode_broadcast -v
```

预期: FAIL - function not defined

**Step 3: 实现编码/解码函数**

在 `clip_bridge/discovery.py` 中添加:

```python
# 广播协议常量
BROADCAST_PREFIX = b"CLIP-HELLO:"
BROADCAST_SEPARATOR = b":"


def encode_broadcast(port: int) -> bytes:
    """编码广播消息

    Args:
        port: 本地监听端口

    Returns:
        广播消息字节

    Raises:
        ValueError: 端口无效
    """
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid port: {port}")
    return BROADCAST_PREFIX + str(port).encode()


def decode_broadcast(data: bytes) -> int:
    """解码广播消息

    Args:
        data: 接收到的广播消息字节

    Returns:
        对端监听端口

    Raises:
        ValueError: 消息格式无效
    """
    if not data.startswith(BROADCAST_PREFIX):
        raise ValueError(f"Invalid broadcast prefix: {data[:20]}")

    port_str = data[len(BROADCAST_PREFIX):].decode()
    if not port_str:
        raise ValueError("Empty port")

    try:
        port = int(port_str)
    except ValueError as e:
        raise ValueError(f"Invalid port format: {port_str}") from e

    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid port number: {port}")

    return port
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_discovery.py::test_encode_broadcast -v
pytest tests/test_discovery.py::test_decode_broadcast -v
```

预期: PASS (7 tests)

**Step 5: 提交**

```bash
git add clip_bridge/discovery.py tests/test_discovery.py
git commit -m "feat(discovery): add broadcast encode/decode functions

- Add encode_broadcast() to create CLIP-HELLO:<port> messages
- Add decode_broadcast() to parse broadcast messages
- Add validation for port ranges and message format"
```

---

### Task 4: 发现模块 - UDP 监听器

**Files:**
- Modify: `clip_bridge/discovery.py`
- Modify: `tests/test_discovery.py`

**Step 1: 编写监听器测试**

在 `tests/test_discovery.py` 中添加:

```python
import socket
import time
import threading
from unittest.mock import patch, MagicMock
from clip_bridge.discovery import UDPAutoDiscovery


def test_listener_receives_broadcast():
    """测试监听器接收广播消息"""
    # 创建发现实例
    discovery = UDPAutoDiscovery(local_port=9999)

    # 在后台线程运行监听器
    discovered = []
    def run_listener():
        peer = discovery._listen_once()
        if peer:
            discovered.append(peer)

    listener_thread = threading.Thread(target=run_listener)
    listener_thread.start()

    # 等待监听器启动
    time.sleep(0.1)

    # 发送广播消息
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(b"CLIP-HELLO:9998", ("255.255.255.255", 9997))
    sock.close()

    # 等待接收
    listener_thread.join(timeout=2.0)

    assert len(discovered) == 1
    assert discovered[0].port == 9998
    assert discovered[0].ip != ""  # 应该有 IP 地址


def test_listener_filters_invalid_messages():
    """测试监听器过滤无效消息"""
    discovery = UDPAutoDiscovery(local_port=9999)

    discovered = []
    def run_listener():
        peer = discovery._listen_once()
        if peer:
            discovered.append(peer)

    listener_thread = threading.Thread(target=run_listener)
    listener_thread.start()
    time.sleep(0.1)

    # 发送无效消息
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(b"INVALID:9998", ("255.255.255.255", 9997))
    sock.close()

    listener_thread.join(timeout=2.0)

    # 应该没有发现任何设备
    assert len(discovered) == 0


def test_listener_filters_own_broadcast():
    """测试监听器过滤自己的广播"""
    discovery = UDPAutoDiscovery(local_port=9999)

    discovered = []
    def run_listener():
        peer = discovery._listen_once()
        if peer:
            discovered.append(peer)

    listener_thread = threading.Thread(target=run_listener)
    listener_thread.start()
    time.sleep(0.1)

    # 发送与自己端口相同的广播
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(b"CLIP-HELLO:9999", ("255.255.255.255", 9997))
    sock.close()

    listener_thread.join(timeout=2.0)

    # 应该过滤掉自己的广播
    assert len(discovered) == 0
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_discovery.py::test_listener_receives_broadcast -v
```

预期: FAIL - class not defined

**Step 3: 实现 UDPAutoDiscovery 类基础结构和监听器**

在 `clip_bridge/discovery.py` 中添加:

```python
import socket
import time
from typing import Optional


class UDPAutoDiscovery:
    """UDP 自动发现"""

    def __init__(self, config: DiscoveryConfig, local_port: int):
        """初始化自动发现

        Args:
            config: 发现配置
            local_port: 本地监听端口（用于过滤自己的广播）
        """
        self._config = config
        self._local_port = local_port
        self._broadcast_socket: Optional[socket.socket] = None
        self._listen_socket: Optional[socket.socket] = None

    def _listen_once(self) -> Optional[PeerDevice]:
        """监听一次广播

        Returns:
            发现的设备信息，超时返回 None
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)  # 1秒超时

        try:
            sock.bind(("0.0.0.0", self._config.broadcast_port))
            data, addr = sock.recvfrom(1024)

            # 解析广播消息
            try:
                port = decode_broadcast(data)
            except ValueError:
                logger.debug(f"Received invalid broadcast from {addr}")
                return None

            # 过滤自己的广播
            if port == self._local_port:
                logger.debug(f"Filtered own broadcast (port {port})")
                return None

            # 记录发现的设备
            ip = addr[0]
            logger.info(f"Discovered peer: {ip}:{port}")
            return PeerDevice(ip=ip, port=port, last_seen=time.time())

        except socket.timeout:
            return None
        finally:
            sock.close()
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_discovery.py::test_listener_receives_broadcast -v
pytest tests/test_discovery.py::test_listener_filters_invalid_messages -v
pytest tests/test_discovery.py::test_listener_filters_own_broadcast -v
```

预期: PASS

**Step 5: 提交**

```bash
git add clip_bridge/discovery.py tests/test_discovery.py
git commit -m "feat(discovery): add UDP broadcast listener

- Add UDPAutoDiscovery class with _listen_once() method
- Filter out own broadcasts by port matching
- Validate incoming broadcast messages
- Add comprehensive listener tests"
```

---

### Task 5: 发现模块 - 广播发送器

**Files:**
- Modify: `clip_bridge/discovery.py`
- Modify: `tests/test_discovery.py`

**Step 1: 编写广播发送器测试**

在 `tests/test_discovery.py` 中添加:

```python
def test_broadcast_presence():
    """测试广播自身存在"""
    discovery = UDPAutoDiscovery(
        config=DiscoveryConfig(broadcast_port=9997),
        local_port=9999
    )

    # 创建监听器接收广播
    received_messages = []

    def listener():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(2.0)
        sock.bind(("0.0.0.0", 9997))
        try:
            while True:
                data, addr = sock.recvfrom(1024)
                received_messages.append((data, addr))
                if len(received_messages) >= 2:  # 接收2条广播后停止
                    break
        except socket.timeout:
            pass
        finally:
            sock.close()

    # 启动监听器
    listener_thread = threading.Thread(target=listener)
    listener_thread.start()

    time.sleep(0.1)  # 等待监听器启动

    # 发送广播
    discovery._broadcast_presence()

    # 等待接收
    listener_thread.join(timeout=3.0)

    # 验证广播内容
    assert len(received_messages) >= 1
    data, addr = received_messages[0]
    assert data == b"CLIP-HELLO:9999"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_discovery.py::test_broadcast_presence -v
```

预期: FAIL - method not implemented

**Step 3: 实现广播发送器**

在 `clip_bridge/discovery.py` 的 `UDPAutoDiscovery` 类中添加:

```python
def _broadcast_presence(self) -> None:
    """广播自身存在"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        message = encode_broadcast(self._local_port)
        # 广播到网络广播地址
        sock.sendto(message, ("255.255.255.255", self._config.broadcast_port))
        logger.debug(f"Broadcasted presence on port {self._local_port}")
    finally:
        sock.close()
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_discovery.py::test_broadcast_presence -v
```

预期: PASS

**Step 5: 提交**

```bash
git add clip_bridge/discovery.py tests/test_discovery.py
git commit -m "feat(discovery): add broadcast presence sender

- Add _broadcast_presence() method to UDPAutoDiscovery
- Send CLIP-HELLO:<port> to broadcast address
- Add test to verify broadcast message format"
```

---

### Task 6: 发现模块 - 主发现流程

**Files:**
- Modify: `clip_bridge/discovery.py`
- Modify: `tests/test_discovery.py`

**Step 1: 编写主发现流程测试**

在 `tests/test_discovery.py` 中添加:

```python
def test_discover_peer_found():
    """测试成功发现对端"""
    config = DiscoveryConfig(timeout=2.0, broadcast_interval=0.5)

    # 模拟对端广播
    def mock_peer_broadcaster():
        time.sleep(0.2)  # 延迟启动，模拟真实场景
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for _ in range(5):
            sock.sendto(b"CLIP-HELLO:9998", ("255.255.255.255", 9997))
            time.sleep(0.5)
        sock.close()

    peer_thread = threading.Thread(target=mock_peer_broadcaster)
    peer_thread.start()

    # 运行发现
    discovery = UDPAutoDiscovery(config=config, local_port=9999)
    peer = discovery.discover()

    peer_thread.join(timeout=5.0)

    assert peer is not None
    assert peer.port == 9998


def test_discover_peer_timeout():
    """测试超时未发现"""
    config = DiscoveryConfig(timeout=1.0, broadcast_interval=0.5)
    discovery = UDPAutoDiscovery(config=config, local_port=9999)
    peer = discovery.discover()

    assert peer is None


def test_discover_peer_multiple():
    """测试发现多个设备时返回第一个"""
    config = DiscoveryConfig(timeout=2.0, broadcast_interval=0.5)

    def mock_multiple_peers():
        time.sleep(0.2)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # 先发送设备2
        sock.sendto(b"CLIP-HELLO:9998", ("255.255.255.255", 9997))
        time.sleep(0.3)
        # 再发送设备3
        sock.sendto(b"CLIP-HELLO:9997", ("255.255.255.255", 9997))
        sock.close()

    peer_thread = threading.Thread(target=mock_multiple_peers)
    peer_thread.start()

    discovery = UDPAutoDiscovery(config=config, local_port=9999)
    peer = discovery.discover()

    peer_thread.join(timeout=5.0)

    assert peer is not None
    # 应该返回发现的第一个设备
    assert peer.port in [9998, 9997]
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_discovery.py::test_discover_peer_found -v
```

预期: FAIL - method not implemented

**Step 3: 实现主发现流程**

在 `clip_bridge/discovery.py` 的 `UDPAutoDiscovery` 类中添加:

```python
def discover(self) -> Optional[PeerDevice]:
    """执行自动发现

    在超时时间内:
    1. 持续广播自身存在
    2. 监听其他设备的广播
    3. 发现设备后立即返回

    Returns:
        发现的设备信息，未发现返回 None
    """
    logger.info(f"Starting auto-discovery (timeout={self._config.timeout}s)...")

    start_time = time.time()
    discovered_peer: Optional[PeerDevice] = None

    while time.time() - start_time < self._config.timeout:
        # 先尝试监听（可能已有设备在广播）
        peer = self._listen_once()
        if peer:
            logger.info(f"Discovered peer: {peer.ip}:{peer.port}")
            return peer

        # 广播自身存在
        self._broadcast_presence()

        # 等待一段时间再尝试
        time.sleep(self._config.broadcast_interval)

    logger.info("Auto-discovery timeout, no peer found")
    return None
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_discovery.py::test_discover_peer -v
```

预期: PASS (3 tests)

**Step 5: 提交**

```bash
git add clip_bridge/discovery.py tests/test_discovery.py
git commit -m "feat(discovery): add main discover() method

- Implement discover() with broadcast + listen loop
- Return first discovered peer immediately
- Return None on timeout
- Add tests for found, timeout, and multiple peers scenarios"
```

---

### Task 7: 主入口集成 - main.py 修改

**Files:**
- Modify: `clip_bridge/main.py`
- Create: `tests/test_main_discovery.py`

**Step 1: 编写集成测试**

创建 `tests/test_main_discovery.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from clip_bridge.main import ClipBridge
from clip_bridge.config import Config
from clip_bridge.discovery import PeerDevice


@pytest.fixture
def mock_config():
    return Config(
        local_port=9999,
        remote_host="192.168.1.100",  # 原配置
        remote_port=9998,
        auto_discover=True,
        discovery_timeout=1.0,
    )


def test_auto_discovery_updates_config(mock_config):
    """测试自动发现更新配置"""
    mock_peer = PeerDevice(ip="192.168.1.50", port=9998, last_seen=0)

    with patch('clip_bridge.main.UDPAutoDiscovery') as mock_discovery_class:
        mock_discovery = MagicMock()
        mock_discovery.discover.return_value = mock_peer
        mock_discovery_class.return_value = mock_discovery

        # 创建 ClipBridge（不启动实际组件）
        with patch('clip_bridge.main.ClipReceiver'), \
             patch('clip_bridge.main.ClipSender'), \
             patch('clip_bridge.main.ClipMonitor'):
            bridge = ClipBridge(mock_config)

            # 验证配置被更新
            assert mock_config.remote_host == "192.168.1.50"
            assert mock_config.remote_port == 9998


def test_auto_discovery_skipped_when_disabled(mock_config):
    """测试禁用自动发现时不调用发现"""
    mock_config.auto_discover = False

    with patch('clip_bridge.main.UDPAutoDiscovery') as mock_discovery_class:
        with patch('clip_bridge.main.ClipReceiver'), \
             patch('clip_bridge.main.ClipSender'), \
             patch('clip_bridge.main.ClipMonitor'):
            ClipBridge(mock_config)

            # 验证未创建发现实例
            mock_discovery_class.assert_not_called()

        # 验证配置保持原值
        assert mock_config.remote_host == "192.168.1.100"


def test_auto_discovery_fallback_on_failure(mock_config):
    """测试发现失败时回退到配置"""
    with patch('clip_bridge.main.UDPAutoDiscovery') as mock_discovery_class:
        mock_discovery = MagicMock()
        mock_discovery.discover.return_value = None  # 发现失败
        mock_discovery_class.return_value = mock_discovery

        with patch('clip_bridge.main.ClipReceiver'), \
             patch('clip_bridge.main.ClipSender'), \
             patch('clip_bridge.main.ClipMonitor'):
            ClipBridge(mock_config)

            # 验证配置保持原值（回退）
            assert mock_config.remote_host == "192.168.1.100"
            assert mock_config.remote_port == 9998
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_main_discovery.py -v
```

预期: FAIL - discovery not integrated

**Step 3: 在 main.py 中集成自动发现**

在 `clip_bridge/main.py` 中添加导入和修改 `ClipBridge.__init__`:

```python
# 在文件顶部添加导入
from clip_bridge.discovery import UDPAutoDiscovery, DiscoveryConfig, PeerDevice

# 在 ClipBridge.__init__ 中，创建组件之前添加自动发现
class ClipBridge:
    def __init__(self, config: Config):
        self._config = config
        self._logger = logging.getLogger(__name__)
        self._running = False

        # 自动发现对端
        if config.auto_discover:
            self._logger.info("Auto-discovery enabled")
            discovery_config = DiscoveryConfig(
                timeout=config.discovery_timeout,
                broadcast_port=config.broadcast_port,
            )
            discovery = UDPAutoDiscovery(discovery_config, config.local_port)
            peer = discovery.discover()
            if peer:
                self._config.remote_host = peer.ip
                self._config.remote_port = peer.port
                self._logger.info(
                    f"Auto-discovered peer: {peer.ip}:{peer.port}"
                )
            else:
                self._logger.info(
                    "No peer discovered, using configured values"
                )

        # 现有的组件初始化代码...
```

**Step 4: 运行测试确认通过**

```bash
pytest tests/test_main_discovery.py -v
pytest tests/ -v  # 确保所有测试通过
```

预期: PASS

**Step 5: 提交**

```bash
git add clip_bridge/main.py tests/test_main_discovery.py
git commit -m "feat(main): integrate auto-discovery into startup flow

- Add UDPAutoDiscovery integration in ClipBridge.__init__
- Update remote_host/port when peer is discovered
- Fallback to configured values if discovery fails
- Respect auto_discover config flag
- Add integration tests"
```

---

### Task 8: 配置文件模板更新

**Files:**
- Modify: `config.yaml`

**Step 1: 更新配置模板**

在 `config.yaml` 中添加新选项（保留注释说明）:

```yaml
# 本地监听端口（用于接收来自对端的连接）
local_port: 9999

# 对端设备地址（自动发现时会自动更新）
remote_host: 192.168.1.100
remote_port: 9998

# 自动发现设置
auto_discover: true          # 是否启用自动发现
discovery_timeout: 3.0       # 发现超时时间（秒）
broadcast_port: 9997         # 广播监听端口

# 剪贴板监听设置
poll_interval: 0.5           # 轮询间隔（秒）
sync_cooldown: 2.0           # 同步冷却时间（秒）

# 网络设置
max_size: 1048576            # 最大消息大小（1MB）
```

**Step 2: 验证配置加载**

```bash
python -c "
from clip_bridge.config import Config
config = Config.from_yaml('config.yaml')
print(f'auto_discover: {config.auto_discover}')
print(f'discovery_timeout: {config.discovery_timeout}')
print(f'broadcast_port: {config.broadcast_port}')
"
```

预期: 输出新配置的值

**Step 3: 提交**

```bash
git add config.yaml
git commit -m "docs(config): add auto-discovery options to template

- Add auto_discover, discovery_timeout, broadcast_port
- Update comments to explain new options"
```

---

### Task 9: 集成测试 - 端到端测试

**Files:**
- Create: `tests/integration/test_auto_discovery_integration.py`

**Step 1: 创建集成测试**

创建 `tests/integration/test_auto_discovery_integration.py`:

```python
"""自动发现集成测试

注意：这些测试需要两台机器或使用 localhost 模拟
"""

import pytest
import socket
import time
import threading
from clip_bridge.config import Config
from clip_bridge.discovery import UDPAutoDiscovery, DiscoveryConfig


def find_free_port():
    """查找可用端口"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_two_devices_discover_each_other():
    """测试两台设备互相发现"""
    # 使用不同端口模拟两台设备
    port1 = find_free_port()
    port2 = find_free_port()
    broadcast_port = find_free_port()

    config1 = DiscoveryConfig(timeout=2.0, broadcast_port=broadcast_port)
    config2 = DiscoveryConfig(timeout=2.0, broadcast_port=broadcast_port)

    discovered1 = []
    discovered2 = []

    def device1():
        discovery = UDPAutoDiscovery(config1, port1)
        peer = discovery.discover()
        if peer:
            discovered1.append(peer)

    def device2():
        time.sleep(0.1)  # 错开启动时间
        discovery = UDPAutoDiscovery(config2, port2)
        peer = discovery.discover()
        if peer:
            discovered2.append(peer)

    # 同时启动两台设备
    t1 = threading.Thread(target=device1)
    t2 = threading.Thread(target=device2)
    t1.start()
    t2.start()

    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    # 验证互相发现
    assert len(discovered1) > 0 or len(discovered2) > 0, "至少一台设备应发现对端"


@pytest.mark.skipif(True, reason="需要实际网络环境")
def test_real_network_discovery():
    """真实网络环境测试（手动执行）

    在两台真实机器上同时运行 clip-bridge，验证自动发现
    """
    pass
```

**Step 2: 运行集成测试**

```bash
pytest tests/integration/test_auto_discovery_integration.py -v
```

预期: PASS

**Step 3: 提交**

```bash
git add tests/integration/test_auto_discovery_integration.py
git commit -m "test(discovery): add integration tests

- Add two-device mutual discovery test
- Add placeholder for real network test
- Use dynamic port allocation to avoid conflicts"
```

---

### Task 10: 文档更新

**Files:**
- Modify: `README.md`

**Step 1: 更新 README**

在 `README.md` 中添加自动发现说明:

```markdown
## 自动发现

Clip Bridge 支持 UDP 广播自动发现功能。启用后，设备会在局域网内自动发现彼此，无需手动配置 IP 地址。

### 配置

在 `config.yaml` 中设置：

```yaml
auto_discover: true          # 启用自动发现
discovery_timeout: 3.0       # 发现超时时间（秒）
broadcast_port: 9997         # 广播监听端口
```

### 工作原理

1. 设备启动时，会广播自身的存在（携带监听端口）
2. 同时监听其他设备的广播消息
3. 收到广播后，自动更新对端配置并建立连接
4. 如果超时未发现设备，回退到配置文件中的值

### 防火墙设置

确保 UDP 端口 9997 允许广播流量。
```

**Step 2: 提交**

```bash
git add README.md
git commit -m "docs: add auto-discovery documentation to README

- Explain auto-discovery feature
- Add configuration example
- Document how it works
- Add firewall setup note"
```

---

### Task 11: 最终验证和清理

**Step 1: 运行所有测试**

```bash
pytest tests/ -v --cov=clip_bridge
```

预期: 所有测试通过，覆盖率报告良好

**Step 2: 代码风格检查**

```bash
ruff check clip_bridge/discovery.py clip_bridge/main.py clip_bridge/config.py
```

预期: 无错误

**Step 3: 手动测试（在两台机器上）**

```bash
# Mac 上
uv run python -m clip_bridge mac.yaml
# 观察日志输出，验证自动发现

# Ubuntu 上
uv run python -m clip_bridge ubuntu.yaml
# 观察日志输出，验证自动发现
```

**Step 4: 最终提交**

```bash
git add .
git commit -m "feat: complete auto-discovery feature implementation

- UDP broadcast auto-discovery for peer devices
- Automatic config update when peer found
- Fallback to manual config on timeout
- Comprehensive test coverage
- Documentation updates

All tests passing."
```

---

## 总结

此实现计划遵循 TDD 原则，每个功能都先编写测试再实现。主要变更：

1. **新增模块**: `clip_bridge/discovery.py` - UDP 广播发现
2. **修改模块**: `clip_bridge/config.py` - 添加发现配置
3. **修改模块**: `clip_bridge/main.py` - 集成自动发现流程
4. **测试**: 单元测试 + 集成测试
5. **文档**: 更新 README.md

关键设计决策：
- 使用 UDP 广播协议 `CLIP-HELLO:<port>`
- 固定端口 9998/9999 简化实现
- 自动连接第一台发现的设备
- 超时后回退到手动配置
