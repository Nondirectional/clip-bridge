# Clip Bridge 自动发现功能设计文档

**日期**: 2026-03-06
**作者**: Claude & User
**状态**: 已批准

## 概述

为 Clip Bridge 添加 UDP 广播自动发现功能，使 Mac 和 Ubuntu 设备能在局域网内自动发现彼此并建立连接，无需手动配置 IP 地址。

## 背景

当前版本需要手动在配置文件中指定对端的 IP 地址，这在动态 IP 环境或多设备场景下不够便利。自动发现功能可以简化用户体验。

## 设计目标

1. 无需手动配置 IP，启动即用
2. 使用 UDP 广播，简单可靠
3. 自动连接第一台发现的设备
4. 兼容现有手动配置

## 架构

### 新增组件

```
clip_bridge/
├── discovery.py          # 新增：UDP 广播发现模块
├── config.py             # 修改：新增 discovery 相关配置
└── main.py               # 修改：启动流程集成发现
```

### 启动流程变更

```
原流程: 加载配置 → 启动 receiver → 连接 sender → 启动 monitor

新流程: 加载配置 → UDP 发现对端 → 更新 remote_host → 启动 receiver → 连接 sender → 启动 monitor
```

## 广播协议

### 消息格式

```
CLIP-HELLO:<local_port>
```

- 前缀 `CLIP-HELLO:` - 便于识别和过滤
- `<local_port>` - 本机监听端口（文本格式）
- 使用 UDP 广播到 `255.255.255.255:9997`

### 示例

```
Mac 广播:    CLIP-HELLO:9999
Ubuntu 广播: CLIP-HELLO:9998
```

## 组件设计

### `discovery.py` 模块

```python
@dataclass
class DiscoveryConfig:
    broadcast_port: int = 9997      # 广播监听端口
    timeout: float = 3.0            # 发现超时时间（秒）
    broadcast_interval: float = 0.5 # 广播间隔（秒）

@dataclass
class PeerDevice:
    ip: str          # 设备 IP 地址
    port: int        # 设备监听端口
    last_seen: float # 最后发现时间

class UDPAutoDiscovery:
    def __init__(self, config: DiscoveryConfig, local_port: int)

    def discover(self) -> Optional[PeerDevice]
        """广播自己 + 监听他人，返回第一台发现的设备"""

    def _broadcast_presence(self) -> None
        """在后台线程持续广播"""

    def _listen_for_broadcasts(self) -> List[PeerDevice]
        """监听并收集发现的设备"""
```

### `config.py` 修改

```python
@dataclass
class Config:
    # 现有字段...
    auto_discover: bool = True          # 新增：是否启用自动发现
    discovery_timeout: float = 3.0      # 新增：发现超时
    broadcast_port: int = 9997          # 新增：广播端口
```

### `main.py` 修改

```python
class ClipBridge:
    def __init__(self, config: Config):
        # 现有初始化...

        # 新增：自动发现
        if config.auto_discover:
            peer = self._discover_peer(config)
            if peer:
                config.remote_host = peer.ip
                config.remote_port = peer.port
                logger.info(f"Auto-discovered peer: {peer.ip}:{peer.port}")
```

## 数据流

### 发现时序

```
设备 A (Mac)                设备 B (Ubuntu)
    |                            |
    | 启动                       | 启动
    |                            |
    | → 广播 CLIP-HELLO:9999 →   |
    | ← 广播 CLIP-HELLO:9998 ←   |
    |                            |
    | 收到 B 的广播              | 收到 A 的广播
    | IP: 192.168.1.100:9998     | IP: 192.168.1.50:9999
    |                            |
    | 更新 remote_host           | 更新 remote_host
    | 连接到 192.168.1.100:9998  | 连接到 192.168.1.50:9999
    |                            |
    | ←──── TCP 连接 ────→       |
```

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 未发现设备 | 记录日志，回退到配置的 remote_host |
| 广播失败 | 记录日志，继续监听 |
| 超时 | 使用配置的 remote_host |
| 无效广播消息 | 忽略，记录调试日志 |

## 测试

### 单元测试

```python
# tests/test_discovery.py

def test_broadcast_message_format():
    # 验证广播消息格式正确

def test_discover_peers():
    # 模拟两台设备，验证能互相发现

def test_discovery_timeout():
    # 验证超时后返回 None

def test_parse_broadcast():
    # 验证解析广播消息
```

### 集成测试场景

1. **同网段两台设备**：Mac 和 Ubuntu，验证自动发现并连接
2. **仅一台设备**：验证超时后回退到配置
3. **多台设备**：验证只连接第一台
4. **已有配置**：验证 auto_discover=false 时跳过发现

### 手动验证步骤

```bash
# Mac 上
uv run python -m clip_bridge mac.yaml
# 预期输出:
# [INFO] Broadcasting presence on port 9999...
# [INFO] Discovered peer: 192.168.1.100:9998

# Ubuntu 上
uv run python -m clip_bridge ubuntu.yaml
# 预期输出:
# [INFO] Broadcasting presence on port 9998...
# [INFO] Discovered peer: 192.168.1.50:9999
```

## 实现注意事项

1. UDP Socket 设置 `SO_BROADCAST` 选项
2. 广播和监听使用不同线程
3. 监听设置超时避免永久阻塞
4. 过滤掉自己发出的广播（通过端口匹配）
5. 使用固定端口 9998/9999 简化逻辑

## 后续扩展可能

- 支持 mDNS 作为备选发现方式
- 支持设备名称显示
- 支持多设备同时连接
- 支持密钥验证增强安全性
