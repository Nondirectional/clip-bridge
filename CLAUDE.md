# Clip Bridge

一个简单的跨平台剪贴板共享工具，用于在局域网内多台电脑之间同步纯文本剪贴板内容。

## 项目概述

- **目标**: 在 Mac 和 Ubuntu 之间共享剪贴板（纯文本）
- **网络**: 同一局域网，TCP Socket 双向通信
- **语言**: Python 3.10+
- **配置**: 手动配置对端 IP 和端口

## 技术栈

- **Python**: 3.12
- **依赖管理**: uv

| 功能 | 技术 |
|------|------|
| 剪贴板操作 | `pyperclip` |
| 配置解析 | `pyyaml` |
| 网络通信 | `socket` (标准库) |

## 项目结构

```
clip-bridge/
├── clip_bridge/
│   ├── __init__.py
│   ├── main.py          # 入口，启动服务
│   ├── monitor.py       # 剪贴板监听器
│   ├── sender.py        # TCP 客户端（发送到对端）
│   ├── receiver.py      # TCP 服务端（接收来自对端）
│   └── config.py        # 配置加载
├── config.yaml          # 配置模板
├── pyproject.toml       # uv 项目配置
└── README.md
```

## 设计文档

## 开发约定

1. **TDD 模式**: 测试驱动开发，先写测试再写实现
2. **代码风格**: 遵循 PEP 8
3. **类型注解**: 使用 type hints
4. **日志**: 使用 `logging` 模块，格式为 `[LEVEL] Message`
5. **错误处理**: 网络错误自动重连，其他错误记录日志不崩溃
6. **测试**: 使用 pytest，Mac 和 Ubuntu 实际环境验证

## 核心协议

消息格式: `CLIP<length>:<content>`

- 前缀 `CLIP` - 4 字节
- `<length>` - 内容长度
- `:` - 分隔符
- `<content>` - 实际内容

最大消息大小: 1MB

## 启动方式

```bash
# 安装依赖
uv sync

# Mac 上
cp config.yaml mac.yaml
# 编辑 mac.yaml: local_port=9999, remote_host=Ubuntu_IP, remote_port=9998
uv run python -m clip_bridge mac.yaml

# Ubuntu 上
cp config.yaml ubuntu.yaml
# 编辑 ubuntu.yaml: local_port=9998, remote_host=Mac_IP, remote_port=9999
uv run python -m clip_bridge ubuntu.yaml
```
