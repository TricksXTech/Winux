-- TricksXTech Clink Integration
-- Provides live TrueColor prompt, Git status, Python/Node env, duration, exit code,
-- and theme-synced Clink syntax/autosuggestion colors in CMD.

local function get_tx_root()
    local env_root = os.getenv("TX_ROOT")
    if env_root and env_root ~= "" then
        return env_root
    end
    local src = debug.getinfo(1, "S").source
    if src:sub(1, 1) == "@" then src = src:sub(2) end
    local dir = src:match("^(.*)[/\\]src[/\\]cmd[/\\][^/\\]+$")
    return dir or "d:\\Terminal"
end

-- Minimal pure-Lua JSON decoder
local json_decode
do
    local function skip_ws(s, i)
        return s:match("^%s*()", i)
    end
    local parse_val
    local function parse_str(s, i)
        i = i + 1
        local out = {}
        while i <= #s do
            local c = s:sub(i, i)
            if c == '"' then return table.concat(out), i + 1 end
            if c == "\\" then
                local n = s:sub(i + 1, i + 1)
                local map = { ['"']='"', ["\\"]="\\", ["/"]="/", b="\b", f="\f", n="\n", r="\r", t="\t" }
                if map[n] then
                    out[#out + 1] = map[n]
                    i = i + 2
                elseif n == "u" then
                    local hex = s:sub(i + 2, i + 5)
                    local cp = tonumber(hex, 16) or 32
                    if cp < 128 then out[#out + 1] = string.char(cp) else out[#out + 1] = "?" end
                    i = i + 6
                else
                    out[#out + 1] = n
                    i = i + 2
                end
            else
                out[#out + 1] = c
                i = i + 1
            end
        end
        return table.concat(out), i
    end
    local function parse_arr(s, i)
        i = skip_ws(s, i + 1)
        local res = {}
        if s:sub(i, i) == "]" then return res, i + 1 end
        while i <= #s do
            local v; v, i = parse_val(s, i)
            res[#res + 1] = v
            i = skip_ws(s, i)
            if s:sub(i, i) == "," then i = skip_ws(s, i + 1)
            elseif s:sub(i, i) == "]" then return res, i + 1
            else break end
        end
        return res, i
    end
    local function parse_obj(s, i)
        i = skip_ws(s, i + 1)
        local res = {}
        if s:sub(i, i) == "}" then return res, i + 1 end
        while i <= #s do
            local k; k, i = parse_str(s, i)
            i = skip_ws(s, i)
            if s:sub(i, i) == ":" then i = skip_ws(s, i + 1) end
            local v; v, i = parse_val(s, i)
            res[k] = v
            i = skip_ws(s, i)
            if s:sub(i, i) == "," then i = skip_ws(s, i + 1)
            elseif s:sub(i, i) == "}" then return res, i + 1
            else break end
        end
        return res, i
    end
    parse_val = function(s, i)
        i = skip_ws(s, i)
        local c = s:sub(i, i)
        if c == '"' then return parse_str(s, i)
        elseif c == "{" then return parse_obj(s, i)
        elseif c == "[" then return parse_arr(s, i)
        elseif s:sub(i, i + 3) == "true" then return true, i + 4
        elseif s:sub(i, i + 4) == "false" then return false, i + 5
        elseif s:sub(i, i + 3) == "null" then return nil, i + 4
        else
            local num = s:match("^-?%d+%.?%d*[eE]?[+-]?%d*", i)
            if num and #num > 0 then return tonumber(num), i + #num end
            return nil, i + 1
        end
    end
    json_decode = function(s)
        if not s or s == "" then return nil end
        if s:sub(1, 3) == "\239\187\191" then s = s:sub(4) end
        local ok, val = pcall(parse_val, s, 1)
        if ok then return val end
        return nil
    end
end

local function read_file(path)
    local f = io.open(path, "rb")
    if not f then return nil end
    local data = f:read("*a")
    f:close()
    return data
end

local function deep_merge(base, over)
    local out = {}
    for k, v in pairs(base or {}) do out[k] = v end
    for k, v in pairs(over or {}) do
        if type(v) == "table" and type(out[k]) == "table" then
            out[k] = deep_merge(out[k], v)
        else
            out[k] = v
        end
    end
    return out
end

local function hex_rgb(hex)
    hex = (hex or "#FFFFFF"):gsub("^#", "")
    local r = tonumber(hex:sub(1, 2), 16) or 255
    local g = tonumber(hex:sub(3, 4), 16) or 255
    local b = tonumber(hex:sub(5, 6), 16) or 255
    return r, g, b
end

local function ansi_fg(hex)
    local r, g, b = hex_rgb(hex)
    return string.format("\x1b[38;2;%d;%d;%dm", r, g, b)
end

local function ansi_bg(hex)
    local r, g, b = hex_rgb(hex)
    return string.format("\x1b[48;2;%d;%d;%dm", r, g, b)
end

local function sgr_rgb(hex)
    local r, g, b = hex_rgb(hex)
    return string.format("38;2;%d;%d;%d", r, g, b)
end

local function load_state()
    local root = get_tx_root()
    local def = json_decode(read_file(root .. "\\config\\defaults.json")) or {}
    local usr = json_decode(read_file(root .. "\\config\\user.json")) or {}
    local cfg = deep_merge(def, usr)
    local themes_doc = json_decode(read_file(root .. "\\themes\\themes.json")) or {}
    local themes = themes_doc.themes or {}
    local theme = themes[cfg.theme] or themes["tokyo-night"]
    return cfg, theme
end

local function short_path(cwd)
    local home = os.getenv("USERPROFILE") or ""
    local disp = cwd
    if home ~= "" and disp:sub(1, #home):lower() == home:lower() then
        disp = "~" .. disp:sub(#home + 1)
    end
    disp = disp:gsub("\\", "/")
    local parts = {}
    for p in disp:gmatch("[^/]+") do parts[#parts + 1] = p end
    if #parts > 4 then
        return parts[1] .. "/…/" .. parts[#parts - 1] .. "/" .. parts[#parts]
    end
    return disp
end

local function get_git_info(cwd)
    local dir = cwd
    local found = false
    while dir and dir ~= "" do
        if os.isdir(dir .. "\\.git") or os.isfile(dir .. "\\.git") then
            found = true
            break
        end
        local parent = path.getdirectory(dir)
        if not parent or parent == dir then break end
        dir = parent
    end
    if not found then return nil end

    local p = io.popen('git -C "' .. cwd .. '" status --porcelain=v2 --branch 2>nul')
    if not p then return nil end
    local branch, oid = "", ""
    local ahead, behind, staged, modified, untracked, conflicts = 0, 0, 0, 0, 0, 0
    for line in p:lines() do
        local h = line:match("^# branch%.head (.+)$")
        if h then branch = h
        elseif line:match("^# branch%.oid ") then
            oid = line:match("^# branch%.oid ([0-9a-f]+)") or ""
        elseif line:match("^# branch%.ab ") then
            local a, b = line:match("^# branch%.ab %+(%d+) %-(%d+)")
            if a then ahead = tonumber(a) or 0 end
            if b then behind = tonumber(b) or 0 end
        elseif line:sub(1, 2) == "1 " or line:sub(1, 2) == "2 " then
            local xy = line:sub(3, 4)
            if xy:sub(1, 1) ~= "." then staged = staged + 1 end
            if xy:sub(2, 2) ~= "." then modified = modified + 1 end
        elseif line:sub(1, 2) == "u " then
            conflicts = conflicts + 1
        elseif line:sub(1, 2) == "? " then
            untracked = untracked + 1
        end
    end
    p:close()
    if branch == "(detached)" or branch == "" then
        branch = oid ~= "" and ("@" .. oid:sub(1, 7)) or "detached"
    end
    return {
        branch = branch, ahead = ahead, behind = behind,
        staged = staged, modified = modified, untracked = untracked, conflicts = conflicts,
        dirty = (staged + modified + untracked + conflicts) > 0
    }
end

local cmd_start_time = nil
local last_duration_ms = 0
local last_theme_synced = nil

clink.onbeginedit(function()
    if cmd_start_time then
        last_duration_ms = (os.clock() - cmd_start_time) * 1000
        cmd_start_time = nil
    else
        last_duration_ms = 0
    end
    local cfg, theme = load_state()
    if theme and theme.id ~= last_theme_synced and settings and settings.set then
        last_theme_synced = theme.id
        local ui = theme.ui
        pcall(settings.set, "color.cmd", sgr_rgb(ui.primary))
        pcall(settings.set, "color.arg", sgr_rgb(ui.text))
        pcall(settings.set, "color.flag", sgr_rgb(ui.accent))
        pcall(settings.set, "color.suggestion", sgr_rgb(ui.muted))
        pcall(settings.set, "color.input", sgr_rgb(ui.text))
        pcall(settings.set, "color.unrecognized", sgr_rgb(ui.error))
        pcall(settings.set, "color.executable", sgr_rgb(theme.palette.green))
    end
end)

clink.onendedit(function(line)
    if line and line:match("%S") then
        cmd_start_time = os.clock()
    else
        cmd_start_time = nil
    end
end)

local tx_prompt = clink.promptfilter(30)

function tx_prompt:filter(prompt_str)
    local cfg, theme = load_state()
    if not theme then return prompt_str end
    local ui = theme.ui
    local style = cfg.style or "capsule"
    local segs_cfg = cfg.segments or {}
    local cwd = os.getcwd()
    local sp = short_path(cwd)
    local git = (segs_cfg.git ~= false) and get_git_info(cwd) or nil
    local exit_code = (os.geterrorlevel and os.geterrorlevel()) or 0
    local is_nerd = (cfg.icons == "nerd")
    local rst = "\x1b[0m"
    local bold = "\x1b[1m"
    local chev_clr = (exit_code ~= 0) and ui.error or ui.primary

    local leaf = cwd:match("([^\\/]+)$") or cwd
    local title = git and string.format("CMD • %s (%s)", leaf, git.branch) or ("CMD • " .. leaf)
    local osc = "\x1b]0;" .. title .. "\x1b\\\x1b]9;9;\"" .. cwd .. "\"\x1b\\"

    if style == "minimal" then
        local g_part = ""
        if git then
            local gc = git.dirty and ui.warning or ui.success
            g_part = " " .. ansi_fg(gc) .. "(" .. git.branch .. (git.dirty and "*" or "") .. ")" .. rst
        end
        local e_part = (exit_code ~= 0) and (" " .. ansi_fg(ui.error) .. bold .. "[" .. exit_code .. "]" .. rst) or ""
        return osc .. ansi_fg(ui.accent) .. bold .. sp .. rst .. g_part .. e_part .. " " .. ansi_fg(chev_clr) .. bold .. "❯" .. rst .. " ", false
    end

    if style == "classic" then
        local t = (segs_cfg.clock ~= false) and (ansi_fg(ui.muted) .. "[" .. os.date("%H:%M:%S") .. "] " .. rst) or ""
        local uh = ansi_fg(ui.primary) .. bold .. (os.getenv("USERNAME") or "user") .. "@" .. (os.getenv("COMPUTERNAME") or "PC") .. " " .. rst
        local gp = ""
        if git then
            local gc = git.dirty and ui.warning or ui.success
            gp = ansi_fg(gc) .. " [" .. git.branch .. (git.dirty and " *" or "") .. "]" .. rst
        end
        local ep = (exit_code ~= 0) and (ansi_fg(ui.error) .. bold .. " [exit:" .. exit_code .. "]" .. rst) or ""
        return osc .. t .. uh .. ansi_fg(ui.accent) .. bold .. sp .. rst .. gp .. ep .. "\n" .. ansi_fg(chev_clr) .. bold .. "╰─❯ " .. rst, false
    end

    local badges = {}
    badges[#badges + 1] = { text = "CMD", fg = ui.darkText, bg = ui.primary, acc = ui.primary, bold = true }
    if segs_cfg.path ~= false then
        badges[#badges + 1] = { text = sp, fg = ui.accent, bg = ui.surface, acc = ui.accent, bold = true }
    end
    if git then
        local gt = git.branch
        if git.ahead > 0 then gt = gt .. " ↑" .. git.ahead end
        if git.behind > 0 then gt = gt .. " ↓" .. git.behind end
        if git.dirty then
            local dp = {}
            if git.staged > 0 then dp[#dp + 1] = "+" .. git.staged end
            if git.modified > 0 then dp[#dp + 1] = "~" .. git.modified end
            if git.untracked > 0 then dp[#dp + 1] = "?" .. git.untracked end
            gt = gt .. " " .. table.concat(dp, " ")
        else
            gt = gt .. " ✓"
        end
        local gc = (git.conflicts > 0) and ui.error or (git.dirty and ui.warning or ui.success)
        badges[#badges + 1] = { text = gt, fg = ui.darkText, bg = gc, acc = gc, bold = true }
    end
    local venv = os.getenv("VIRTUAL_ENV")
    if segs_cfg.env ~= false and venv and venv ~= "" then
        local vname = venv:match("([^\\/]+)$") or venv
        badges[#badges + 1] = { text = "py:" .. vname, fg = ui.warning, bg = ui.surfaceAlt, acc = ui.warning, bold = false }
    end
    if segs_cfg.duration ~= false and last_duration_ms >= 150 then
        local ds = (last_duration_ms < 1000) and string.format("%dms", math.floor(last_duration_ms)) or string.format("%.2fs", last_duration_ms / 1000)
        badges[#badges + 1] = { text = "◷ " .. ds, fg = ui.warning, bg = ui.surfaceAlt, acc = ui.warning, bold = false }
    end
    if segs_cfg.exitCode ~= false and exit_code ~= 0 then
        badges[#badges + 1] = { text = "✘ " .. exit_code, fg = ui.darkText, bg = ui.error, acc = ui.error, bold = true }
    end

    local out = { osc }
    if style == "powerline" and is_nerd then
        for i, b in ipairs(badges) do
            if i == 1 then out[#out + 1] = ansi_fg(b.bg) .. "\xee\x82\xb6" end -- 
            out[#out + 1] = ansi_bg(b.bg) .. ansi_fg(b.fg) .. (b.bold and bold or "") .. " " .. b.text .. " " .. rst
            if i < #badges then
                out[#out + 1] = ansi_fg(b.bg) .. ansi_bg(badges[i + 1].bg) .. "\xee\x82\xb0" .. rst -- 
            else
                out[#out + 1] = ansi_fg(b.bg) .. "\xee\x82\xb0" .. rst
            end
        end
    else
        for i, b in ipairs(badges) do
            if i > 1 then out[#out + 1] = " " end
            if is_nerd then
                out[#out + 1] = ansi_fg(b.bg) .. "\xee\x82\xb6" .. ansi_bg(b.bg) .. ansi_fg(b.fg) .. (b.bold and bold or "") .. " " .. b.text .. " " .. rst .. ansi_fg(b.bg) .. "\xee\x82\xb4" .. rst
            else
                out[#out + 1] = ansi_fg(ui.border) .. "[" .. ansi_fg(b.acc) .. (b.bold and bold or "") .. b.text .. rst .. ansi_fg(ui.border) .. "]" .. rst
            end
        end
    end
    if segs_cfg.clock ~= false then
        out[#out + 1] = " " .. ansi_fg(ui.muted) .. os.date("%H:%M:%S") .. rst
    end
    out[#out + 1] = "\n" .. ansi_fg(chev_clr) .. bold .. "╰─❯ " .. rst
    return table.concat(out), false
end
