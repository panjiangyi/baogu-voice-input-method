# Typeless 客户端调研与 VoiceIME 改进

日期：2026-10-16。目标：本机 Typeless 2.2.0 Linux 发行包。

## 证据范围

`/opt/Typeless/resources/app.asar` SHA256：
`fe04ada92a412dbf095d79f67a091c2748e805d61fef1c238d3f6f78a2f6aa18`。

通过 REA 对选定的主进程、音频 worker、录音/通信 renderer 文件进行静态分析。
主 Evidence：`ev_c7600097947e2ae3ff1e80f55348e4dafee388b86e05c7dc3007a98d9d0c29fa`。
3 个 JS 文件解析无错误；完整包其他文件未分析，语义图达到节点上限。
源码恢复工具缺少 Wakaru。字符串混淆造成部分调用无法解析。
后续 literal trace 未在截断图中匹配 `replace_audio_context`，不是能力不存在的证据；
该消息及以下逻辑来自对发行包代码的补充静态读取。
没有执行 Typeless 代码、抓取实际听写请求或分析服务器实现。

## 已观察到的实现与迁移决定

| Typeless 发行包证据 | 能确认什么 | VoiceIME 采用方式 |
|---|---|---|
| `Clr6HqQG.js`：`/ws/rt_voice_flow`、音频二进制块、`set_audio_chunk_info` | 存在流式上传协议 | 保留本地流式 ASR，避免为模仿通信架构引入音频上传 |
| 同文件：`transcription`、`refine_completed`、`refined_text` | 客户端区分转写和整理结果 | 新增显式 `dictation` 口语整理模式，沿用预编辑后一次提交 |
| 同文件：`startRefineRace`、HTTP fallback、`Promise.race`、完成 ID 集合 | 存在兜底竞争及去重实现 | 本地候选与可选云端结果竞争；设置总等待时间，迟到结果丢弃 |
| 主进程：输入框、选区、可见文本辅助接口；通信层 `audio_context` 与更新消息 | 有上下文获取与传递能力 | 通过 Fcitx 原生桥读取当前会话的有界 surrounding-text；按用户要求默认开启，可显式关闭 |
| 主进程：`checkEditedText`、原始/当前内容、改动计数和 `auto_add_dictionary` 响应处理 | 存在修改追踪与自动加词反馈机制 | 本轮不自动追踪；先保留现有显式个人词库，避免把普通编辑当纠错 |
| 原生包：IBus/Fcitx 注册、`commit`、`surrounding`、敏感字段状态 | 多输入框适配，区分敏感输入 | 新上下文接口拒绝密码和敏感标记，限制 session 与焦点 |
| `refine_selected_text` 事件、`getSelectedText` / 模拟复制读取选区 | 针对选中文字的处理是独立能力 | 新增 `Alt + A` 选中文字提问：读 PRIMARY 选区，语音提问，独立窗口显示回答 |

云端模型名称、提示词、是否针对用户训练模型、线上延迟和服务端数据保留行为均未知。
不能从客户端出现两类事件，推断服务端一定使用两个独立模型。

## 本轮工程修改

1. 新增原生 `ContextSession(s) -> sss`：应用、前文、后文；各侧最多 500 个
   Unicode 码点，不包含选区正文。Python 在麦克风打开后、显示本句预编辑前取一次
   快照，避免查询延迟吞掉首字；旧插件可回退。
2. `dictation` 提示词要求去无意义口头语、重复、处理明确自我纠正；它是允许改写的
   可选模式，不承诺模型一定保真。系统指令与 JSON 输入/上下文/词典分开。
3. 独立单工作线程运行云端纠错，主流程轮询总期限与下一次 PTT。超时保留本地候选；
   后台请求不拥有输入桥，不能二次提交；后台仍忙时直接跳过下一次云端纠错。
4. 修复原先固定 256 tokens：按输入长度分配 512–8192 tokens，明确的 `max_tokens`
   截断返回完整原文。正常纠错日志改为字符计数，不记录输入、输出内容片段。
5. 部署脚本支持 `dictation`、上下文开关与等待预算。默认纠错模式不变；后续按用户要求，
   上下文默认开启，`VOICEIME_CONTEXT_ENABLED=0` 可关闭，云端纠错关闭时不发送。
6. 新增「选中文字提问」：左 Alt + `a` 为提问热键（右 Alt 仍是听写键）；优先读取 X11
   PRIMARY 选区，不导出 PRIMARY 的应用回退模拟 Ctrl+C 并保存/还原剪贴板。提问复用本地
   流式识别，**不写入应用正文**；回答经同一 AI 接口返回，显示在独立窗口（`voiceime-ask`）。
   提问与纠错开关独立，`VOICEIME_LLM_DISABLED=1` 同时禁止两者。

## 验证边界

使用本地 HTTP stub 验证请求结构、截断回退、口语模式路由；使用可阻塞 worker
验证总时间限制、下一次按键抢占及不积压请求。这些测试不证明真实模型整理质量。
原生 D-Bus 集成验证 Unicode 截取、选区排除、过期 session 和敏感字段排除。
真人录音与实际应用的上下文可用性仍需日常使用验收。

本轮检查结果：`python3 -m unittest discover -s tests` 共 83 项通过；
`python3 -m py_compile` 覆盖引擎、PTT、ask 窗口与全部测试；`bash -n` 与
`bash native/build.sh` 通过；隔离 `dbus-run-session` 内运行 `tests/native_bridge.py`
通过；`git diff --check` 通过。
选中文字提问的单元测试覆盖 PRIMARY 优先、Ctrl+C 回退与剪贴板还原、热键状态机、
请求文件的一次性消费、状态文件的原子写入、以及 ask 回答请求结构；真实选区、
不同应用到 PRIMARY/Ctrl+C 的实际可用性、以及回答质量仍需日常使用验收。
本轮仅更新项目及构建产物，未重启桌面服务、未触发真实 AI 提问、未更改个人词库。
