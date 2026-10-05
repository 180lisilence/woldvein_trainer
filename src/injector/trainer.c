/*
 * woldvein_trainer.dll v0.3 - 《平野孤鸿》通用修改器注入DLL
 *
 * 版本历史：
 *   v0.1 初版：IAT-Hook lua_pcall，发现KLuaVM缓存指针绕过IAT
 *   v0.3 改为Inline-Hook Lua5X64.dll，增加指令长度解码器，
 *        新增请求ID竞态防护（CMD/RESULT 文件首行 REQ_ID 校验），
 *        F6/F7 opcode 特殊处理（按 reg 字段判断是否带 imm）
 *
 * 关键修复：
 *   - 定制Lua5X64.dll无lua_tostring导出，用lua_tolstring替代
 *   - UTF-8 BOM头导致loadstring失败，改用二进制模式跳过BOM
 *   - 指令长度解码器：自研256项opcode表，失败时放弃安装
 * =================================================
 * 原理：Inline Hook Lua5X64.dll 的 lua_pcall，
 *       捕获 lua_State，通过命令文件机制在游戏主线程执行 Lua 代码。
 *
 * 通信机制：
 *   - Python端写入 lua_cmd.txt（Lua代码）
 *   - DLL在主线程pcall hook中检测并执行
 *   - 执行结果写入 lua_result.txt
 *
 * 安全设计：
 *   - 所有Lua代码在游戏主线程执行
 *   - pcall保护，单条命令失败不影响游戏
 *   - 命令文件执行后立即删除
 *
 * 编译（MinGW-w64）：
 *   gcc -shared -O2 -w -o woldvein_trainer.dll trainer.c -luser32 -lkernel32
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

/* ---------- Lua 5.1 API 类型声明 ---------- */
typedef struct lua_State lua_State;
typedef int  (__cdecl *lua_pcall_t)(lua_State *L, int nargs, int nresults, int errfunc);
typedef const char* (__cdecl *luaL_loadstring_t)(lua_State *L, const char *s);
typedef const char* (__cdecl *lua_tolstring_t)(lua_State *L, int idx, size_t *len);
typedef void (__cdecl *lua_settop_t)(lua_State *L, int idx);
typedef int  (__cdecl *lua_toboolean_t)(lua_State *L, int idx);
typedef int  (__cdecl *lua_type_t)(lua_State *L, int idx);
typedef double (__cdecl *lua_tonumber_t)(lua_State *L, int idx);

#define LUA_GLOBALSINDEX  (-10002)
#define LUA_TSTRING 4
#define LUA_TNUMBER 3

/* ---------- 全局状态 ---------- */
static lua_State *g_L = NULL;
static HMODULE g_lua_dll = NULL;
static lua_pcall_t real_lua_pcall = NULL;
static luaL_loadstring_t g_loadstring = NULL;
static lua_tolstring_t g_tolstring = NULL;
static lua_settop_t g_settop = NULL;
static lua_toboolean_t g_toboolean = NULL;
static lua_type_t g_lua_type = NULL;
static lua_tonumber_t g_lua_tonumber = NULL;
static char g_result_str[65536] = {0};  /* 字符串返回值缓冲区 */
static int g_result_is_str = 0;         /* 上次返回值是否为字符串 */
static char g_req_id[64] = {0};         /* 当前请求ID（用于竞态防护） */

static volatile LONG g_hooked = 0;
static CRITICAL_SECTION g_log_lock;
static char g_log_file[MAX_PATH] = {0};

/* ---------- 命名管道通信（v0.4.6 新增，替代文件轮询） ---------- */
#define PIPE_NAME "\\\\.\\pipe\\woldvein_trainer"
static HANDLE g_pipe = INVALID_HANDLE_VALUE;
static HANDLE g_pipe_thread = NULL;
static volatile LONG g_pipe_connected = 0;
static volatile LONG g_pipe_stop = 0;
static CRITICAL_SECTION g_pipe_lock;

/* Inline hook 相关 */
static unsigned char g_orig_bytes[32] = {0};
static void *g_hook_target = NULL;
static void *g_trampoline = NULL;
static int g_hook_length = 0;  /* 实际 hook 长度（动态计算） */

/* ---------- x86-64 指令长度解码器（简化版，用于计算 inline hook 长度） ---------- */

/* opcode 属性表：每项 1 字节
 * bit 0-1: immediate 长度 (0=无, 1=1字节, 2=2/4字节取决于0x66, 3=4字节)
 * bit 2:   1=有 ModR/M 字节
 * bit 3:   1=0x0F 2字节 opcode
 * bit 4:   1=immediate 长度受 0x66 前缀影响（默认2字节，有0x66时仍2字节）
 * bit 5-7: 保留
 */
static const unsigned char opcode_table[256] = {
    /* 00 */ 0x04,0x04,0x04,0x04, 0x01,0x03,0x00,0x00,  /* add/or/adc/sbb + AL/EAX imm; 06/07=PUSH/POP ES(x64无效) */
    /* 08 */ 0x04,0x04,0x04,0x04, 0x01,0x03,0x00,0x00,  /* 0E=PUSH CS(x64无效); 0F=2字节opcode前缀(单独处理) */
    /* 10 */ 0x04,0x04,0x04,0x04, 0x01,0x03,0x00,0x00,  /* 16/17=PUSH/POP SS(x64无效) */
    /* 18 */ 0x04,0x04,0x04,0x04, 0x01,0x03,0x00,0x00,  /* 1E/1F=PUSH/POP DS(x64无效) */
    /* 20 */ 0x04,0x04,0x04,0x04, 0x01,0x03,0x00,0x00,  /* 26=ES前缀; 27=DAA(x64无效) */
    /* 28 */ 0x04,0x04,0x04,0x04, 0x01,0x03,0x00,0x00,  /* 2E=CS前缀; 2F=DAS(x64无效) */
    /* 30 */ 0x04,0x04,0x04,0x04, 0x01,0x03,0x00,0x00,  /* 36=SS前缀; 37=AAA(x64无效) */
    /* 38 */ 0x04,0x04,0x04,0x04, 0x01,0x03,0x00,0x00,  /* 3E=DS前缀; 3F=AAS(x64无效) */
    /* 40 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  /* REX 前缀（单独处理） */
    /* 48 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    /* 50 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  /* push/pop reg */
    /* 58 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,
    /* 60 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x02,0x04,  /* pushad/popad/.../imul */
    /* 68 */ 0x03,0x04,0x00,0x00, 0x00,0x00,0x00,0x00,  /* push imm / imul r,rm,imm */
    /* 70 */ 0x01,0x01,0x01,0x01, 0x01,0x01,0x01,0x01,  /* jcc rel8 */
    /* 78 */ 0x01,0x01,0x01,0x01, 0x01,0x01,0x01,0x01,
    /* 80 */ 0x05,0x07,0x05,0x05, 0x01,0x01,0x01,0x01,  /* alu r/m,imm (有ModR/M) */
    /* 88 */ 0x04,0x04,0x04,0x04, 0x04,0x04,0x04,0x04,  /* mov r/m,r / mov r,r/m */
    /* 90 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  /* nop/xchg */
    /* 98 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,  /* cbw/cwde/cdq/... */
    /* A0 */ 0x03,0x03,0x03,0x03, 0x00,0x00,0x00,0x00,  /* mov moffs / movs */
    /* A8 */ 0x01,0x03,0x00,0x00, 0x00,0x00,0x00,0x00,  /* test al/eax,imm (A8/A9) / stos (AA/AB无立即数) */
    /* B0 */ 0x01,0x01,0x01,0x01, 0x01,0x01,0x01,0x01,  /* mov reg8, imm8 */
    /* B8 */ 0x03,0x03,0x03,0x03, 0x03,0x03,0x03,0x03,  /* mov reg, imm32/64 */
    /* C0 */ 0x05,0x05,0x02,0x00, 0x00,0x00,0x05,0x07,  /* rol r/m,imm / ret / mov r/m,imm32 (C7=0x07) */
    /* C8 */ 0x02,0x00,0x02,0x00, 0x00,0x00,0x00,0x00,  /* enter / leave / retf / int3 */
    /* D0 */ 0x04,0x04,0x04,0x04, 0x00,0x00,0x00,0x00,  /* rol r/m,1/cl / aam/aad/salc/xlat */
    /* D8 */ 0x04,0x04,0x04,0x04, 0x04,0x04,0x04,0x04,  /* x87 FPU (有ModR/M) */
    /* E0 */ 0x01,0x01,0x01,0x01, 0x01,0x01,0x01,0x01,  /* loop/jecxz / in/out imm8 */
    /* E8 */ 0x03,0x03,0x01,0x00, 0x00,0x00,0x00,0x00,  /* call/jmp rel32 / jmp rel8 / in/out dx */
    /* F0 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x07,0x07,  /* lock/.../hlt/cmc / test r/m,imm32 (F6=0x05,F7=0x07) */
    /* F8 */ 0x00,0x00,0x00,0x00, 0x00,0x00,0x04,0x04,  /* clc/stc/cli/sti/cld/std / inc/dec r/m */
};

/* 0x0F 2字节 opcode 表（简化：大部分有 ModR/M） */
static int opcode_has_modrm_0f(unsigned char op2) {
    /* 0x0F 开头的指令，大部分有 ModR/M
     * 例外：0x0F 0x05 (syscall), 0x0F 0x0B (ud2), 0x0F 0x31 (rdtsc), 等
     * 对于 lua_pcall 开头，通常不会遇到这些
     */
    if (op2 == 0x05 || op2 == 0x0B || op2 == 0x31 || op2 == 0x34 ||
        op2 == 0x35 || op2 == 0x37 || op2 == 0x3E || op2 == 0x77 ||
        op2 == 0x90 || op2 == 0xA2 || op2 == 0xAA || op2 == 0xC8 ||
        op2 == 0xC9 || op2 == 0xCA || op2 == 0xCB) {
        return 0;
    }
    /* 0x0F 0x80-0x8F: jcc rel32 (无 ModR/M) */
    if (op2 >= 0x80 && op2 <= 0x8F) return 0;
    /* 0x0F 0x18-0x1F: prefetch (有 ModR/M) */
    /* 其他默认有 ModR/M */
    return 1;
}

static int get_instruction_length(unsigned char *code, int max_len) {
    int len = 0;
    int has_66 = 0;
    int rex = 0;

    if (max_len <= 0) return 0;

    /* 1. 跳过 legacy 前缀 */
    while (len < max_len) {
        unsigned char b = code[len];
        if (b == 0x66) { has_66 = 1; len++; }
        else if (b == 0x67) { len++; } /* 0x67地址大小前缀，不需要记录 */
        else if (b == 0xF0 || b == 0xF2 || b == 0xF3) len++;
        else if (b == 0x2E || b == 0x36 || b == 0x3E || b == 0x26 || b == 0x64 || b == 0x65) len++;
        else break;
    }

    /* 2. REX 前缀 */
    if (len < max_len && code[len] >= 0x40 && code[len] <= 0x4F) {
        rex = code[len];
        len++;
    }

    /* 3. Opcode */
    if (len >= max_len) return len;
    unsigned char op = code[len];
    len++;

    int has_modrm = 0;
    int imm_len = 0;
    

    if (op == 0x0F) {
        /* 2字节 opcode */
        if (len >= max_len) return len;
        unsigned char op2 = code[len];
        len++;
        has_modrm = opcode_has_modrm_0f(op2);
        /* 0x0F 0x80-0x8F: jcc rel32 */
        if (op2 >= 0x80 && op2 <= 0x8F) imm_len = 4;
        /* 0x0F 0x38/0x3A: 3字节 opcode (有 ModR/M) */
        if (op2 == 0x38 || op2 == 0x3A) {
            if (len >= max_len) return len;
            len++; /* 第3字节 */
            has_modrm = 1;
        }
    } else {
        unsigned char attr = opcode_table[op];
        has_modrm = (attr & 0x04) ? 1 : 0;
        int imm_code = attr & 0x03;
        if (imm_code == 1) imm_len = 1;
        else if (imm_code == 2) imm_len = has_66 ? 2 : 4;
        else if (imm_code == 3) imm_len = (rex & 0x08) ? 8 : 4; /* REX.W 时 imm=8 (mov reg64, imm64) */
    }

    /* 4. ModR/M */
    if (has_modrm && len < max_len) {
        unsigned char modrm = code[len];
        len++;
        int mod = (modrm >> 6) & 0x3;
        int reg = (modrm >> 3) & 0x7;  /* ModR/M reg 字段 */
        int rm = modrm & 0x7;

        /* F6/F7 特殊处理：reg=0/1 是 test（带 imm8/imm32），reg=2-7 是 not/neg/mul/div（无 imm）
         * 不修正会导致 F6 /2 ~ /7 多算 1 字节 imm，可能切断后续指令致游戏崩溃
         */
        if (op == 0xF6 || op == 0xF7) {
            if (reg <= 1) {
                /* test r/m, imm：F6 → imm8, F7 → imm32（受 0x66 影响 imm16） */
                if (op == 0xF6) imm_len = 1;
                else imm_len = has_66 ? 2 : 4;
            } else {
                /* not/neg/mul/imul/div/idiv：无 imm */
                imm_len = 0;
            }
        }

        /* SIB 字节 (mod=00, rm=100) */
        if (mod == 0 && rm == 4 && len < max_len) {
            unsigned char sib = code[len];
            len++;
            /* SIB base=5, mod=0 -> disp32 */
            if ((sib & 0x7) == 5 && len + 4 <= max_len) len += 4;
        }
        /* Displacement */
        else if (mod == 1 && len + 1 <= max_len) len += 1;  /* disp8 */
        else if (mod == 2 && len + 4 <= max_len) len += 4;  /* disp32 */
        else if (mod == 0 && rm == 5 && len + 4 <= max_len) len += 4;  /* disp32 */
    }

    /* 5. Immediate */
    if (imm_len > 0 && len + imm_len <= max_len) {
        len += imm_len;
    }

    return len;
}

/* 计算覆盖至少 min_len 字节所需的完整指令长度 */
static int calc_hook_length(void *target, int min_len) {
    unsigned char *p = (unsigned char*)target;
    int total = 0;
    int count = 0;
    while (total < min_len && count < 16) {
        int ilen = get_instruction_length(p + total, 16);
        if (ilen <= 0) break;
        total += ilen;
        count++;
    }
    return total;
}

/* 检查目标地址开头是否包含相对跳转/调用（高风险指令） */
static int has_relative_jump(void *target, int len) {
    unsigned char *p = (unsigned char*)target;
    for (int i = 0; i < len; i++) {
        unsigned char b = p[i];
        /* E8=call rel32, E9=jmp rel32, EB=jmp rel8, E0-E3=loop/jecxz, 70-7F=jcc rel8 */
        if (b == 0xE8 || b == 0xE9 || b == 0xEB ||
            (b >= 0xE0 && b <= 0xE3) ||
            (b >= 0x70 && b <= 0x7F)) {
            return 1;
        }
        /* 0x0F 0x80-0x8F = jcc rel32 */
        if (b == 0x0F && i + 1 < len && p[i+1] >= 0x80 && p[i+1] <= 0x8F) {
            return 1;
        }
    }
    return 0;
}

/* ---------- 日志 ---------- */
static void log_msg(const char *fmt, ...) {
    if (g_log_file[0] == 0) return;
    FILE *f = fopen(g_log_file, "a");
    if (!f) return;
    EnterCriticalSection(&g_log_lock);
    SYSTEMTIME st;
    GetLocalTime(&st);
    fprintf(f, "[%02d:%02d:%02d.%03d] ", st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
    va_list args;
    va_start(args, fmt);
    vfprintf(f, fmt, args);
    va_end(args);
    fprintf(f, "\n");
    fclose(f);
    LeaveCriticalSection(&g_log_lock);
}

/* ---------- 执行Lua代码 ---------- */
static int execute_lua(const char *code) {
    if (!g_L || !g_loadstring || !g_settop) return -1;

    if (g_loadstring(g_L, code) != 0) {
        if (g_tolstring) {
            size_t len = 0;
            const char *err = g_tolstring(g_L, -1, &len);
            log_msg("[Lua] loadstring失败: %s", err ? err : "?");
        }
        g_settop(g_L, -2); /* 弹出错误 */
        return -1;
    }

    /* pcall 执行 */
    int result = real_lua_pcall(g_L, 0, 1, 0);
    if (result != 0) {
        if (g_tolstring) {
            size_t len = 0;
            const char *err = g_tolstring(g_L, -1, &len);
            log_msg("[Lua] 执行失败: %s", err ? err : "?");
        }
        g_settop(g_L, -2);
        return -1;
    }

    /* 获取返回值（支持字符串和数字） */
    g_result_is_str = 0;
    g_result_str[0] = 0;
    int ret = 0;
    if (g_lua_type) {
        int t = g_lua_type(g_L, -1);
        if (t == LUA_TSTRING && g_tolstring) {
            size_t len = 0;
            const char *s = g_tolstring(g_L, -1, &len);
            if (s && len > 0) {
                if (len >= sizeof(g_result_str)) len = sizeof(g_result_str) - 1;
                memcpy(g_result_str, s, len);
                g_result_str[len] = 0;
                g_result_is_str = 1;
                ret = 1;
            }
        } else if (t == LUA_TNUMBER && g_lua_tonumber) {
            ret = (int)g_lua_tonumber(g_L, -1);
        } else if (g_toboolean) {
            ret = g_toboolean(g_L, -1);
        }
    } else if (g_toboolean) {
        ret = g_toboolean(g_L, -1);
    }
    g_settop(g_L, -2); /* 弹出返回值 */

    return ret;
}

/* ---------- 检查并执行命令文件 ---------- */
static void check_command_file() {
    char cmd_file[MAX_PATH];
    char result_file[MAX_PATH];
    /* 使用固定路径 %LOCALAPPDATA%\woldvein_trainer\
       原因：PyInstaller onefile模式下_MEIPASS每次启动不同，
       DLL驻留游戏进程后重启修改器会导致路径不一致，改用固定路径 */
    char local_appdata[MAX_PATH];
    if (GetEnvironmentVariableA("LOCALAPPDATA", local_appdata, MAX_PATH) == 0) {
        GetTempPathA(MAX_PATH, local_appdata);
    }
    /* 确保目录存在 */
    char dir_path[MAX_PATH];
    snprintf(dir_path, MAX_PATH, "%s\\woldvein_trainer", local_appdata);
    CreateDirectoryA(dir_path, NULL);
    snprintf(cmd_file, MAX_PATH, "%s\\woldvein_trainer\\lua_cmd.txt", local_appdata);
    snprintf(result_file, MAX_PATH, "%s\\woldvein_trainer\\lua_result.txt", local_appdata);

    FILE *f = fopen(cmd_file, "rb");
    if (!f) return;

    /* 读取命令 */
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size <= 0 || size > 100000) {
        fclose(f);
        DeleteFileA(cmd_file);
        return;
    }

    char *code = (char*)malloc(size + 1);
    if (!code) { fclose(f); return; }
    size_t read_size = fread(code, 1, size, f);
    code[read_size] = 0;
    fclose(f);

    /* 跳过 UTF-8 BOM (EF BB BF) */
    char *code_start = code;
    if (read_size >= 3 &&
        (unsigned char)code[0] == 0xEF &&
        (unsigned char)code[1] == 0xBB &&
        (unsigned char)code[2] == 0xBF) {
        code_start = code + 3;
        log_msg("[Cmd] 跳过UTF-8 BOM头");
    }

    /* 解析请求ID（竞态防护）：第一行格式为 REQ_ID:xxxxxxxx */
    g_req_id[0] = 0;  /* 每次先清空 */
    if (strncmp(code_start, "REQ_ID:", 7) == 0) {
        char *newline = strchr(code_start, '\n');
        if (newline) {
            int id_len = (int)(newline - code_start - 7);
            if (id_len > 0 && id_len < (int)sizeof(g_req_id)) {
                memcpy(g_req_id, code_start + 7, id_len);
                g_req_id[id_len] = 0;
            }
            code_start = newline + 1;  /* 跳过ID行，从下一行开始执行 */
            log_msg("[Cmd] 请求ID: %s", g_req_id);
        }
    }

    /* 删除命令文件（防止重复执行） */
    DeleteFileA(cmd_file);

    /* 防御性：理论上 code_start 不会超过 code + read_size，
     * 但若 BOM/REQ_ID 解析异常导致越界，强制回退到 code 起点 */
    if (code_start > code + read_size) {
        log_msg("[Cmd] 警告：code_start 越界，回退到缓冲区起点");
        code_start = code;
    }
    int code_bytes = (int)(read_size - (code_start - code));
    if (code_bytes < 0) code_bytes = 0;
    log_msg("[Cmd] 执行Lua命令 (%d bytes)", code_bytes);

    /* 执行 */
    int ret = execute_lua(code_start);

    /* 写结果（字符串或数字），第一行是请求ID（竞态防护） */
    FILE *rf = fopen(result_file, "wb");
    if (rf) {
        if (g_req_id[0]) {
            fprintf(rf, "REQ_ID:%s\n", g_req_id);  /* 第一行：请求ID */
        }
        if (g_result_is_str && g_result_str[0]) {
            fputs(g_result_str, rf);                /* 第二行起：字符串结果 */
        } else {
            fprintf(rf, "%d", ret);                /* 第二行起：数字结果 */
        }
        fclose(rf);
    }

    free(code);
}

/* ---------- 命名管道通信（v0.4.6） ---------- */

/* 管道服务器后台线程：创建管道→等待连接→监控连接→断开后重连 */
static DWORD WINAPI pipe_server_thread(LPVOID param) {
    while (!InterlockedCompareExchange(&g_pipe_stop, 0, 0)) {
        g_pipe = CreateNamedPipeA(
            PIPE_NAME,
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            1,
            65536, 65536,
            0, NULL
        );
        if (g_pipe == INVALID_HANDLE_VALUE) {
            Sleep(1000);
            continue;
        }
        /* 阻塞等待客户端连接 */
        if (ConnectNamedPipe(g_pipe, NULL) || GetLastError() == ERROR_PIPE_CONNECTED) {
            InterlockedExchange(&g_pipe_connected, 1);
            log_msg("[Pipe] Python客户端已连接");
        }
        /* 监控连接状态，断开则重建 */
        while (g_pipe != INVALID_HANDLE_VALUE &&
               InterlockedCompareExchange(&g_pipe_connected, 0, 0) &&
               !InterlockedCompareExchange(&g_pipe_stop, 0, 0)) {
            Sleep(200);
            DWORD avail = 0;
            if (!PeekNamedPipe(g_pipe, NULL, 0, NULL, &avail, NULL)) {
                break;  /* 客户端断开 */
            }
        }
        InterlockedExchange(&g_pipe_connected, 0);
        if (g_pipe != INVALID_HANDLE_VALUE) {
            DisconnectNamedPipe(g_pipe);
            CloseHandle(g_pipe);
            g_pipe = INVALID_HANDLE_VALUE;
        }
        log_msg("[Pipe] 客户端断开，等待重连");
    }
    return 0;
}

/* 在 lua_pcall hook 中调用：检查管道是否有命令，有则执行并写回 */
static void check_named_pipe(void) {
    if (!InterlockedCompareExchange(&g_pipe_connected, 0, 0) ||
        g_pipe == INVALID_HANDLE_VALUE) {
        return;
    }
    EnterCriticalSection(&g_pipe_lock);
    DWORD avail = 0;
    if (!PeekNamedPipe(g_pipe, NULL, 0, NULL, &avail, NULL) || avail == 0) {
        LeaveCriticalSection(&g_pipe_lock);
        return;
    }
    char *buf = (char*)malloc(100001);
    if (!buf) { LeaveCriticalSection(&g_pipe_lock); return; }
    DWORD nread = 0;
    if (!ReadFile(g_pipe, buf, 100000, &nread, NULL) || nread == 0) {
        free(buf);
        LeaveCriticalSection(&g_pipe_lock);
        return;
    }
    buf[nread] = 0;

    /* 解析请求ID（与文件格式一致：REQ_ID:xxxxxxxx\n + Lua代码） */
    g_req_id[0] = 0;
    char *code_start = buf;
    if (strncmp(buf, "REQ_ID:", 7) == 0) {
        char *nl = strchr(buf, '\n');
        if (nl) {
            int idlen = (int)(nl - buf - 7);
            if (idlen > 0 && idlen < (int)sizeof(g_req_id)) {
                memcpy(g_req_id, buf + 7, idlen);
                g_req_id[idlen] = 0;
            }
            code_start = nl + 1;
        }
    }

    log_msg("[Pipe] 执行Lua命令 (%d bytes)", (int)(nread - (code_start - buf)));
    int ret = execute_lua(code_start);

    /* 写回结果：REQ_ID:xxxxxxxx\n + 结果 */
    char rbuf[65600];
    int rlen = 0;
    if (g_req_id[0]) {
        rlen = snprintf(rbuf, sizeof(rbuf), "REQ_ID:%s\n", g_req_id);
    }
    if (g_result_is_str && g_result_str[0]) {
        int slen = (int)strlen(g_result_str);
        if (rlen + slen < (int)sizeof(rbuf)) {
            memcpy(rbuf + rlen, g_result_str, slen);
            rlen += slen;
        }
    } else {
        rlen += snprintf(rbuf + rlen, sizeof(rbuf) - rlen, "%d", ret);
    }
    DWORD nwritten = 0;
    WriteFile(g_pipe, rbuf, rlen, &nwritten, NULL);

    free(buf);
    LeaveCriticalSection(&g_pipe_lock);
}

/* ---------- Hook 回调 ---------- */
static int __cdecl my_lua_pcall(lua_State *L, int nargs, int nresults, int errfunc) {
    if (!g_L) {
        g_L = L;
        log_msg("[Hook] 捕获 lua_State=%p", L);
    }

    /* 检查命令文件（频率控制：50ms间隔检查一次）
     * 使用 GetTickCount64 避免约49.7天的32位溢出 */
    static ULONGLONG last_check = 0;
    ULONGLONG now = GetTickCount64();
    if (now - last_check > 50) { /* 50ms 间隔 */
        last_check = now;
        check_command_file();
        check_named_pipe();  /* v0.4.6：命名管道通信（优先） */
    }

    return real_lua_pcall(L, nargs, nresults, errfunc);
}

/* ---------- Inline Hook 实现 ---------- */
static int install_inline_hook(void *target, void *detour, unsigned char *orig_bytes, int ncopy) {
    DWORD old_protect;
    if (!VirtualProtect(target, ncopy, PAGE_EXECUTE_READWRITE, &old_protect)) {
        log_msg("[Hook] VirtualProtect失败: %d", GetLastError());
        return -1;
    }

    /* 保存原始字节 */
    memcpy(orig_bytes, target, ncopy);

    /* 构建 trampoline（原始指令 + 跳回） */
    void *tramp = VirtualAlloc(NULL, ncopy + 14, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tramp) {
        VirtualProtect(target, ncopy, old_protect, &old_protect);
        return -1;
    }
    memcpy(tramp, target, ncopy);

    /* trampoline 末尾：jmp [rip+0]; addr */
    unsigned char jmp_back[14] = {
        0xFF, 0x25, 0x00, 0x00, 0x00, 0x00,  /* jmp [rip+0] */
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00  /* 地址 */
    };
    void *back_addr = (char*)target + ncopy;
    memcpy(jmp_back + 6, &back_addr, 8);
    memcpy((char*)tramp + ncopy, jmp_back, 14);

    /* 覆盖目标：jmp [rip+0]; detour_addr */
    unsigned char jmp_detour[14] = {
        0xFF, 0x25, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    memcpy(jmp_detour + 6, &detour, 8);
    memcpy(target, jmp_detour, 14);

    /* 填充剩余字节为 NOP */
    for (int i = 14; i < ncopy; i++) {
        ((unsigned char*)target)[i] = 0x90;
    }

    VirtualProtect(target, ncopy, old_protect, &old_protect);

    g_hook_target = target;
    g_trampoline = tramp;
    return 0;
}

/* 还原 inline hook */
static void restore_inline_hook() {
    if (!g_hook_target || !g_hooked || g_hook_length <= 0) return;
    DWORD old_protect;
    if (VirtualProtect(g_hook_target, g_hook_length, PAGE_EXECUTE_READWRITE, &old_protect)) {
        memcpy(g_hook_target, g_orig_bytes, g_hook_length);
        VirtualProtect(g_hook_target, g_hook_length, old_protect, &old_protect);
        log_msg("[Hook] lua_pcall hook 已还原 (长度=%d)", g_hook_length);
    }
    if (g_trampoline) {
        VirtualFree(g_trampoline, 0, MEM_RELEASE);
        g_trampoline = NULL;
    }
    g_hooked = 0;
    g_hook_target = NULL;
    g_hook_length = 0;
}

/* ---------- 查找 lua_pcall 地址 ---------- */
static void* find_lua_pcall() {
    g_lua_dll = GetModuleHandleA("Lua5X64.dll");
    if (!g_lua_dll) {
        log_msg("[Hook] 未找到 Lua5X64.dll");
        return NULL;
    }

    void *addr = (void*)GetProcAddress(g_lua_dll, "lua_pcall");
    if (!addr) {
        log_msg("[Hook] 未找到 lua_pcall 导出");
        return NULL;
    }

    log_msg("[Hook] lua_pcall 地址: %p", addr);
    return addr;
}

/* ---------- 初始化 Lua API ---------- */
static int init_lua_api() {
    if (!g_lua_dll) return -1;

    g_loadstring = (luaL_loadstring_t)GetProcAddress(g_lua_dll, "luaL_loadstring");
    g_tolstring = (lua_tolstring_t)GetProcAddress(g_lua_dll, "lua_tolstring");
    g_settop = (lua_settop_t)GetProcAddress(g_lua_dll, "lua_settop");
    g_toboolean = (lua_toboolean_t)GetProcAddress(g_lua_dll, "lua_toboolean");
    g_lua_type = (lua_type_t)GetProcAddress(g_lua_dll, "lua_type");
    g_lua_tonumber = (lua_tonumber_t)GetProcAddress(g_lua_dll, "lua_tonumber");

    if (!g_loadstring) log_msg("[Init] 未找到 luaL_loadstring");
    if (!g_tolstring) log_msg("[Init] 未找到 lua_tolstring");
    if (!g_settop) log_msg("[Init] 未找到 lua_settop");
    if (!g_toboolean) log_msg("[Init] 未找到 lua_toboolean");
    if (!g_lua_type) log_msg("[Init] 未找到 lua_type");
    if (!g_lua_tonumber) log_msg("[Init] 未找到 lua_tonumber");

    return (g_loadstring && g_settop) ? 0 : -1;
}

/* ---------- 安装 hook（自动计算长度+风险检查） ---------- */
static int do_install_hook(void *target) {
    /* 1. 动态计算覆盖 14 字节所需的完整指令长度 */
    int hook_len = calc_hook_length(target, 14);
    if (hook_len < 14 || hook_len > 32) {
        log_msg("[Hook] 指令长度计算失败 (%d)，放弃安装 hook（避免切断指令导致崩溃）", hook_len);
        return -1;
    }
    g_hook_length = hook_len;
    log_msg("[Hook] 计算 hook 长度: %d 字节", hook_len);

    /* 2. 检查实际 hook 范围内是否包含相对跳转（高风险） */
    if (has_relative_jump(target, hook_len)) {
        log_msg("[Hook] 警告：hook范围内包含相对跳转指令，trampoline 可能出错");
    }

    /* 3. 安装 hook */
    if (install_inline_hook(target, my_lua_pcall, g_orig_bytes, hook_len) != 0) {
        log_msg("[Hook] inline hook 安装失败");
        return -1;
    }
    real_lua_pcall = (lua_pcall_t)g_trampoline;
    g_hooked = 1;
    log_msg("[Hook] lua_pcall inline hook 安装成功 (长度=%d)", hook_len);
    return 0;
}

/* ---------- 重试 hook 线程（DllMain时LuaDLL未加载则定期重试） ---------- */
static DWORD WINAPI retry_hook_thread(LPVOID param) {
    for (int i = 0; i < 60; i++) {  /* 最多重试60次，每次1秒 */
        if (g_hooked) break;
        Sleep(1000);
        void *target = find_lua_pcall();
        if (target) {
            init_lua_api();
            if (do_install_hook(target) == 0) {
                log_msg("[Hook] 重试成功");
                break;
            }
        }
    }
    return 0;
}

/* ---------- DLL 入口 ---------- */
BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    switch (fdwReason) {
        case DLL_PROCESS_ATTACH: {
            DisableThreadLibraryCalls(hinstDLL);
            InitializeCriticalSection(&g_log_lock);
            InitializeCriticalSection(&g_pipe_lock);

            /* 设置日志路径 */
            GetModuleFileNameA(hinstDLL, g_log_file, MAX_PATH);
            char *slash = strrchr(g_log_file, '\\');
            if (slash) {
                *(slash + 1) = 0;
                strcat(g_log_file, "trainer_dll.log");
            }

            log_msg("========================================");
            log_msg("woldvein_trainer.dll v0.4.6 注入（命名管道通信）");
            log_msg("========================================");

            /* 启动命名管道服务器线程（后台等待Python连接） */
            g_pipe_thread = CreateThread(NULL, 0, pipe_server_thread, NULL, 0, NULL);
            log_msg("[Pipe] 命名管道服务器线程已启动: %s", PIPE_NAME);

            /* 查找并 hook lua_pcall */
            void *target = find_lua_pcall();
            if (target) {
                init_lua_api();
                do_install_hook(target);
            } else {
                log_msg("[Hook] 未找到lua_pcall，启动重试线程（最多60秒）");
                CreateThread(NULL, 0, retry_hook_thread, NULL, 0, NULL);
            }
            break;
        }
        case DLL_PROCESS_DETACH: {
            /* 停止命名管道线程 */
            InterlockedExchange(&g_pipe_stop, 1);
            if (g_pipe != INVALID_HANDLE_VALUE) {
                DisconnectNamedPipe(g_pipe);
                CloseHandle(g_pipe);
                g_pipe = INVALID_HANDLE_VALUE;
            }
            if (g_pipe_thread) {
                WaitForSingleObject(g_pipe_thread, 2000);
                CloseHandle(g_pipe_thread);
                g_pipe_thread = NULL;
            }
            DeleteCriticalSection(&g_pipe_lock);
            restore_inline_hook();
            log_msg("woldvein_trainer.dll 卸载");
            DeleteCriticalSection(&g_log_lock);
            break;
        }
    }
    return TRUE;
}

