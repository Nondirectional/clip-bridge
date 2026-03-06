# Clip Bridge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个跨平台剪贴板共享工具，在 Mac 和 Ubuntu 之间通过 TCP Socket 双向同步纯文本

**Architecture:** 单进程多线程架构，主线程管理生命周期，三个工作线程分别处理剪贴板监听、发送、接收。通过线程安全队列通信，使用时间戳+哈希实现防循环机制。

**Tech Stack:** Python 3.12, pyperclip (剪贴板), pyyaml (配置), socket (TCP), threading (多线程), pytest (测试)

---

## Task 1: 项目基础设施

**Files:**
- Create: `pyproject.toml`
- Create: `clip_bridge/__init__.py`
- Create: `tests/__init__.py`

**Step 1: 创建 pyproject.toml**

```toml
[project]
name = "clip-bridge"
version = "0.1.0"
description = "Cross-platform clipboard sharing tool"
requires-python = ">=3.10"
dependencies = [
    "pyperclip>=1.8.2",
    "pyyaml>=6.0.1",
]

[project.scripts]
clip-bridge = "clip_bridge.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 2: 创建包初始化文件**

```bash
mkdir -p clip_bridge tests
touch clip_bridge/__init__.py tests/__init__.py
```

**Step 3: 安装依赖**

```bash
uv sync
```

**Step 4: 验证安装**

```bash
uv run python -c "import clip_bridge; print('OK')"
```

**Step 5: Commit**

```bash
git add pyproject.toml clip_bridge/__init__.py tests/__init__.py
git commit -m "feat: initialize project structure and dependencies"
```

---

## Task 2: 配置模块

**Files:**
- Create: `clip_bridge/config.py`
- Create: `tests/test_config.py`
- Create: `config.yaml.template`

**Step 1: 先写测试 - tests/test_config.py**

```python
import pytest
from pathlib import Path
import tempfile
from clip_bridge.config import Config, ConfigError

def test_config_load_valid_file():
    """测试加载有效配置文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
poll_interval: 0.5
sync_cooldown: 2.0
max_size: 1048576
""")
        f.flush()
        config = Config.load(f.name)
        assert config.local_port == 9999
        assert config.remote_host == "192.168.1.100"
        assert config.remote_port == 9998
        assert config.poll_interval == 0.5
        assert config.sync_cooldown == 2.0
        assert config.max_size == 1048576
        Path(f.name).unlink()

def test_config_missing_required_field():
    """测试缺少必需字段"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("local_port: 9999")
        f.flush()
        with pytest.raises(ConfigError, match="remote_host"):
            Config.load(f.name)
        Path(f.name).unlink()

def test_config_invalid_port():
    """测试无效端口"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("local_port: 99999\nremote_host: 192.168.1.1\nremote_port: 9998")
        f.flush()
        with pytest.raises(ConfigError, match="port"):
            Config.load(f.name)
        Path(f.name).unlink()

def test_config_defaults():
    """测试默认值"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("local_port: 9999\nremote_host: 192.168.1.1\nremote_port: 9998")
        f.flush()
        config = Config.load(f.name)
        assert config.poll_interval == 0.5
        assert config.sync_cooldown == 2.0
        assert config.max_size == 1048576
        Path(f.name).unlink()
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: clip_bridge.config`

**Step 3: 实现配置模块 - clip_bridge/config.py**

```python
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class Config:
    """剪贴板桥接配置"""
    local_port: int
    remote_host: str
    remote_port: int
    poll_interval: float = 0.5
    sync_cooldown: float = 2.0
    max_size: int = 1048576  # 1MB

    @classmethod
    def load(cls, path: str) -> "Config":
        """从 YAML 文件加载配置"""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        # 验证必需字段
        required = ['local_port', 'remote_host', 'remote_port']
        for field in required:
            if field not in data:
                raise ConfigError(f"Missing required field: {field}")

        # 验证端口范围
        for port_field in ['local_port', 'remote_port']:
            port = data[port_field]
            if not 1 <= port <= 65535:
                raise ConfigError(f"Invalid {port_field}: {port} (must be 1-65535)")

        # 验证非空字符串
        if not data['remote_host'].strip():
            raise ConfigError("remote_host cannot be empty")

        return cls(
            local_port=data['local_port'],
            remote_host=data['remote_host'],
            remote_port=data['remote_port'],
            poll_interval=data.get('poll_interval', 0.5),
            sync_cooldown=data.get('sync_cooldown', 2.0),
            max_size=data.get('max_size', 1048576),
        )

    def save(self, path: str) -> None:
        """保存配置到 YAML 文件"""
        with open(path, 'w') as f:
            yaml.dump({
                'local_port': self.local_port,
                'remote_host': self.remote_host,
                'remote_port': self.remote_port,
                'poll_interval': self.poll_interval,
                'sync_cooldown': self.sync_cooldown,
                'max_size': self.max_size,
            }, f, default_flow_style=False)


class ConfigError(Exception):
    """配置错误"""
    pass
```

**Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_config.py -v
```

Expected: All PASS

**Step 5: 创建配置模板**

```bash
cat > config.yaml.template << 'EOF'
# Clip Bridge 配置模板
# 复制此文件为 mac.yaml 或 ubuntu.yaml 并修改

# 本地监听端口 (Mac 建议 9999, Ubuntu 建议 9998)
local_port: 9999

# 对端 IP 地址
remote_host: 192.168.1.100

# 对端端口 (Mac 的对端是 Ubuntu 的 9998, 反之亦然)
remote_port: 9998

# 剪贴板轮询间隔（秒）
poll_interval: 0.5

# 防循环冷却时间（秒）- 接收数据后多久不发送相同内容
sync_cooldown: 2.0

# 最大消息大小（字节）
max_size: 1048576
EOF
```

**Step 6: Commit**

```bash
git add clip_bridge/config.py tests/test_config.py config.yaml.template
git commit -m "feat: implement config module with validation"
```

---

## Task 3: 协议模块

**Files:**
- Create: `clip_bridge/protocol.py`
- Create: `tests/test_protocol.py`

**Step 1: 先写测试 - tests/test_protocol.py**

```python
import pytest
from clip_bridge.protocol import encode_message, decode_message, ProtocolError

def test_encode_simple_message():
    """测试编码简单消息"""
    data = b"Hello, World!"
    result = encode_message(data)
    assert result.startswith(b"CLIP")
    assert result.endswith(data)

def test_encode_empty_message():
    """测试编码空消息"""
    result = encode_message(b"")
    assert result == b"CLIP0:"

def test_encode_unicode():
    """测试编码 Unicode"""
    data = "你好，世界！".encode('utf-8')
    result = encode_message(data)
    assert result.startswith(b"CLIP")
    decoded = decode_message(result)
    assert decoded == data

def test_decode_valid_message():
    """测试解码有效消息"""
    msg = b"CLIP5:Hello"
    result = decode_message(msg)
    assert result == b"Hello"

def test_decode_valid_message_with_newlines():
    """测试解码包含换行的消息"""
    msg = b"CLIP12:Hello\nWorld"
    result = decode_message(msg)
    assert result == b"Hello\nWorld"

def test_decode_invalid_prefix():
    """测试无效前缀"""
    with pytest.raises(ProtocolError, match="Invalid prefix"):
        decode_message(b"WRONG5:Hello")

def test_decode_missing_colon():
    """测试缺少冒号"""
    with pytest.raises(ProtocolError, match="Missing colon"):
        decode_message(b"CLIP5Hello")

def test_decode_invalid_length():
    """测试无效长度"""
    with pytest.raises(ProtocolError, match="Invalid length"):
        decode_message(b"CLIPabc:Hello")

def test_decode_length_mismatch():
    """测试长度不匹配"""
    with pytest.raises(ProtocolError, match="Length mismatch"):
        decode_message(b"CLIP10:Hello")

def test_decode_empty_message():
    """测试解码空消息"""
    result = decode_message(b"CLIP0:")
    assert result == b""
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_protocol.py -v
```

Expected: `ModuleNotFoundError: clip_bridge.protocol`

**Step 3: 实现协议模块 - clip_bridge/protocol.py**

```python
import re

# 消息前缀和格式
PREFIX = b"CLIP"
SEPARATOR = b":"
# 正则匹配前缀和长度: CLIP<number>:
PATTERN = re.compile(r"^CLIP(\d+):")

# 最大消息大小
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB


def encode_message(data: bytes) -> bytes:
    """
    编码消息为 CLIP 协议格式

    格式: CLIP<length>:<content>

    Args:
        data: 要编码的字节数据

    Returns:
        编码后的消息
    """
    if len(data) > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Message too large: {len(data)} bytes (max {MAX_MESSAGE_SIZE})")

    length = len(data)
    return PREFIX + str(length).encode() + SEPARATOR + data


def decode_message(data: bytes) -> bytes:
    """
    解码 CLIP 协议格式消息

    Args:
        data: 编码的消息

    Returns:
        解码后的原始数据

    Raises:
        ProtocolError: 消息格式无效
    """
    if not data.startswith(PREFIX):
        raise ProtocolError("Invalid prefix: expected CLIP")

    # 查找分隔符位置
    colon_pos = data.find(SEPARATOR, len(PREFIX))
    if colon_pos == -1:
        raise ProtocolError("Missing colon separator")

    # 提取长度字符串
    length_str = data[len(PREFIX):colon_pos].decode()
    if not length_str.isdigit():
        raise ProtocolError(f"Invalid length: {length_str}")

    # 解析长度
    expected_length = int(length_str)
    if expected_length > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Message too large: {expected_length} bytes")

    # 提取内容
    content = data[colon_pos + 1:]
    actual_length = len(content)

    if actual_length != expected_length:
        raise ProtocolError(
            f"Length mismatch: expected {expected_length}, got {actual_length}"
        )

    return content


class ProtocolError(Exception):
    """协议错误"""
    pass
```

**Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_protocol.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add clip_bridge/protocol.py tests/test_protocol.py
git commit -m "feat: implement CLIP protocol message encoding/decoding"
```

---

## Task 4: 防循环机制

**Files:**
- Create: `clip_bridge/cooldown.py`
- Create: `tests/test_cooldown.py`

**Step 1: 先写测试 - tests/test_cooldown.py**

```python
import time
import pytest
from clip_bridge.cooldown import CooldownManager

def test_is_not_cooldown_initially():
    """测试初始状态不在冷却"""
    manager = CooldownManager(cooldown_seconds=1.0)
    assert not manager.is_cooldown(b"test content")

def test_add_cooldown():
    """测试添加冷却"""
    manager = CooldownManager(cooldown_seconds=1.0)
    manager.add_cooldown(b"test content")
    assert manager.is_cooldown(b"test content")

def test_cooldown_expires():
    """测试冷却过期"""
    manager = CooldownManager(cooldown_seconds=0.5)
    manager.add_cooldown(b"test content")
    assert manager.is_cooldown(b"test content")
    time.sleep(0.6)
    assert not manager.is_cooldown(b"test content")

def test_different_content_separate_cooldown():
    """测试不同内容独立冷却"""
    manager = CooldownManager(cooldown_seconds=1.0)
    manager.add_cooldown(b"content A")
    assert not manager.is_cooldown(b"content B")

def test_cleanup_expired():
    """测试清理过期条目"""
    manager = CooldownManager(cooldown_seconds=0.5)
    manager.add_cooldown(b"test1")
    time.sleep(0.6)
    manager.add_cooldown(b"test2")
    manager.cleanup()
    # 过期条目被清理
    assert not manager.is_cooldown(b"test1")
    assert manager.is_cooldown(b"test2")

def test_max_entries():
    """测试最大条目限制"""
    manager = CooldownManager(cooldown_seconds=10.0, max_entries=3)
    manager.add_cooldown(b"test1")
    manager.add_cooldown(b"test2")
    manager.add_cooldown(b"test3")
    manager.add_cooldown(b"test4")  # 应该淘汰 test1
    assert not manager.is_cooldown(b"test1")
    assert manager.is_cooldown(b"test2")
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_cooldown.py -v
```

Expected: `ModuleNotFoundError: clip_bridge.cooldown`

**Step 3: 实现冷却管理器 - clip_bridge/cooldown.py**

```python
import time
import hashlib
from collections import OrderedDict
from typing import Dict


class CooldownManager:
    """
    管理防循环冷却状态

    使用内容哈希跟踪最近接收的内容，在冷却时间内
    相同内容不会再次被发送。
    """

    def __init__(self, cooldown_seconds: float = 2.0, max_entries: int = 1000):
        """
        初始化冷却管理器

        Args:
            cooldown_seconds: 冷却时间（秒）
            max_entries: 最大条目数，防止内存无限增长
        """
        self._cooldown_seconds = cooldown_seconds
        self._max_entries = max_entries
        self._entries: OrderedDict[str, float] = OrderedDict()

    def _hash(self, content: bytes) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content).hexdigest()

    def add_cooldown(self, content: bytes) -> None:
        """
        添加内容到冷却列表

        Args:
            content: 接收到的内容
        """
        content_hash = self._hash(content)
        now = time.time()

        # 达到最大条目时，删除最旧的
        if len(self._entries) >= self._max_entries:
            self._entries.popitem(last=False)

        # 更新或添加条目（移到末尾表示最新）
        if content_hash in self._entries:
            del self._entries[content_hash]
        self._entries[content_hash] = now

    def is_cooldown(self, content: bytes) -> bool:
        """
        检查内容是否在冷却中

        Args:
            content: 要检查的内容

        Returns:
            True 如果在冷却中，False 否则
        """
        content_hash = self._hash(content)
        if content_hash not in self._entries:
            return False

        timestamp = self._entries[content_hash]
        now = time.time()

        # 检查是否过期
        if now - timestamp > self._cooldown_seconds:
            del self._entries[content_hash]
            return False

        return True

    def cleanup(self) -> None:
        """清理过期的条目"""
        now = time.time()
        expired = [
            h for h, t in self._entries.items()
            if now - t > self._cooldown_seconds
        ]
        for h in expired:
            del self._entries[h]
```

**Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_cooldown.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add clip_bridge/cooldown.py tests/test_cooldown.py
git commit -m "feat: implement cooldown manager for loop prevention"
```

---

## Task 5: 发送器 (Sender)

**Files:**
- Create: `clip_bridge/sender.py`
- Create: `tests/test_sender.py`

**Step 1: 先写测试 - tests/test_sender.py**

```python
import pytest
import socket
import threading
import time
from clip_bridge.sender import Sender
from clip_bridge.protocol import decode_message

def test_sender_connects_and_sends(free_port):
    """测试发送器连接并发送数据"""
    received = []

    def mock_server():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', free_port))
        server.listen(1)
        conn, _ = server.accept()
        data = conn.recv(1024)
        received.append(data)
        conn.close()
        server.close()

    # 启动模拟服务器
    server_thread = threading.Thread(target=mock_server, daemon=True)
    server_thread.start()

    # 创建发送器并发送
    sender = Sender('127.0.0.1', free_port)
    sender.send(b"Hello, World!")
    sender.stop()

    server_thread.join(timeout=2)

    assert len(received) == 1
    assert decode_message(received[0]) == b"Hello, World!"

def test_sender_reconnects_on_failure():
    """测试发送器自动重连"""
    sender = Sender('127.0.0.1', 19999, reconnect_delay=0.1)
    # 先发送失败（没有服务器）
    sender.send(b"test")
    sender.stop()
    # 应该不崩溃

@pytest.fixture
def free_port():
    """获取一个空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        return s.getsockname()[1]
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_sender.py -v
```

Expected: `ModuleNotFoundError: clip_bridge.sender`

**Step 3: 实现发送器 - clip_bridge/sender.py**

```python
import socket
import threading
import queue
import logging
import time

logger = logging.getLogger(__name__)


class Sender:
    """
    TCP 发送器 - 连接到对端并发送剪贴板数据

    在独立线程中运行，维护发送队列和自动重连。
    """

    def __init__(self, host: str, port: int, reconnect_delay: float = 1.0):
        """
        初始化发送器

        Args:
            host: 对端主机
            port: 对端端口
            reconnect_delay: 重连延迟（秒）
        """
        self._host = host
        self._port = port
        self._reconnect_delay = reconnect_delay
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """启动发送器线程"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"[Sender] Started, connecting to {self._host}:{self._port}")

    def stop(self) -> None:
        """停止发送器"""
        if not self._running:
            return

        self._running = False
        self._queue.put(None)  # 发送停止信号
        if self._thread:
            self._thread.join(timeout=2)

        with self._lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

        logger.info("[Sender] Stopped")

    def send(self, data: bytes) -> None:
        """
        发送数据（异步）

        Args:
            data: 要发送的数据
        """
        if self._running:
            self._queue.put(data)

    def _connect(self) -> bool:
        """尝试连接到对端"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self._host, self._port))
            with self._lock:
                self._socket = sock
            logger.info(f"[Sender] Connected to {self._host}:{self._port}")
            return True
        except OSError as e:
            logger.warning(f"[Sender] Connection failed: {e}")
            return False

    def _run(self) -> None:
        """发送器主循环"""
        while self._running:
            # 如果没有连接，尝试连接
            if not self._socket:
                if not self._connect():
                    time.sleep(self._reconnect_delay)
                    continue

            # 等待数据，带超时以便检查运行状态
            try:
                data = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # 停止信号
            if data is None:
                break

            # 发送数据
            if not self._send_data(data):
                # 发送失败，关闭连接等待重连
                with self._lock:
                    if self._socket:
                        try:
                            self._socket.close()
                        except Exception:
                            pass
                        self._socket = None

    def _send_data(self, data: bytes) -> bool:
        """发送数据到已连接的 socket"""
        try:
            with self._lock:
                if not self._socket:
                    return False
                self._socket.sendall(data)
            return True
        except OSError as e:
            logger.warning(f"[Sender] Send failed: {e}")
            return False
```

**Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_sender.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add clip_bridge/sender.py tests/test_sender.py
git commit -m "feat: implement TCP sender with auto-reconnect"
```

---

## Task 6: 接收器 (Receiver)

**Files:**
- Create: `clip_bridge/receiver.py`
- Create: `tests/test_receiver.py`

**Step 1: 先写测试 - tests/test_receiver.py**

```python
import pytest
import socket
import threading
import time
from clip_bridge.receiver import Receiver
from clip_bridge.protocol import encode_message

def test_receiver_receives_and_callbacks(free_port):
    """测试接收器接收数据并回调"""
    received = []

    def on_receive(data: bytes):
        received.append(data)

    receiver = Receiver('0.0.0.0', free_port, on_receive)
    receiver.start()

    # 发送测试数据
    time.sleep(0.1)  # 等待服务器启动
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('127.0.0.1', free_port))
    client.send(encode_message(b"Test message"))
    client.close()

    time.sleep(0.2)  # 等待处理
    receiver.stop()

    assert len(received) == 1
    assert received[0] == b"Test message"

def test_receiver_rejects_multiple_connections(free_port):
    """测试接收器拒绝额外连接"""
    receiver = Receiver('0.0.0.0', free_port, lambda x: None)
    receiver.start()

    time.sleep(0.1)

    # 第一个连接
    client1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client1.connect(('127.0.0.1', free_port))

    # 第二个连接应该被拒绝
    client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client2.connect(('127.0.0.1', free_port))
        # 如果连接成功，服务器没有正确拒绝
        assert False, "Second connection should be rejected"
    except (ConnectionRefusedError, ConnectionResetError):
        pass  # 预期的行为

    client1.close()
    client2.close()
    receiver.stop()

@pytest.fixture
def free_port():
    """获取一个空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        return s.getsockname()[1]
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_receiver.py -v
```

Expected: `ModuleNotFoundError: clip_bridge.receiver`

**Step 3: 实现接收器 - clip_bridge/receiver.py**

```python
import socket
import threading
import logging
from typing import Callable

from clip_bridge.protocol import decode_message, ProtocolError

logger = logging.getLogger(__name__)


class Receiver:
    """
    TCP 接收器 - 监听端口接收剪贴板数据

    单一连接模式：只接受一个客户端连接，拒绝额外连接。
    """

    def __init__(
        self,
        host: str,
        port: int,
        on_receive: Callable[[bytes], None]
    ):
        """
        初始化接收器

        Args:
            host: 监听地址
            port: 监听端口
            on_receive: 接收数据回调
        """
        self._host = host
        self._port = port
        self._on_receive = on_receive
        self._server_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._connected = False

    def start(self) -> None:
        """启动接收器"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"[Receiver] Started on {self._host}:{self._port}")

    def stop(self) -> None:
        """停止接收器"""
        if not self._running:
            return

        self._running = False

        # 关闭服务器 socket 以解除 accept 阻塞
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass

        if self._thread:
            self._thread.join(timeout=2)

        logger.info("[Receiver] Stopped")

    def _run(self) -> None:
        """接收器主循环"""
        try:
            self._server_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM
            )
            self._server_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            self._server_socket.bind((self._host, self._port))
            self._server_socket.listen(1)
            self._server_socket.settimeout(0.5)  # 用于检查 running 状态

            logger.info(f"[Receiver] Listening on {self._host}:{self._port}")

            while self._running:
                # 等待连接
                try:
                    client_socket, addr = self._server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    # socket 已关闭
                    break

                # 如果已有连接，拒绝新连接
                if self._connected:
                    logger.warning(
                        f"[Receiver] Rejecting additional connection from {addr}"
                    )
                    try:
                        client_socket.close()
                    except Exception:
                        pass
                    continue

                # 处理连接
                self._connected = True
                logger.info(f"[Receiver] Connected to {addr}")
                self._handle_client(client_socket)
                self._connected = False

        except Exception as e:
            logger.error(f"[Receiver] Error: {e}")
        finally:
            if self._server_socket:
                try:
                    self._server_socket.close()
                except Exception:
                    pass

    def _handle_client(self, client_socket: socket.SocketType) -> None:
        """处理客户端连接"""
        try:
            buffer = b""

            while self._running:
                data = client_socket.recv(4096)
                if not data:
                    break

                buffer += data

                # 尝试解析消息
                while True:
                    try:
                        # 检查是否有完整消息
                        if not buffer.startswith(b"CLIP"):
                            logger.warning("[Receiver] Invalid message format")
                            buffer = b""
                            break

                        # 查找分隔符
                        colon_pos = buffer.find(b":", 4)
                        if colon_pos == -1:
                            # 数据不完整，等待更多数据
                            break

                        # 解析长度
                        length_str = buffer[4:colon_pos].decode()
                        if not length_str.isdigit():
                            logger.warning("[Receiver] Invalid length format")
                            buffer = b""
                            break

                        expected_length = int(length_str)
                        content_start = colon_pos + 1
                        content_end = content_start + expected_length

                        # 检查是否有完整内容
                        if len(buffer) < content_end:
                            # 数据不完整，等待更多数据
                            break

                        # 提取并处理消息
                        content = buffer[content_start:content_end]
                        buffer = buffer[content_end:]

                        self._on_receive(content)
                        logger.info(f"[Receiver] Received {len(content)} bytes")

                    except Exception as e:
                        logger.error(f"[Receiver] Parse error: {e}")
                        buffer = b""
                        break

        except Exception as e:
            logger.error(f"[Receiver] Client error: {e}")
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
            logger.info("[Receiver] Client disconnected")
```

**Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_receiver.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add clip_bridge/receiver.py tests/test_receiver.py
git commit -m "feat: implement TCP receiver with single connection mode"
```

---

## Task 7: 剪贴板监听器 (Monitor)

**Files:**
- Create: `clip_bridge/monitor.py`
- Create: `tests/test_monitor.py`

**Step 1: 先写测试 - tests/test_monitor.py**

```python
import pytest
import time
import pyperclip
from clip_bridge.monitor import Monitor

def test_monitor_detects_changes():
    """测试监听器检测剪贴板变化"""
    events = []

    def on_change(content: str):
        events.append(content)

    monitor = Monitor(interval=0.1, on_change=on_change)
    monitor.start()

    # 初始剪贴板
    pyperclip.copy("initial")
    time.sleep(0.2)

    # 修改剪贴板
    pyperclip.copy("changed")
    time.sleep(0.2)

    monitor.stop()

    # 应该检测到变化
    assert any("changed" in e for e in events)

def test_monitor_ignores_duplicates():
    """测试监听器忽略重复内容"""
    events = []

    def on_change(content: str):
        events.append(content)

    monitor = Monitor(interval=0.1, on_change=on_change)
    monitor.start()

    pyperclip.copy("test")
    time.sleep(0.2)
    # 再次复制相同内容
    pyperclip.copy("test")
    time.sleep(0.2)

    monitor.stop()

    # 应该只触发一次
    assert events.count("test") <= 1
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_monitor.py -v
```

Expected: `ModuleNotFoundError: clip_bridge.monitor`

**Step 3: 实现监听器 - clip_bridge/monitor.py**

```python
import threading
import logging
import time
from typing import Callable

import pyperclip

logger = logging.getLogger(__name__)


class Monitor:
    """
    剪贴板监听器 - 轮询检测剪贴板变化

    使用轮询方式检测剪贴板内容变化，兼容性最好。
    """

    def __init__(self, interval: float = 0.5, on_change: Callable[[str], None] | None = None):
        """
        初始化监听器

        Args:
            interval: 轮询间隔（秒）
            on_change: 内容变化回调
        """
        self._interval = interval
        self._on_change = on_change
        self._last_content = ""
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """启动监听器"""
        if self._running:
            return

        self._running = True
        # 初始化当前内容
        try:
            self._last_content = pyperclip.paste()
        except Exception as e:
            logger.warning(f"[Monitor] Failed to read initial clipboard: {e}")
            self._last_content = ""

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"[Monitor] Started (interval: {self._interval}s)")

    def stop(self) -> None:
        """停止监听器"""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

        logger.info("[Monitor] Stopped")

    def _run(self) -> None:
        """监听器主循环"""
        while self._running:
            try:
                content = pyperclip.paste()

                if content != self._last_content:
                    with self._lock:
                        self._last_content = content

                    logger.info(f"[Monitor] Clipboard changed ({len(content)} chars)")

                    if self._on_change:
                        self._on_change(content)

            except Exception as e:
                logger.error(f"[Monitor] Error reading clipboard: {e}")

            time.sleep(self._interval)

    def update_last_content(self, content: str) -> None:
        """
        更新最后的内容（用于防止循环）

        Args:
            content: 新的最后内容
        """
        with self._lock:
            self._last_content = content
```

**Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_monitor.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add clip_bridge/monitor.py tests/test_monitor.py
git commit -m "feat: implement clipboard monitor with polling"
```

---

## Task 8: 交互式配置

**Files:**
- Modify: `clip_bridge/config.py` (添加默认配置路径函数)
- Create: `clip_bridge/interactive.py`
- Create: `tests/test_interactive.py`

**Step 1: 先写测试 - tests/test_interactive.py**

```python
import pytest
import tempfile
from pathlib import Path
from clip_bridge.interactive import InteractiveSetup, DEFAULT_PORTS

def test_interactive_creates_config():
    """测试交互式配置创建配置文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        setup = InteractiveSetup(tmpdir)

        # 模拟用户输入
        setup.set_answers({
            'machine_name': 'mac',
            'remote_ip': '192.168.1.100',
        })

        config_path = setup.run()

        assert config_path == str(Path(tmpdir) / 'mac.yaml')
        assert Path(config_path).exists()

        # 验证配置内容
        from clip_bridge.config import Config
        config = Config.load(config_path)
        assert config.remote_host == '192.168.1.100'

def test_mac_vs_ubuntu_ports():
    """测试 Mac 和 Ubuntu 端口分配"""
    assert DEFAULT_PORTS['mac'] == (9999, 9998)
    assert DEFAULT_PORTS['ubuntu'] == (9998, 9999)
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_interactive.py -v
```

Expected: `ModuleNotFoundError: clip_bridge.interactive`

**Step 3: 实现交互式配置 - clip_bridge/interactive.py**

```python
import logging
from pathlib import Path
from typing import Literal

from clip_bridge.config import Config

logger = logging.getLogger(__name__)

MachineType = Literal['mac', 'ubuntu']

# 默认端口分配: (local_port, remote_port)
DEFAULT_PORTS = {
    'mac': (9999, 9998),    # Mac 本地 9999，对端 Ubuntu 9998
    'ubuntu': (9998, 9999), # Ubuntu 本地 9998，对端 Mac 9999
}


class InteractiveSetup:
    """
    交互式配置向导

    首次运行时引导用户创建配置文件。
    """

    def __init__(self, config_dir: str = "."):
        """
        初始化交互式设置

        Args:
            config_dir: 配置文件目录
        """
        self._config_dir = Path(config_dir)
        self._answers: dict | None = None

    def set_answers(self, answers: dict) -> None:
        """设置预定义答案（用于测试）"""
        self._answers = answers

    def _ask(self, question: str, default: str | None = None) -> str:
        """
        向用户提问

        Args:
            question: 问题文本
            default: 默认值

        Returns:
            用户答案
        """
        if self._answers is not None:
            # 测试模式：使用预定义答案
            return self._answers.get(question, default or "")

        prompt = question
        if default:
            prompt += f" [{default}]"
        prompt += ": "

        answer = input(prompt).strip()
        return answer if answer else (default or "")

    def run(self) -> str:
        """
        运行交互式配置

        Returns:
            创建的配置文件路径
        """
        print("\n=== Clip Bridge 配置向导 ===\n")

        # 选择机器类型
        print("请选择本机类型:")
        print("  1. Mac")
        print("  2. Ubuntu/Linux")

        choice = self._ask("选择 (1/2)", "1")
        machine_type: MachineType = 'mac' if choice == '1' else 'ubuntu'

        # 获取对端 IP
        remote_ip = self._ask(
            "请输入对端电脑的 IP 地址",
            "192.168.1.100" if machine_type == 'mac' else "192.168.1.101"
        )

        # 确认配置
        local_port, remote_port = DEFAULT_PORTS[machine_type]

        print(f"\n配置摘要:")
        print(f"  本机类型: {machine_type}")
        print(f"  本地端口: {local_port}")
        print(f"  对端 IP: {remote_ip}")
        print(f"  对端端口: {remote_port}")

        confirm = self._ask("\n确认创建配置? (y/n)", "y")
        if confirm.lower() != 'y':
            print("已取消")
            return ""

        # 创建配置
        config = Config(
            local_port=local_port,
            remote_host=remote_ip,
            remote_port=remote_port,
        )

        # 保存配置文件
        config_path = self._config_dir / f"{machine_type}.yaml"
        config.save(str(config_path))

        print(f"\n配置已保存到: {config_path}")
        print(f"\n启动命令:")
        print(f"  uv run python -m clip_bridge {config_path}")
        print()

        return str(config_path)


def find_config(config_dir: str = ".") -> str | None:
    """
    查找配置文件

    Args:
        config_dir: 配置文件目录

    Returns:
        配置文件路径，如果没找到返回 None
    """
    config_path = Path(config_dir)
    yaml_files = list(config_path.glob("*.yaml"))

    # 过滤掉模板文件
    yaml_files = [f for f in yaml_files if 'template' not in f.name]

    if not yaml_files:
        return None

    if len(yaml_files) == 1:
        return str(yaml_files[0])

    # 多个文件时，让用户选择
    print("\n找到多个配置文件:")
    for i, f in enumerate(yaml_files, 1):
        print(f"  {i}. {f.name}")

    choice = input("选择配置文件 (1-{len(yaml_files)}) [1]: ").strip()
    if not choice:
        choice = "1"

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(yaml_files):
            return str(yaml_files[idx])
    except ValueError:
        pass

    return str(yaml_files[0])
```

**Step 4: 更新 config.py 添加 save 方法（如果还没有）**

检查 config.py 是否有 save 方法，已在 Task 2 实现。

**Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_interactive.py -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add clip_bridge/interactive.py tests/test_interactive.py
git commit -m "feat: implement interactive configuration wizard"
```

---

## Task 9: 主程序 (Main)

**Files:**
- Create: `clip_bridge/main.py`

**Step 1: 实现主程序 - clip_bridge/main.py**

```python
#!/usr/bin/env python3
"""
Clip Bridge - 跨平台剪贴板共享工具
"""

import logging
import signal
import sys
from pathlib import Path

from clip_bridge.config import Config, ConfigError
from clip_bridge.interactive import find_config, InteractiveSetup
from clip_bridge.monitor import Monitor
from clip_bridge.sender import Sender
from clip_bridge.receiver import Receiver
from clip_bridge.cooldown import CooldownManager
from clip_bridge.protocol import encode_message

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)


class ClipBridge:
    """剪贴板桥接主程序"""

    def __init__(self, config_path: str):
        """
        初始化

        Args:
            config_path: 配置文件路径
        """
        self._config = Config.load(config_path)
        self._cooldown = CooldownManager(
            cooldown_seconds=self._config.sync_cooldown
        )
        self._monitor: Monitor | None = None
        self._sender: Sender | None = None
        self._receiver: Receiver | None = None
        self._running = False

    def start(self) -> None:
        """启动所有组件"""
        self._running = True

        # 启动接收器
        self._receiver = Receiver(
            '0.0.0.0',
            self._config.local_port,
            self._on_receive
        )
        self._receiver.start()

        # 启动发送器
        self._sender = Sender(
            self._config.remote_host,
            self._config.remote_port
        )
        self._sender.start()

        # 启动监听器
        self._monitor = Monitor(
            interval=self._config.poll_interval,
            on_change=self._on_clipboard_change
        )
        self._monitor.start()

        logger.info("[ClipBridge] All components started")
        logger.info(f"[ClipBridge] Local port: {self._config.local_port}")
        logger.info(f"[ClipBridge] Remote: {self._config.remote_host}:{self._config.remote_port}")
        logger.info("[ClipBridge] Press Ctrl+C to stop")

    def stop(self) -> None:
        """停止所有组件"""
        if not self._running:
            return

        self._running = False
        logger.info("[ClipBridge] Shutting down...")

        if self._monitor:
            self._monitor.stop()
        if self._sender:
            self._sender.stop()
        if self._receiver:
            self._receiver.stop()

        logger.info("[ClipBridge] Stopped")

    def _on_clipboard_change(self, content: str) -> None:
        """剪贴板变化回调"""
        data = content.encode('utf-8')

        # 检查冷却状态
        if self._cooldown.is_cooldown(data):
            logger.debug("[ClipBridge] Content in cooldown, skipping send")
            return

        # 发送
        if self._sender:
            msg = encode_message(data)
            self._sender.send(msg)
            logger.debug(f"[ClipBridge] Sent {len(data)} bytes")

    def _on_receive(self, data: bytes) -> None:
        """接收数据回调"""
        import pyperclip

        try:
            # 添加到冷却
            self._cooldown.add_cooldown(data)

            # 更新剪贴板
            content = data.decode('utf-8')
            pyperclip.copy(content)

            # 更新监听器状态，防止循环
            if self._monitor:
                self._monitor.update_last_content(content)

            logger.info(f"[ClipBridge] Clipboard updated ({len(content)} chars)")
        except Exception as e:
            logger.error(f"[ClipBridge] Failed to update clipboard: {e}")


def main() -> int:
    """入口点"""
    import argparse

    parser = argparse.ArgumentParser(description="Clip Bridge - 跨平台剪贴板共享")
    parser.add_argument(
        'config',
        nargs='?',
        help='配置文件路径'
    )
    parser.add_argument(
        '--setup',
        action='store_true',
        help='运行交互式配置'
    )

    args = parser.parse_args()

    # 交互式配置模式
    if args.setup:
        setup = InteractiveSetup()
        config_path = setup.run()
        return 0 if config_path else 1

    # 确定配置文件
    config_path = args.config

    if not config_path:
        config_path = find_config()

    if not config_path:
        logger.info("未找到配置文件，启动交互式配置...")
        setup = InteractiveSetup()
        config_path = setup.run()
        if not config_path:
            return 1

    # 验证配置文件存在
    if not Path(config_path).exists():
        logger.error(f"配置文件不存在: {config_path}")
        return 1

    try:
        # 加载配置
        config = Config.load(config_path)
        logger.info(f"配置已加载: {config_path}")
    except ConfigError as e:
        logger.error(f"配置错误: {e}")
        return 1

    # 创建并启动 ClipBridge
    bridge = ClipBridge(config_path)

    # 信号处理
    def signal_handler(signum, frame):
        bridge.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bridge.start()
        # 保持运行
        import time
        while bridge._running:
            time.sleep(0.5)
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

**Step 2: 测试主程序可以导入**

```bash
uv run python -c "from clip_bridge.main import ClipBridge; print('OK')"
```

**Step 3: 测试交互式配置触发**

```bash
uv run python -m clip_bridge --help
```

Expected: 显示帮助信息

**Step 4: Commit**

```bash
git add clip_bridge/main.py
git commit -m "feat: implement main entry point and orchestration"
```

---

## Task 10: 集成测试

**Files:**
- Create: `tests/test_integration.py`

**Step 1: 编写集成测试 - tests/test_integration.py**

```python
import pytest
import tempfile
import threading
import time
from pathlib import Path

from clip_bridge.main import ClipBridge
from clip_bridge.config import Config
from clip_bridge.protocol import encode_message
import socket
import pyperclip


def test_end_to_end_sync():
    """测试端到端同步"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建两个配置
        config1_path = Path(tmpdir) / "config1.yaml"
        config2_path = Path(tmpdir) / "config2.yaml"

        config1 = Config(
            local_port=19998,
            remote_host='127.0.0.1',
            remote_port=19999,
            poll_interval=0.1,
            sync_cooldown=1.0,
        )
        config1.save(str(config1_path))

        config2 = Config(
            local_port=19999,
            remote_host='127.0.0.1',
            remote_port=19998,
            poll_interval=0.1,
            sync_cooldown=1.0,
        )
        config2.save(str(config2_path))

        # 启动两个实例
        bridge1 = ClipBridge(str(config1_path))
        bridge2 = ClipBridge(str(config2_path))

        # 在单独线程中启动
        def run_bridge(bridge):
            import time
            bridge.start()
            while bridge._running:
                time.sleep(0.1)

        thread1 = threading.Thread(target=run_bridge, args=(bridge1,), daemon=True)
        thread2 = threading.Thread(target=run_bridge, args=(bridge2,), daemon=True)

        thread1.start()
        thread2.start()

        # 等待连接建立
        time.sleep(1)

        # 测试同步
        pyperclip.copy("Test from bridge1")
        time.sleep(1)

        # 获取 bridge2 的剪贴板
        content = pyperclip.paste()
        assert content == "Test from bridge1"

        # 清理
        bridge1.stop()
        bridge2.stop()

        time.sleep(0.5)
```

**Step 2: 运行集成测试**

```bash
uv run pytest tests/test_integration.py -v -s
```

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test"
```

---

## Task 11: 文档和清理

**Files:**
- Create: `README.md`
- Create: `.gitignore`

**Step 1: 创建 README.md**

```bash
cat > /data/projects/clip-bridge/README.md << 'EOF'
# Clip Bridge

跨平台剪贴板共享工具，用于在局域网内多台电脑之间同步纯文本剪贴板内容。

## 功能

- Mac 和 Ubuntu/Linux 之间双向同步剪贴板
- TCP Socket 双向通信
- 自动重连机制
- 防循环同步
- 交互式配置向导

## 安装

```bash
# 克隆仓库
git clone <repo-url>
cd clip-bridge

# 使用 uv 安装依赖
uv sync
```

## 快速开始

### 首次运行

```bash
# 运行交互式配置
uv run python -m clip_bridge --setup

# 或直接运行，自动触发配置向导
uv run python -m clip_bridge
```

配置向导会询问：
1. 本机类型 (Mac 或 Ubuntu/Linux)
2. 对端 IP 地址

### 启动服务

**Mac 上：**
```bash
uv run python -m clip_bridge mac.yaml
```

**Ubuntu 上：**
```bash
uv run python -m clip_bridge ubuntu.yaml
```

## 配置文件

配置文件是 YAML 格式：

```yaml
# 本地监听端口
local_port: 9999

# 对端 IP 地址
remote_host: 192.168.1.100

# 对端端口
remote_port: 9998

# 剪贴板轮询间隔（秒）
poll_interval: 0.5

# 防循环冷却时间（秒）
sync_cooldown: 2.0

# 最大消息大小（字节）
max_size: 1048576
```

## 协议

消息格式: `CLIP<length>:<content>`

- `CLIP` - 4 字节前缀
- `<length>` - 内容长度（十进制）
- `:` - 分隔符
- `<content>` - 实际内容（UTF-8 编码）

## 开发

```bash
# 运行测试
uv run pytest

# 运行测试并显示输出
uv run pytest -v -s

# 运行特定测试
uv run pytest tests/test_config.py -v
```

## 依赖

- Python 3.10+
- pyperclip - 剪贴板操作
- pyyaml - 配置解析

## 许可

MIT License
EOF
```

**Step 2: 创建 .gitignore**

```bash
cat > /data/projects/clip-bridge/.gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo

# Config files (keep template)
*.yaml
!config.yaml.template

# uv
.uv/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Logs
*.log
EOF
```

**Step 3: Commit**

```bash
git add README.md .gitignore
git commit -m "docs: add README and .gitignore"
```

---

## 验证步骤

### 运行所有测试

```bash
cd /data/projects/clip-bridge
uv run pytest -v
```

### 手动测试

1. 在 Mac 上：
```bash
uv run python -m clip_bridge --setup
# 选择 Mac，输入 Ubuntu IP
uv run python -m clip_bridge mac.yaml
```

2. 在 Ubuntu 上：
```bash
uv run python -m clip_bridge --setup
# 选择 Ubuntu，输入 Mac IP
uv run python -m clip_bridge ubuntu.yaml
```

3. 在 Mac 上复制文本，检查 Ubuntu 是否同步

4. 在 Ubuntu 上复制文本，检查 Mac 是否同步

---

## 文件结构

```
clip-bridge/
├── clip_bridge/
│   ├── __init__.py
│   ├── main.py          # 入口，启动服务
│   ├── monitor.py       # 剪贴板监听器
│   ├── sender.py        # TCP 客户端（发送到对端）
│   ├── receiver.py      # TCP 服务端（接收来自对端）
│   ├── config.py        # 配置加载
│   ├── interactive.py   # 交互式配置向导
│   ├── cooldown.py      # 防循环机制
│   └── protocol.py      # 消息协议
├── tests/
│   ├── test_config.py
│   ├── test_protocol.py
│   ├── test_cooldown.py
│   ├── test_sender.py
│   ├── test_receiver.py
│   ├── test_monitor.py
│   ├── test_interactive.py
│   └── test_integration.py
├── docs/
│   └── plans/
│       ├── 2026-03-06-clip-bridge-design.md
│       └── 2026-03-06-clip-bridge-implementation.md
├── config.yaml.template
├── pyproject.toml
├── README.md
└── .gitignore
```
