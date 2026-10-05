"""
woldvein Trainer v0.4.6 - Lua 探查器

探查游戏中的 Lua 环境，列出全局变量、函数、表结构，帮助逆向和调试。

功能：
    1. 列出 _G 中的所有全局变量
    2. 递归探查表结构
    3. 查找特定函数/变量
    4. 获取函数信息（参数、upvalue）
    5. 执行 Lua 代码并返回结果

依赖：
    - DLL 已注入，Lua 执行通道可用（命名管道或文件通信）

使用方式：
    from .lua_explorer import LuaExplorer
    explorer = LuaExplorer()
    globals_list = explorer.list_globals()
    table_info = explorer.explore_table("g_TalentManager")
"""
import json
import re

from .logger import log, log_success, log_error, log_warning


class LuaExplorer:
    """Lua 环境探查器"""

    def __init__(self, lua_executor=None):
        """
        参数：
            lua_executor: Lua 执行函数，接受 Lua 代码字符串，返回 (success, result)
                         如果为 None，使用默认的 execute_lua 函数
        """
        if lua_executor is None:
            from .lua_engine import execute_lua
            self._execute = execute_lua
        else:
            self._execute = lua_executor

    def execute_lua(self, code):
        """执行 Lua 代码。

        返回：
            (success, result)
        """
        try:
            return self._execute(code)
        except Exception as e:
            return False, str(e)

    def list_globals(self, filter_pattern=None):
        """列出 _G 中的所有全局变量。

        参数：
            filter_pattern: 过滤正则表达式（可选）

        返回：
            [{"name": str, "type": str}, ...]
        """
        lua_code = '''
        local results = {}
        for k, v in pairs(_G) do
            if type(k) == "string" then
                table.insert(results, k .. "\\t" .. type(v))
            end
        end
        table.sort(results)
        return table.concat(results, "\\n")
        '''
        success, result = self.execute_lua(lua_code)
        if not success:
            log_error(f"[Lua探查] 列出全局变量失败: {result}")
            return []

        items = []
        for line in str(result).split("\n"):
            line = line.strip()
            if not line or "\t" not in line:
                continue
            name, typ = line.split("\t", 1)
            if filter_pattern and not re.search(filter_pattern, name, re.IGNORECASE):
                continue
            items.append({"name": name, "type": typ})

        log(f"[Lua探查] 找到 {len(items)} 个全局变量")
        return items

    def explore_table(self, table_name, max_depth=2, max_items=100):
        """递归探查表结构。

        参数：
            table_name: 表名（如 "g_TalentManager"）
            max_depth: 最大递归深度
            max_items: 每层最大条目数

        返回：
            {"name": str, "type": str, "fields": [...]}
        """
        lua_code = f'''
        local function explore(tbl, name, depth, maxDepth, maxItems)
            if depth > maxDepth then return end
            local results = {{}}
            local count = 0
            for k, v in pairs(tbl) do
                count = count + 1
                if count > maxItems then
                    table.insert(results, "... (more)")
                    break
                end
                local kstr = tostring(k)
                local vtype = type(v)
                if vtype == "table" then
                    table.insert(results, kstr .. " = {{table}}")
                elseif vtype == "function" then
                    table.insert(results, kstr .. " = function")
                elseif vtype == "userdata" then
                    table.insert(results, kstr .. " = userdata")
                else
                    table.insert(results, kstr .. " = " .. tostring(v))
                end
            end
            return table.concat(results, "\\n")
        end

        local target = {table_name}
        if target == nil then
            return "ERROR: table not found"
        end
        if type(target) ~= "table" then
            return "ERROR: not a table, type=" .. type(target)
        end
        return explore(target, "{table_name}", 1, {max_depth}, {max_items})
        '''

        success, result = self.execute_lua(lua_code)
        if not success:
            log_error(f"[Lua探查] 探查表 {table_name} 失败: {result}")
            return {"name": table_name, "type": "error", "error": str(result)}

        fields = []
        for line in str(result).split("\n"):
            line = line.strip()
            if not line or " = " not in line:
                continue
            name, value = line.split(" = ", 1)
            fields.append({"name": name, "value": value})

        log(f"[Lua探查] 表 {table_name} 有 {len(fields)} 个字段")
        return {
            "name": table_name,
            "type": "table",
            "fields": fields,
        }

    def get_function_info(self, func_name):
        """获取函数信息。

        参数：
            func_name: 函数名（如 "g_TalentManager.AddExp"）

        返回：
            {"name": str, "type": str, "info": {...}}
        """
        lua_code = f'''
        local func = {func_name}
        if func == nil then
            return "ERROR: function not found"
        end
        if type(func) ~= "function" then
            return "ERROR: not a function, type=" .. type(func)
        end

        local info = debug.getinfo(func, "Slu")
        local result = {{}}
        result.source = info.source or "unknown"
        result.linedefined = info.linedefined or -1
        result.lastlinedefined = info.lastlinedefined or -1
        result.nparams = info.nparams or 0
        result.isvararg = info.isvararg or false
        result.nups = info.nups or 0
        result.what = info.what or "unknown"

        -- 获取 upvalue 名称
        local upvalues = {{}}
        for i = 1, info.nups do
            local name, value = debug.getupvalue(func, i)
            if name then
                table.insert(upvalues, name .. "=" .. type(value))
            end
        end
        result.upvalues = table.concat(upvalues, ", ")

        return result.source .. "\\n" ..
               "line:" .. result.linedefined .. "-" .. result.lastlinedefined .. "\\n" ..
               "params:" .. result.nparams .. (result.isvararg and "+" or "") .. "\\n" ..
               "upvalues:" .. result.nups .. "\\n" ..
               "upvalue_names:" .. result.upvalues .. "\\n" ..
               "what:" .. result.what
        '''

        success, result = self.execute_lua(lua_code)
        if not success:
            return {"name": func_name, "type": "error", "error": str(result)}

        info = {}
        for line in str(result).split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()

        return {"name": func_name, "type": "function", "info": info}

    def search_globals(self, keyword):
        """搜索包含关键词的全局变量。

        参数：
            keyword: 搜索关键词

        返回：
            [{"name": str, "type": str}, ...]
        """
        return self.list_globals(filter_pattern=re.escape(keyword))

    def get_value(self, var_name):
        """获取变量的值（字符串表示）。

        参数：
            var_name: 变量名

        返回：
            (success, value_str)
        """
        lua_code = f'''
        local val = {var_name}
        if val == nil then return "nil" end
        if type(val) == "table" then
            return "table: " .. tostring(val)
        elseif type(val) == "function" then
            return "function: " .. tostring(val)
        elseif type(val) == "userdata" then
            return "userdata: " .. tostring(val)
        else
            return tostring(val)
        end
        '''
        return self.execute_lua(lua_code)

    def call_function(self, func_name, args=None):
        """调用 Lua 函数并返回结果。

        参数：
            func_name: 函数名
            args: 参数列表（可选）

        返回：
            (success, result)
        """
        args_str = ""
        if args:
            args_str = ", ".join(f'"{a}"' if isinstance(a, str) else str(a) for a in args)

        lua_code = f'''
        local ok, result = pcall({func_name}, {args_str})
        if not ok then
            return "ERROR: " .. tostring(result)
        end
        if result == nil then return "nil" end
        return tostring(result)
        '''
        return self.execute_lua(lua_code)

    def list_methods(self, table_name):
        """列出表中的所有方法（function 类型的字段）。

        参数：
            table_name: 表名

        返回：
            [method_name, ...]
        """
        info = self.explore_table(table_name)
        if info.get("type") == "error":
            return []
        methods = [f["name"] for f in info.get("fields", []) if "function" in f.get("value", "")]
        log(f"[Lua探查] 表 {table_name} 有 {len(methods)} 个方法")
        return methods

    def dump_environment(self, output_file=None):
        """导出整个 Lua 环境概览。

        参数：
            output_file: 输出文件路径（可选）

        返回：
            环境概览文本
        """
        globals_list = self.list_globals()

        lines = []
        lines.append("=" * 60)
        lines.append("Lua Environment Dump")
        lines.append(f"Total globals: {len(globals_list)}")
        lines.append("=" * 60)
        lines.append("")

        # 按类型分组
        by_type = {}
        for item in globals_list:
            typ = item["type"]
            if typ not in by_type:
                by_type[typ] = []
            by_type[typ].append(item["name"])

        for typ in sorted(by_type.keys()):
            lines.append(f"--- {typ} ({len(by_type[typ])}) ---")
            for name in sorted(by_type[typ]):
                lines.append(f"  {name}")
            lines.append("")

        result = "\n".join(lines)

        if output_file:
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(result)
                log_success(f"[Lua探查] 环境已导出到: {output_file}")
            except Exception as e:
                log_error(f"[Lua探查] 导出失败: {e}")

        return result


def quick_explore(table_name):
    """便捷函数：快速探查一个表。"""
    explorer = LuaExplorer()
    return explorer.explore_table(table_name)
