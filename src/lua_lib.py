"""
woldvein Trainer v0.3 - Lua 辅助库

功能说明：
    在游戏 Lua 环境注入的公共辅助函数，供各 Lua 脚本片段复用：

    __trainer_emit(event, data, provider)
        统一的 UI 事件触发。原代码混用 g_LHBUI:Emit(...)（该全局对象并不存在）
        与 g_LHBUIProvider:EmitTo(provider, event, data)，前者静默失效。
        本函数统一走 EmitTo，并返回是否成功。

    __trainer_hook(cls, method) / __trainer_unhook(cls, method) / __trainer_is_hooked(cls, method)
        统一的方法 hook / 还原。原代码用 cls.__cm_orig_<Method> 保存原方法，
        各处命名不统一，关闭时容易漏还原（还原失败 → 关闭创造模式后仍生效）。

注入时机：
    在 DLL Hook 就绪、Lua 通道打通后立即注入（见 main_gui._wait_dll_ready /
    _wait_dll_ready_silent）。注入后，调用 __trainer_emit 的脚本才可正常工作。

    注：hook 迁移（__trainer_hook/unhook）需逐对迁移并在实机验证后切换，
    当前保留原 __cm_orig_* 写法，本模块的 hook 辅助函数为迁移就绪状态。
"""

LUA_TRAINER_LIB = r"""
-- 统一 UI 事件触发：g_LHBUIProvider:EmitTo(provider, event, data)
-- 返回 true 表示成功触发
function __trainer_emit(event, data, provider)
    if not g_LHBUIProvider or not g_LHBUIEvents then return false end
    provider = provider or "LSystemProvider"
    local ok = pcall(function()
        g_LHBUIProvider:EmitTo(provider, event, data)
    end)
    return ok
end

-- 统一 hook：保存原方法到 __trainer_orig_<method>，可重复调用（幂等）
function __trainer_hook(cls, method)
    if not cls or type(cls[method]) ~= "function" then return false end
    local key = "__trainer_orig_" .. method
    if cls[key] then return true end
    cls[key] = cls[method]
    return true
end

-- 统一还原：把 __trainer_orig_<method> 写回，并清除标记
function __trainer_unhook(cls, method)
    if not cls then return false end
    local key = "__trainer_orig_" .. method
    if not cls[key] then return false end
    cls[method] = cls[key]
    cls[key] = nil
    return true
end

-- 查询是否已 hook
function __trainer_is_hooked(cls, method)
    if not cls then return false end
    return cls["__trainer_orig_" .. method] ~= nil
end

-- 通用对象导出：把 table / userdata（含 tolua 绑定方法）的字段与方法列成文本行
-- 用法：local lines = {}; __trainer_dump(g_LMarketManager, lines); return table.concat(lines, "\n")
function __trainer_dump(obj, lines, prefix)
    prefix = prefix or "  "
    if obj == nil then table.insert(lines, prefix .. "(nil)"); return end
    local t = type(obj)
    table.insert(lines, prefix .. "type=" .. t)
    local seen = {}
    if t == "table" then
        for k, v in pairs(obj) do
            seen[k] = true
            local vs = type(v)
            if vs == "function" then
                table.insert(lines, prefix .. "[方法] " .. tostring(k))
            elseif vs == "number" or vs == "string" or vs == "boolean" then
                table.insert(lines, prefix .. tostring(k) .. " = " .. tostring(v))
            else
                table.insert(lines, prefix .. tostring(k) .. " (" .. vs .. ")")
            end
        end
    end
    local mt = getmetatable(obj)
    if mt and type(mt) == "table" then
        local idx = mt.__index
        if type(idx) == "table" then
            local names, fields = {}, {}
            for k, v in pairs(idx) do
                if not seen[k] then
                    if type(v) == "function" then
                        names[#names + 1] = tostring(k)
                    elseif type(v) == "number" or type(v) == "string" or type(v) == "boolean" then
                        fields[#fields + 1] = tostring(k) .. "=" .. tostring(v)
                    end
                end
            end
            table.sort(names)
            table.sort(fields)
            if #names > 0 then
                table.insert(lines, prefix .. "绑定方法: " .. table.concat(names, ", "))
            end
            if #fields > 0 then
                table.insert(lines, prefix .. "绑定字段: " .. table.concat(fields, ", "))
            end
        end
    end
    -- Lua 类对象：方法在 obj.class（tolua 风格）
    if t == "table" and type(obj.class) == "table" then
        local cnames = {}
        for k, v in pairs(obj.class) do
            if type(v) == "function" and not seen[k] then cnames[#cnames + 1] = tostring(k) end
        end
        table.sort(cnames)
        if #cnames > 0 then
            table.insert(lines, prefix .. "class 方法: " .. table.concat(cnames, ", "))
        end
    end
end

g_trainer_lib_loaded = true
return 1
"""
