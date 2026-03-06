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
