# 平野孤鸿项目变更日志

## v0.4.9 (2026-10-05)

### 新增
- **引擎性能优化模块**（`src/perf_optimizer.py`）：针对西山居 KG3D 引擎，改写游戏 `configs\config.ini`
  里出厂被锁死的性能参数。三档可选（保守 / 均衡 / 极致），线程数与内存上限按本机硬件自动计算。
- **优化面板**：侧边栏独立导航「⚡ 优化」（`_build_sidebar` 的 NAV_ITEMS 第 4 项），
  下分 4 个子项 —— 优化档位 / 改动明细 / 系统侧优化 / 还原。
  每个子页顶部共用本机硬件与当前档位状态条，底部共用说明。
- 单元测试 `tests/test_perf_optimizer.py`：18 项，覆盖 ini 字节级最小侵入、profile 数据完整性、
  公开 API 契约、UI 面板构造冒烟。

### 优化依据（逆向证据）
- `KG3DEngineX64.dll` 的 `GetInt(section, key, default)` 调用现场抓到出厂默认值：
  `MinWorkSet=600` `MaxWorkSet=1400` `NumCpuThread=1` `UseMultiThreadCull=0`
  `UseMultiThreadLoad=0` `bMultiThreadLoadAnimation=0` `bEnableModelLod=0` `UseProgressMeshLOD=0`。
- 隐藏开关 `bDisableDynamicScale`：exe 在 `0x371123` 用 `GetPrivateProfileIntA` 从 `[KG3DENGINE]` 读取，
  但 config.ini 里原本没有这一项 → 引擎按默认 0 处理 = 动态分辨率缩放常开，画面被压糊。
- 已验证**没有任何模块对 config.ini 做 WritePrivateProfileStringA**，改值不会被游戏写回覆盖。
- 证伪：`config.cfg` 的 `LogicFrame` / `RenderFrame` 无任何代码读取，改它不会解锁帧率。

### 技术要点
- ini 写入为字节级最小侵入：保留行尾符与全部非 ASCII 字节，实测 283→284 行、CRLF 全保留。
- 首次改动前自动备份原始 config.ini，还原走同一份备份索引。
- 应用状态记在 `_applied_state.json`，避免"动态值每次微调导致档位判定失效"。
- 双显卡笔记本支持：写 `HKCU\Software\Microsoft\DirectX\UserGpuPreferences` 强制 `GpuPreference=2`。

### 导航索引重排（改 sidebar 时必读）
侧边栏插入「优化」后，原「存档/监控/内部」顺延一位，**设置由 6 变为 7**。
同步改动四处，缺一就会点错页：
`_build_sidebar` 的 NAV_ITEMS、settings 按钮的 `_switch_nav(7)`、
`func_data` 的键重编号、`_update_action_panel` 的 nav 分支。
测试 `test_no_empty_nav_page` 会遍历全部导航索引，防止重排后出现白屏页。

### 版本
- `APP_VERSION` / `trainer_version` / 安装包版本号全部 0.4.8 → 0.4.9。
- v0.4.8 的注入器 / 修改器拆分结构保持不变，调用契约未动。

## v0.4.6 (2026-09-27)

### UI集成
- 新增模块UI集成：预设系统（保存/加载/删除/列出）、操作日志撤销/重做按钮、i18n语言切换下拉框、主题切换下拉框、紧急停止按钮、热键冲突检测
### 新增
- 崩溃报告自动收集（src/crash_report.py）：全局异常捕获、系统信息/日志/配置/线程收集、JSON+TXT报告生成、自动保存
- 主题增强（src/theme_manager.py）：6种预设主题（暗色/亮色/午夜蓝/森林绿/日落橙/高对比度），自定义主题创建/导入/导出，tkinter主题应用
### 清理
- 死代码清理：src/gui/ 目录（PyQt旧GUI，18个文件约230KB）已归档到 archived/legacy_gui/，无外部引用
### 重构
- 代码重构：cheat_tools.py 与 advanced_tools.py 重复函数分析，max_all_talents 已搬家到 cheat_tools，advanced_tools 改为导入，详见 docs/代码重构报告.md
### 新增
- CI/CD 工作流（.github/workflows/ci.yml）：自动测试、语法检查、构建EXE、编译DLL、发布Release
- 单元测试（tests/test_core.py）：覆盖输入校验、原子文件、操作历史、热键防抖、紧急停止、事务、i18n、热键冲突 8 个模块
- 热键冲突检测（src/hotkey_conflict.py）：检测内部/系统/游戏热键冲突，提供替代建议，支持配置导入导出
- 日志增强（src/log_enhancer.py）：5级日志、文件滚动、过滤搜索、导出、统计、监听器
- 启动优化（src/startup_optimizer.py）：懒加载、并行初始化、延迟初始化、启动性能分析
- 非线性历史跳转（src/nonlinear_history.py）：支持跳转到任意历史快照点，分支历史，快照导入导出
- 事务批量操作（src/transaction.py）：多个操作打包成事务，全部成功或全部回滚，支持事务历史管理
- Lua 探查器（src/lua_explorer.py）：列出全局变量、递归探查表结构、获取函数信息、搜索变量、导出环境
- 多语言 i18n 框架（src/i18n.py + locales/）：支持简体中文/英文切换，翻译键管理，语言切换监听器
- 用户文档补全：docs/用户手册.md（快速上手、功能说明、热键、安全提示）、docs/故障排查指南.md（9大类问题排查）
- 紧急停止管理器（src/emergency_stop.py）：一键终止全部内存写入/Hook/异步任务，支持回调和状态查询
- 热键防抖（src/hotkey_debouncer.py）：防止连续按热键重复触发，不同功能配置不同阈值（普通200ms/高危500ms/一次性1000ms）
- 内存地址合法性校验（src/address_validator.py）：写入前验证地址范围、内存页状态、可写权限、写入范围，防止非法地址写入导致崩溃
- 自动更新系统（src/auto_updater.py）：GitHub Releases 检查更新、下载、SHA256校验、原子替换、失败回滚
- AOB 特征码扫描模块（src/aob_scanner.py）：支持通配符 ?? 的内存特征码搜索，可限定最大结果数
- 游戏内 Overlay 框架（src/injector/overlay.c + src/overlay_controller.py）：DX11 Present Hook + ImGui 渲染框架，INSERT 键切换显示，命名管道通信
- 配置常驻内存+延时写入：配置加载后缓存到内存，保存时默认延时500ms合并写入，减少频繁IO；程序退出自动flush
- 进程句柄缓存（src/process_handle_cache.py）：缓存 OpenProcess 句柄，避免频繁打开/关闭，进程退出自动清理
- 操作日志与撤销机制（src/operation_history.py）：记录所有用户操作，支持撤销/重做，操作历史上限100条
- 系统诊断模块（src/diagnostic.py）：一键收集系统环境、修改器状态、游戏状态、依赖检查，生成诊断报告并可导出
- 监控页新增"一键系统诊断"和"导出诊断报告"按钮
- 预设方案系统（src/preset_manager.py）：保存/加载/删除/重命名/导入/导出修改器配置预设
- 输入数值范围校验模块（src/input_validator.py）：资源数量、知名度、幸福度、品阶等级、跳天天数、时间流速等场景的统一校验
- 资源输入非法时弹窗提示，不再静默回退默认值
- 品阶晋升目标钳制到 1~14 级，避免输入超大数导致游戏异常

### 安全
- 进程白名单：inject_dll 注入前验证目标进程名，只允许注入 BalladsOfHongye.exe，防止误注入其他程序
- 高危操作二次确认：开启全部作弊、全部升级、全部完工、解锁全部成就/地块/天赋、关闭全部灾害等7项批量操作均添加确认对话框
- 所有用户输入数值经过范围校验，防止负数、超大数、非数字导致游戏崩溃或存档损坏
- 存档原子写入（src/atomic_file.py）：配置保存、存档备份先写临时文件再原子替换，防止断电/崩溃导致文件损坏
- 存档备份采用 .tmp 目录 + rename 原子重命名，避免半成品备份
- 命名管道通信（Named Pipe）替代文件轮询，Python端与DLL端通过 `\\.\pipe\woldvein_trainer` 双向通信
- 管道通信失败时自动回退到文件轮询（lua_cmd.txt/lua_result.txt），保证向后兼容
- Python端使用 ctypes 直接调用 Windows API，不依赖 pywin32，PyInstaller 打包更干净

### 优化
- 通信延迟从 50ms 轮询降低到即时响应（管道消息模式）
- 消除文件IO开销，减少磁盘读写

### 技术细节
- DLL端：后台线程创建命名管道服务器，lua_pcall hook 中用 PeekNamedPipe 检查命令
- Python端：_connect_pipe 带超时重试，_pipe_execute 保持 REQ_ID 竞态防护协议
- 两端协议完全一致：REQ_ID:xxxxxxxx\n + Lua代码 / 结果

---

## v0.4.5 (2026-09-26)

### 变更
- 新增「内部」一级导航，复刻 0.3.1 改资源面板（资源表格/实时数值/时间流速/满天赋/幸福度等）

---

## v0.4.3 (2026-09-24)

### 新增
- Inno Setup 安装包（中英双语、桌面快捷方式、卸载清理用户数据）

### 优化
- 版本号统一从 `src/constants.py::APP_VERSION` 读取，消除多处版本不一致
- 项目结构梳理，源码与构建产物分离

### 修复
- 代码审查发现的多项问题（主题切换 TclError、孤立空 group、热键映射等）

---

## v0.4.2 (2026-09-22)

### 重构
- 按关注点分离原则重组目录（app/runtime/domain/input/gui/utils 分包）

### 修复
- 统一版本号到 constants.py，消除 0.3.9/0.4.2 多处不一致
- build spec 问题（upx=False、删除 config.json 打包、补全 hiddenimports）
- trainer_ui_tk.py 主题切换时旧定时器访问已销毁控件的 TclError
- 孤立空 LabelFrame、硬编码游戏路径等

### 新增
- bat 启动器（chcp 65001 中文支持）

---

## v0.4.1 (2026-09-20)

### 新增
- 监控面板（内存涨跌实时监控）
- 存档管理（备份/恢复/打开存档文件夹）

### 优化
- 设置页窗口大小自定义

### 修复
- 监控页切换后不稳定、定时器叠加问题

---

## v0.4.0 (2026-09-19)

### UI 重做
- 微信三栏布局（左侧导航 + 中间功能列表 + 右侧操作面板）
- 新增游戏概览页（进程检测 + DLL 注入 + 快速操作）

### 新增
- 创造模式 9 个子选项（原 4 项扩展）

### 优化
- 全局文字左对齐

### 修复
- 资源编辑功能接入 GUI（此前整块死代码）

---

## v0.3.9 (2026-09-18)

### 修复
- DLL 编译环境切换为 VS 2022 BuildTools（mingw 启动失败）
- 通信路径统一策略

### 优化
- 配置文件不写 C 盘，统一程序目录

---

## v0.3.8 (2026-09-15)

### 新增功能

**创造模式新增2个子选项：**
1. **道路连接豁免**（road_bypass）：行人不必经过道路，可直接到达任意建筑
   - Hook LBuildingMgr:ModifyCheckRoadFlag，所有建筑 m_bIsCheckRoadAdd = false
   - 自动调用 UpdateIsConnectedToPost() 更新连接状态

2. **人口不分类别**（population_universal）：工人/匠人/学者通用，任何人口都可做任何工作
   - Hook LBaseBlock:GetPopulation，返回所有类型人口总和
   - 包括：普通人口、匠人、学者、难民、临时人口

### 修复

- 修复创造模式GUI选项key与后端不一致的问题（max_level→max_boom等）
- 创造模式子选项现在正确传递到Lua端

### 技术细节

- lua_engine.py：LUA_CREATIVE_ENABLE 添加第5、6步hook，LUA_CREATIVE_DISABLE 添加对应还原
- creative_mode.py：_creative_options 新增 road_bypass、population_universal，默认开启
- trainer_ui_tk.py：创造模式页从4个复选框增加到6个

---

## 2026-09-15

### v0.3.7 - 微信三栏布局全功能版 + 搜索功能

**版本号更新**
- `trainer_ui_tk.py`: VERSION = "v0.3.7"
- `main.py`: 头部注释更新为 v0.3.7
- `src/constants.py`: APP_VERSION = "0.3.7"

**新功能：搜索框真正可用**
- 中间功能列表顶部搜索框从摆设变为真正可用
- 跨所有分类搜索（主页/进程/资源/创造/工具/存档/设置）
- 输入关键词实时过滤，显示匹配的功能项
- 搜索结果带分类标签（── 资源 ──）
- 点击搜索结果直接跳转到对应功能
- 清空搜索框恢复正常列表

**修复：启动方式统一为 main.py**
- `main.py` 改为导入 `trainer_ui_tk` 的 main 函数（原为 `src.gui.main_gui`）
- 启动脚本 `启动修改器_v0.3.6.bat` 改为 `python main.py`
- 单实例互斥体更新为 `woldvein_trainer_mutex_v036`
- 桌面快捷方式「平野孤鸿修改器 v0.3.6」指向 main.py 启动

**修复：全局文字左对齐**
- 主页状态卡片：标题和数值左对齐（原为居中）
- 进程页：进程信息左对齐
- 一键全开页：提示文字和功能清单左对齐
- 存档管理页：存档目录提示、存档列表左对齐
- 热键设置页：提示文字左对齐
- 日志管理页：路径文字左对齐
- MOD管理页：说明文字、状态文字左对齐
- 关于页：版本信息左对齐

---

## 2026-09-15

### v0.3.6 - 微信三栏布局全功能集成版

**UI 重做：微信电脑客户端三栏布局**
- 完全抛弃旧版 tab 标签页布局，改为微信风格三栏结构
- 左侧导航栏（70px，浅灰 #f7f7f7）：图标按钮，选中微信绿 #07C160 高亮
- 中间功能列表（260px，白色）：搜索框 + 功能项（图标+名称+描述+状态红点）
- 右侧操作面板：顶部标题栏（56px）+ 中间滚动操作区 + 底部日志区
- 配色：主色 #07C160（微信绿），正文纯黑 #000000，次要文字 #999999，分割线 #e6e6e6
- 字体：微软雅黑

**功能全部集成（无占位页）**

主页：
- 游戏/DLL/Lua 三个状态卡片（每3秒自动更新）
- 快速操作按钮（启动游戏/注入DLL/检测进程）

进程：
- 检测游戏进程 / 启动游戏 / 注入DLL
- 进程信息显示（PID + DLL状态）

资源修改：
- 8种资源单独增加（可自定义数量，默认100万）
- 一键全部资源 +100万
- 资源归零（带确认对话框）
- 幸福度最大 / 知名度 +10000 / 恢复幸福度

创造模式：
- 4个选项（鸿业满级/全建筑解锁/无限资源/无限制升级）
- 全选/反选
- 开启/关闭创造模式
- 诊断解锁状态

高级工具（12个子功能）：
- ⏰ 时间控制：1x/2x/4x/8x加速、春夏秋冬、跳天跳月、诊断
- 🌤️ 天气控制：固定晴天/恢复天气/诊断
- 👤 NPC管理：探查NPC/谋士升满级/探查谋士/人口满员
- 🏠 建造控制：建筑列表/全部升级/全部完工/升级到顶级
- 🏙️ 城市品阶：品阶+1/满级/完成条件/诊断/城市全发展
- 🎖️ Steam成就：全解锁/地块挑战/探查
- 🌾 地块解锁：全解锁/探查
- 🧠 天赋系统：全解锁/满级/+200点/诊断
- 🌪️ 灾害控制：清除地震/全关闭/禁用触发/自然/人为灾害
- 🎆 节日控制：暂停/关闭烟花/清除广告/固定季节/跳过事件
- 💎 核心数值：金钱/幸福度/创造力/繁荣/品阶直接设置 + 市场/产业链/难民/声望/税收
- 🔥 一键全开：所有作弊一次性开启

存档管理：
- 刷新存档列表
- 备份当前存档（整个存档目录）
- 备份单个存档文件
- 清理旧备份（带确认）

设置：
- ⌨️ 热键设置：12个热键列表 / 恢复默认 / 重新注册
- 📝 日志管理：清空日志文件 / 打开日志目录 / 复制日志路径
- 📦 MOD管理：检测散文件MOD / 安装 / 卸载
- ℹ️ 关于：版本信息

**技术实现**
- 独立界面文件 `trainer_ui_tk.py`（约1000行）
- 所有业务操作通过 `threading.Thread` 异步执行，不卡UI
- 日志通过 `set_log_callback` 实时显示到GUI
- 状态检测每3秒自动刷新

---

## 2026-09-14

### v0.3.4 - 微信三栏布局初版（PyQt5 尝试 → tkinter 实现）

**UI 重做尝试**
- 用户要求按照微信电脑客户端三栏结构重做UI
- 先尝试 PyQt5 + QSplitter 实现
- 发现用户 Python 3.14 不支持 PyQt5/PyQt6（无预编译包）
- 尝试 winget 安装 Python 3.12，被用户制止（"你都不问我吗？"）
- 最终改用 tkinter 实现微信三栏布局

**初版功能**
- 纯界面布局，无业务逻辑
- 左侧导航 + 中间功能列表 + 右侧操作面板
- 主页/进程/资源/创造模式 四个页面有基本界面
- 其他页面为占位

---

## 2026-09-14

### v0.3.1 - 旧版 tab 布局稳定版

**基础功能**
- 7大标签页：资源修改/创造模式/存档编辑/热键设置/游戏监控/高级工具/应用设置
- DLL注入 + inline-hook lua_pcall 执行Lua脚本
- 资源修改（8种资源 + 幸福度 + 知名度）
- 创造模式（鸿业满级/全建筑解锁/无限资源/无限制升级）
- 高级工具（时间/天气/NPC/建造/城市/成就/天赋/灾害等）
- 存档管理
- 热键管理
- 游戏监控

**已知问题**
- UI布局为传统 tab 标签页，视觉效果一般
- 部分高级工具功能失效（时间加速/季节变换/NPC人数状态）
- 创造模式建筑解锁有缺陷

---

## 技术栈

- **语言**：Python 3.14 + tkinter
- **DLL**：C (mingw-w64)，Inline Hook Lua5X64.dll 的 lua_pcall
- **通信**：命令文件（lua_cmd.txt / lua_result.txt）轮询
- **游戏**：平野孤鸿 (Ballads of Hongye)，Steam AppID 2656540
- **游戏路径**：D:\steam\steamapps\common\BalladsOfHongye_CN
