---
--- Date         : 2023-01-10 17:39:51
--- Author       : LICHAO7
--- Description  : LXGAgentManager
---

--- @type LXGAgentBase
LOG_I("[PROBE-LOAD] sim_common/script/core/xgagent/xgagent_manager.lua loaded");
local XGAgentBase = ImportScript("script/core/xgagent/xgagent_base.lua").LXGAgentBase;

--- @class LLoginDataStruct
local LLoginDataStruct = class("LoginDataStruct");
function LLoginDataStruct:ctor(strRawJson)
    self:Update(strRawJson or "{}");
end
function LLoginDataStruct:Update(strRawJson)
    local tbRawJsonData = JSON.Loads(strRawJson, {});
    tbRawJsonData.rawinfo = tbRawJsonData.rawinfo or {};
    self.bLogin       = not not tbRawJsonData.bLogin;
    self.code         = tbRawJsonData.code or "";
    self.msg          = tbRawJsonData.msg or "";
    self.channel_code = tbRawJsonData.channel_code or "";
    self.authToken    = tbRawJsonData.rawinfo.authToken or "";
    self.channelId    = tbRawJsonData.rawinfo.channelId or "";
    self.deviceId     = tbRawJsonData.rawinfo.deviceId or "";
    self.extData      = JSON.Loads(tbRawJsonData.rawinfo.extData or "{}", {});
    self.name         = tbRawJsonData.rawinfo.name or "offlineuser";
    self.planId       = tbRawJsonData.rawinfo.planId or "";
    self.sign         = tbRawJsonData.rawinfo.sign or "";
    self.ts           = tbRawJsonData.rawinfo.ts or "";
    self.uid          = tbRawJsonData.rawinfo.uid or "offlineuser";
    self.xgAppId      = tbRawJsonData.rawinfo.xgAppId or "";
end

function LLoginDataStruct:IsValidUser()
    return self.bLogin
        and not string.isempty(self.authToken)
        and not string.isempty(self.channelId)
        and not string.isempty(self.sign)
        and not string.isempty(self.ts)
        and not string.isempty(self.uid)
end

---
--- @class LXGAgentManager:LXGAgentBase
---
local LXGAgentManager = class("LXGAgentManager", XGAgentBase);
LXGAgentManager.AFLAG = true; -- woldvein -- Skip Login GM flag
LXGAgentManager.IXGSDKChannelType = IXGSDKChannelType;

function LXGAgentManager:ctor()
    self.fnLoginCallbackFunc = nil;
    self.fnLogoutCallbackFunc = nil;
    self.fnAccountInfoCallbackFunc = nil;
    self.fnGetPurchasedItemsCallbackFunc = nil;
    self.fnDirtyWordsFilterCallbackFunc = nil;
    self.tbLoginCallbackCtx = nil;
    self.tbLogoutCallbackCtx = nil;
    self.tbAccountInfoCallbackCtx = nil;
    self.tbGetPurchasedItemsCallbackCtx = nil;
    self.tbDirtyWordsFilterCallbackCtx = nil;
    self.strRawLoginJsonData = "{}";
    self.LoginData = LLoginDataStruct:new(self.strRawLoginJsonData); --- @type LLoginDataStruct
    self.bInited = false;
end

function LXGAgentManager:dtor()
end

---
--- 获取金山SDK渠道的SDKAgent接口单例
--- @return XGSDKAgentManager
---
function LXGAgentManager:getAgent()
    return GetXGSDKAgentManager();
end

---
--- 获取渠道类型配置
--- @return number 渠道ID
--- @return boolean 是否发布
---
function LXGAgentManager:getChannelFromConf()
    local cfg = LIniFile:new("configs/config.cfg");
    cfg:parse();
    local nChannel = cfg:GetValue("Misc", "channel") or tostring(IXGSDKChannelType.XGJinShanWithSteam);
    nChannel = tonumber(nChannel);

    local bPublish = cfg:GetValue("Misc", "publish") ~= "0";
    return nChannel, bPublish;
end

function LXGAgentManager:OnBeforeInit()
    if self.bInited then
        return;
    end
    local Define = self.LXGAgentDefine;
    g_EventDispatcherManager:AddEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_INIT, self._onInit, self);
    g_EventDispatcherManager:AddEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_EXIT, self._onExit, self);
    g_EventDispatcherManager:AddEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_LOGIN, self._onLogin, self);
    g_EventDispatcherManager:AddEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_LOGOUT, self._onLogout, self);
    g_EventDispatcherManager:AddEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_GETACCOUNTINFO, self._onGetAccountInfo, self);
    g_EventDispatcherManager:AddEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_DIRTY_WORDS_FILTER, self._onGetFilterdDirtyWords, self);
    g_EventDispatcherManager:AddEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_GET_PURCHASED_CONTENT, self._onGetXGPurchasedItems, self);
    g_EventDispatcherManager:AddEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_CHANNEL_EXIT, self._onNoChannelExit, self);
    local pAgent = self:getAgent();
    if pAgent then
        local pOption = pAgent:GetOptions();
        local eChannelType, bPublish = self:getChannelFromConf();
        Define.XGSDKChannelType = eChannelType;
        Define.XGSDKCheck       = bPublish;
        Define.SteamAppID       = Define.SteamAppIDEnum[eChannelType];
        pOption.eChannelType    = tonumber(eChannelType);
        pOption.pcszGameVersion = Define.GameVersion;
        -- 对于测试环境需要动态生成steam_appid.txt才可以直接启动测试环境下的客户端并连接steam，否则无法连接steam
        if (Define.XGSDKChannelType == IXGSDKChannelType.XGJinShanWithSteam or
            Define.XGSDKChannelType == IXGSDKChannelType.XGJinShanWithSteamByDebug or
            Define.XGSDKChannelType == IXGSDKChannelType.XGJinShanWithSteamV2 or
            Define.XGSDKChannelType == IXGSDKChannelType.XGJinShanWithSteamV2ByDebug or
            Define.XGSDKChannelType == IXGSDKChannelType.XGSteam or
            Define.XGSDKChannelType == IXGSDKChannelType.XGSteamByDebug)
        then
            local strSteamAppIDTextFile = FS.Path.Join(FS.GetCwd(), "bin64", "steam_appid.txt");
            if not Define.XGSDKCheck then
                local lFile = FS.Open(strSteamAppIDTextFile, "w+");
                if lFile and lFile:Valid() then
                    lFile:Write(Define.SteamAppID);
                end
                lFile:Close();
                lFile = nil;
            elseif FS.Path.Exists(strSteamAppIDTextFile) then
                FS.RemoveFile(strSteamAppIDTextFile);
            end
        end
        pAgent:Init(pOption);
    end
    local bOk = not not pAgent and pAgent:Usable();
    LOG_I(string.format("[XGAgent] OnBeforeInit %s", tostring(bOk)));
end

function LXGAgentManager:OnAfterInit()
end

function LXGAgentManager:OnUnInit()
    local Define = self.LXGAgentDefine;
    g_EventDispatcherManager:RemoveEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_INIT, self._onInit, self);
    g_EventDispatcherManager:RemoveEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_EXIT, self._onExit, self);
    g_EventDispatcherManager:RemoveEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_LOGIN, self._onLogin, self);
    g_EventDispatcherManager:RemoveEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_LOGOUT, self._onLogout, self);
    g_EventDispatcherManager:RemoveEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_GETACCOUNTINFO, self._onGetAccountInfo, self);
    g_EventDispatcherManager:RemoveEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_DIRTY_WORDS_FILTER, self._onGetFilterdDirtyWords, self);
    g_EventDispatcherManager:RemoveEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_GET_PURCHASED_CONTENT, self._onGetXGPurchasedItems, self);
    g_EventDispatcherManager:RemoveEventListener(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_CHANNEL_EXIT, self._onNoChannelExit, self);
    self.fnLoginCallbackFunc = nil;
    self.fnLogoutCallbackFunc = nil;
    self.fnAccountInfoCallbackFunc = nil;
    self.fnGetPurchasedItemsCallbackFunc = nil;
    self.fnDirtyWordsFilterCallbackFunc = nil;
    self.tbLoginCallbackCtx = nil;
    self.tbLogoutCallbackCtx = nil;
    self.tbAccountInfoCallbackCtx = nil;
    self.tbGetPurchasedItemsCallbackCtx = nil;
    self.tbDirtyWordsFilterCallbackCtx = nil;
    self.strRawLoginJsonData = "{}";
    self.LoginData:Update(self.strRawLoginJsonData);
    self.bInited = false;
    local pAgent = self:getAgent();
    if pAgent then
        pAgent:UnInit();
    end
end

function LXGAgentManager:_onInit(strJsonData)
    LOG_FOR_PUBLISH_MSG("user init");
    self.bInited = self:IsInited();

    if self.LXGAgentDefine.XGSDKCheck == false then
        self.bInited = true;
    end

    g_LHBUI:Emit(g_LHBUIEvents.S2UI_InitedSdk, self.bInited);
end

--- 是否InitSdk
function LXGAgentManager:IsSdkInited()
    return self.bInited == true;
end


function LXGAgentManager:_onExit(strJsonData)
    local bRetCode = g_Game:EndUp();
    LOG_FOR_PUBLISH_MSG("[LXGAgentManager:onExit]", bRetCode);
end

---
--- Tick
---
function LXGAgentManager:OnGameTick(fDeltaTimeInSecs)
end

---
--- 是否可用
--- @return boolean
---
function LXGAgentManager:IsInited()
    return not not self.pXGSDKAgent and self.pXGSDKAgent:Usable();
end

---
--- 获得玩家名字
--- @return string
---
function LXGAgentManager:GetPersonName()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetPersonName failed. SDK not inited."));
        return retval;
    end
    retval = self.LoginData and self.LoginData.name;
    return retval;
end

---
--- 获取玩家id
--- @return string
---
function LXGAgentManager:GetAccountId()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetAccountId failed. SDK not inited."));
        return retval;
    end
    retval = self.LoginData and self.LoginData.uid;
    return retval;
end

---
--- 是否登录
--- @return boolean
---
function LXGAgentManager:BUserLoggedOn()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] BUserLoggedOn failed. SDK not inited."));
        return retval;
    end
    retval = self.LoginData and self.LoginData:IsValidUser();
    return retval;
end

---
--- 打开用户中心
--- @return boolean
---
function LXGAgentManager:OpenUserCenter()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] OpenUserCenter failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:OpenUserCenter();
    return retval;
end

---
--- 登录
--- @param cbFunc function
--- @param cbCtx table
--- @return boolean
---
function LXGAgentManager:TryLogin(cbFunc, cbCtx)
    self.fnLoginCallbackFunc = cbFunc;
    self.tbLoginCallbackCtx = cbCtx;
    -- woldvein: bypass platform login, simulate success directly
    LOG_W("[LXGAgentManager] TryLogin bypassed, simulating login success");
    self:_onLogin("{\"bLogin\":true,\"name\":\"offlineuser\",\"uid\":\"offlineuser\",\"code\":0,\"msg\":\"ok\"}");
    return true;
end

--- 
--- 针对SSG渠道的客户端，获取已经购买的物品，其他渠道无效
--- @param cbFunc function
--- @param cbCtx table
--- @return boolean
--- 
function LXGAgentManager:GetPurchasedItems(cbFunc, cbCtx)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetPurchasedItems failed. SDK not inited."));
        return retval;
    end
    self.fnGetPurchasedItemsCallbackFunc = cbFunc;
    self.tbGetPurchasedItemsCallbackCtx = cbCtx;
    retval = self.pXGSDKAgent:GetXGPurchasedItems();
    return retval;
end

---
--- 跟踪进入游戏主场景，用来给蓝鲸的事件上报系统使用，那边需要类似网游，有个登陆玩家账号退出账号的操作，属于兼容性处理
--- @return boolean
--- 
function LXGAgentManager:TrackEnterGame(strAccount)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] TrackEnterGame failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:TrackEnterGame(strAccount);
    return retval;
end

---
--- 跟踪退出到主菜单，用来给蓝鲸的事件上报系统使用，那边需要类似网游，有个登陆玩家账号退出账号的操作，属于兼容性处理
--- @return boolean
--- 
function LXGAgentManager:TrackLogoutRole()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] TrackLogoutRole failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:TrackLogoutRole()
    return retval;
end


function LXGAgentManager:_onLogin(strJsonData)
    self.strRawLoginJsonData = strJsonData or "{}";
    self.LoginData:Update(self.strRawLoginJsonData);
    -- woldvein: GetPersonName crashes when Steam module is empty, skip it
    -- name is already set from JSON data via LoginData:Update()
    if not self.LoginData.name or self.LoginData.name == "" then
        self.LoginData.name = "offlineuser";
    end

    local bValidUser = self.LoginData:IsValidUser();
    if not bValidUser and (self.AFLAG or self.LXGAgentDefine.XGSDKCheck == false) then
        --- For Dev Mode here..
        LOG_W("[LXGAgentManager]login callbacked but user is invalid and we are in dev mode, uss dev account automatically, login cb data is:");
        LOG_W(strJsonData);
        self.LoginData.bLogin = true;
        self.LoginData.name = "offlineuser";
        self.LoginData.uid = "offlineuser";
        LOG_W(string.format("[LXGAgentManager]login dev account set to status: %s, name: %s, uid: %s", tostring(self.LoginData.bLogin), self.LoginData.name, self.LoginData.uid));
    end

    local tbData     = self.LoginData;
    local strName    = self.LoginData.name;
    local strAccount = self.LoginData.uid;
    LOG_FOR_PUBLISH_MSG(string.format(
        "[LXGAgentManager][Login] Login callback, login:%s username:%s, account:%s, online:%s",
        tostring(tbData.bLogin), tostring(strName), tostring(strAccount), tostring(bValidUser)
    ));
    self:SetUserFolderName();

    -- woldvein: TrackEnterGame calls XGSDK C function which crashes when Steam is not running
    -- It is only for analytics/reporting, not needed for offline mode
    -- if tbData.bLogin and self.LXGAgentDefine.XGSDKCheck == true then
    --     local ret = self:TrackEnterGame(strAccount);
    --     if ret then
    --         LOG_W(string.format("[LXGAgentManager] TrackEnterGame Success!!!"));
    --     end
    -- end
    LOG_W("[LXGAgentManager] TrackEnterGame skipped for offline mode");

    local fnLogin = self.fnLoginCallbackFunc;
    local anyCtx = self.tbLoginCallbackCtx;
    self.fnLoginCallbackFunc = nil;
    self.tbLoginCallbackCtx = nil;
    if type(fnLogin) == "function" then
        fnLogin(anyCtx, {
            bLogin = tbData.bLogin,
            code   = tbData.code,
            msg    = tbData.msg,
            name   = tbData.name,
            uid    = tbData.uid,
        });
    end
end

---
--- 设置登录回调
--- @param cbFunc function
--- @param cbCtx table
---
function LXGAgentManager:SetLogoutHandle(cbFunc, cbCtx)
    self.fnLogoutCallbackFunc = cbFunc;
    self.tbLogoutCallbackCtx = cbCtx;
end

---
--- 登录
--- @param cbFunc function
--- @param cbCtx table
--- @return boolean
---
function LXGAgentManager:TryLogout(cbFunc, cbCtx)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] TryLogout failed. SDK not inited."));
        return retval;
    end
    self:TrackLogoutRole();
    self.fnLogoutCallbackFunc = cbFunc;
    self.tbLogoutCallbackCtx = cbCtx;
    retval = self.pXGSDKAgent:TryLogout();
    return retval;
end

function LXGAgentManager:_onLogout(strJsonData)
    LOG_FOR_PUBLISH_MSG("user logout");
    self.strRawLoginJsonData = "{}";
    self.LoginData:Update("{}");
    self:SetUserFolderName();
   

    local fnLogout = self.fnLogoutCallbackFunc;
    local anyLogoutCtx = self.tbLogoutCallbackCtx;
    self.fnLogoutCallbackFunc = nil;
    self.tbLogoutCallbackCtx = nil;
    if type(fnLogout) == "function" then
        fnLogout(anyLogoutCtx, {
            bLogin = false,
            code   = "",
            msg    = "",
            name   = "",
            uid    = "",
        });
    end
end

---
--- 获取账号信息
--- @param cbFunc function
--- @param cbCtx table
--- @return boolean
---
function LXGAgentManager:TryGetAccountInfo(cbFunc, cbCtx)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] TryGetAccountInfo failed. SDK not inited."));
        return retval;
    end
    self.fnAccountInfoCallbackFunc = cbFunc;
    self.tbAccountInfoCallbackCtx = cbCtx;
    retval = self.pXGSDKAgent:TryGetAccountInfo();
    return retval;
end

function LXGAgentManager:_onGetAccountInfo(strJsonData)
    local tbData = JSON.Loads(strJsonData or "{}", {}) or {};
    local strName = tbData.passport_id or "";
    local strAccount = tbData.passport_id or "";
    self.LoginData.name = tbData.passport_id or "";
    LOG_FOR_PUBLISH_MSG(string.format(
        "[LXGAgentManager][TryGetAccountInfo] TryGetAccountInfo callback, username:%s, account:%s",
        tostring(strName), tostring(strAccount)
    ));
    local CallbackFunc = self.fnAccountInfoCallbackFunc;
    local CallbackCtx = self.tbAccountInfoCallbackCtx;
    self.fnAccountInfoCallbackFunc = nil;
    self.tbAccountInfoCallbackCtx = nil;
    if type(CallbackFunc) == "function" then
        CallbackFunc(CallbackCtx, {
            bLogin = self.LoginData.bLogin,
            code   = self.LoginData.code,
            msg    = self.LoginData.msg,
            name   = strName,
            uid    = strAccount,
        });
    end
end

function LXGAgentManager:_onGetFilterdDirtyWords(strJsonData)
    local tbData = JSON.Loads(strJsonData or "{}", {}) or {};
    -- 结构：
    -- local bSucc = not not tbData.bSucc;
    -- local strInputWords = tbData.strInputWords;
    -- local strOutputWords = tbData.strOutputWords;
    -- local strErrMsg = tbData.strErrMsg;
    local CallbackFunc = self.fnDirtyWordsFilterCallbackFunc;
    local CallbackCtx = self.tbDirtyWordsFilterCallbackCtx;
    self.fnDirtyWordsFilterCallbackFunc = nil;
    self.tbDirtyWordsFilterCallbackCtx = nil;
    if type(CallbackFunc) == "function" then
        CallbackFunc(CallbackCtx, tbData);
    end
end

function LXGAgentManager:_onGetXGPurchasedItems(strJsonData)
    local tbData = JSON.Loads(strJsonData or "{}", {}) or {};
    -- 结构：
    -- local bSucc = not not tbData.bSucc;
    -- local strPurchasedContent = tbData.strPurchasedContent;
    -- local strErrMsg = tbData.strErrMsg;
    local CallbackFunc = self.fnGetPurchasedItemsCallbackFunc;
    local CallbackCtx = self.tbGetPurchasedItemsCallbackCtx;
    self.fnGetPurchasedItemsCallbackFunc = nil;
    self.tbGetPurchasedItemsCallbackCtx = nil;
    if type(CallbackFunc) == "function" then
        CallbackFunc(CallbackCtx, self.LoginData, tbData);
    end
end

function LXGAgentManager:_onNoChannelExit()
    local bRetCode = g_Game:EndUp();
    LOG_I("[LXGAgentManager:NoChannelExit]", bRetCode);
end

--- @return string
function LXGAgentManager:GetUserFolderName()
    local userDir = g_ClientSetting:GetRecentSteamAccountId();
    if nil == userDir or string.isempty(userDir) then
        return "offlineuser";
    end
    return userDir;
end

--- @return boolean
function LXGAgentManager:SetUserFolderName()
    local bOnline = self:BUserLoggedOn();

    if true == bOnline then
        local strAccount = self:GetAccountId();
        g_ClientSetting:SetRecentSteamAccountId(strAccount);
        return true;
    end
    return false;
end

---
--- 设置成就统计等配置
--- @param tbAchieveConfigs number[]
--- @return boolean
---
function LXGAgentManager:SetupAchievementConfig(tbAchieveConfigs)
    local bRet = true;
    tbAchieveConfigs = tbAchieveConfigs or {};
    for index, item in ipairs(tbAchieveConfigs) do
        local nAchieveId, strAchAPI, strAchieveName, nStateID, strStateName = table.unpack(item);
        if nAchieveId and strAchAPI and strAchieveName then
            bRet = self.pXGSDKAgent:AddAchievementConfig(nAchieveId, strAchAPI, strAchieveName);
        end
        if nStateID and strStateName then
            bRet = self.pXGSDKAgent:AddStatisticConfig(nStateID, strStateName);
        end
        (bRet and LOG_I or LOG_W)(string.format(
            "[LSteamGamePlay] Set achievement config, nAchieveId<%s>, strAchAPI<%s> nStateID<%s>, strAchieveName<%s>, strStateName<%s>",
            nAchieveId, strAchAPI, nStateID or "", strAchieveName, strStateName or ""
        ));
    end
    bRet = self.pXGSDKAgent:SetupAchievement();
    return bRet;
end

---
--- 反设置
--- @return boolean
---
function LXGAgentManager:UnSetupAchievement()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] UnSetupAchievement failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:UnSetupAchievement();
    return retval;
end

---
--- 发送自定义数据到运营平台
--- @param strEventId string
--- @param strEventDesc string
--- @param tbEventContentKeys table<number, string> 内容Key数组
--- @param tbEventContentVals table<number, string> 内容Value数组
--- @return boolean
---
function LXGAgentManager:SendEvent(strEventId, strEventDesc, tbEventContentKeys, tbEventContentVals)
    if not self.pXGSDKAgent or not strEventId then
        -- LOG_W(string.format("[LXGAgentManager] SendEvent failed. strEventId<%s>", strEventId));
        return false;
    end
    return self.pXGSDKAgent:SendEvent(strEventId, strEventDesc, tbEventContentKeys, #tbEventContentKeys, tbEventContentVals, #tbEventContentVals);
end

---
--- 获取当前玩家数量(通过 SetCallBack 异步回调)
--- @return boolean
---
function LXGAgentManager:GetNumberOfCurrentPlayers()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetNumberOfCurrentPlayers failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:GetNumberOfCurrentPlayers();
    return retval;
end

---
--- 判断当前渠道是否为传入的渠道类型
--- @param eChannelType IXGSDKChannelType
--- @return boolean
---
function LXGAgentManager:GetChannelOf(eChannelType)
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetChannelOf failed. SDK not inited."));
        return false;
    end
    local pOption = self.pXGSDKAgent:GetOptions();
    return pOption.eChannelType == eChannelType;
end

---
--- 获取道具数量
--- @return integer
---
function LXGAgentManager:GetItemsCount()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetItemsCount failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:GetItemsCount();
    return retval;
end

---
--- 获取库存中的物品列表
--- @param pItemIds table<number, number> 记录所有物品id的数组指针
--- @param nItemCount integer 物品种类数量
--- @return boolean
---
function LXGAgentManager:GetItemList(tbItemIds, nItemCount)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetItemList failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:GetItemList(tbItemIds, nItemCount);
    return retval;
end

---
--- 获取库存中的物品数量
--- @param pItemQuantity table<number, number> 记录所有物品数量的数组指针
--- @param nItemCount number 物品种类数量
--- @return boolean
---
function LXGAgentManager:GetItemListQuantity(tbItemQuantity, nItemCount)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetItemListQuantity failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:GetItemListQuantity(tbItemQuantity, nItemCount);
    return retval;
end

---
--- 添加物品（可用于线上版本，给玩家加物品）
--- @param nItemID number 物品id
--- @return boolean
---
function LXGAgentManager:AddPromoItem(nItemID)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] AddPromoItem failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:AddPromoItem(nItemID);
    return retval;
end

---
--- 添加指定物品（仅用于开发中，给开发者账号加物品）
--- @param nDefinition number 物品id
--- @return boolean
---
function LXGAgentManager:GenerateItem(nDefinition)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GenerateItem failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:GenerateItem(nDefinition);
    return retval;
end

---
--- 消耗物品
--- @param nItemID number 实例id
--- @param uCount number 消耗数量
--- @return boolean
---
function LXGAgentManager:CostItem(nItemID, uCount)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] CostItem failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:CostItem(nItemID, uCount);
    return retval;
end

---
--- 刷新物品
--- @return boolean
---
function LXGAgentManager:RefreshItems()
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] RefreshItems failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:RefreshItems();
    return retval;
end

---
--- 交换物品
--- @param nGenerateItemDef number 将要创建的物品ID（仅支持 1 件）
--- @param uDestroyInstanceItems table<number, number> 将要销毁的实例id列表
--- @param uDestroyQuantity number 对应将要销毁的物品数量
--- @param uDestroyLength number 将要销毁的物品数组长度
--- @return boolean
---
function LXGAgentManager:ExchangeItem(nGenerateItemDef, tbDestroyInstanceItems, uDestroyQuantity, uDestroyLength)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] ExchangeItem failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:ExchangeItem(nGenerateItemDef, tbDestroyInstanceItems, uDestroyQuantity, uDestroyLength);
    return retval;
end

---
--- 设置触发掉落物品的规则时间
--- @param nDropListDefMinute number 间隔时长（单位：分钟）
--- @return boolean
---
function LXGAgentManager:TriggerItemDrop(nDropListDefMinute)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] TriggerItemDrop failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:TriggerItemDrop(nDropListDefMinute);
    return retval;
end

---
--- 解锁成就
--- @param nAchieveID number 成就id
--- @return boolean
---
function LXGAgentManager:UnlockAchievement(nAchieveID)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] UnlockAchievement failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:UnlockAchievement(nAchieveID);
    return retval;
end

---
--- 新增统计
--- @param nStateID number 统计对象id
--- @return boolean
---
function LXGAgentManager:IncreaseStateValue(nStateID)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] IncreaseStateValue failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:IncreaseStateValue(nStateID);
    return retval;
end

---
--- 获取成就的解锁状态以及解锁时间（如果已解锁）
--- @param pcszName string 成就API-key
--- @param pbRetAchieved boolean 返回值 是否解锁
--- @param uRetUnlockTime integer 返回值 解锁时间（如果已解锁）
--- @return boolean
---
function LXGAgentManager:GetAchievementAndUnlockTime(pcszName, pbRetAchieved, uRetUnlockTime)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetAchievementAndUnlockTime failed. SDK not inited."));
        return retval;
    end
    retval, pbRetAchieved, uRetUnlockTime = self.pXGSDKAgent:GetAchievementAndUnlockTime(pcszName, pbRetAchieved, uRetUnlockTime);
    return retval, pbRetAchieved, uRetUnlockTime;
end

---
--- 删除指定存档文件
--- @param strFilePath string
--- @return boolean
---
function LXGAgentManager:DeleteStorageFile(strFilePath)
    local retval = false;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] DeleteStorageFile failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:DeleteStorageFile(strFilePath);
    return retval;
end

---
--- 检查用户是否已经拥有指定DLC并且安装（EPIC和Steam通用）
--- @param strDLCID string
--- @param onresult function func(boolean bOwnItem, string strID, string strErrMsg) -> void
--- @param context context of onresult
--- @return boolean
---
function LXGAgentManager:QueryDlcOwnership(strDLCID, onresult, context)
    local retval = false;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] IsDLCInstalled failed. SDK not inited."));
        return retval;
    end
    local Define = self.LXGAgentDefine;
    local function _onQueryOwnership(strJsonResult)
        local bOwnItem, strID, strErrMsg = false, "", "";
        if strJsonResult then
            local tbJsonData = JSON.Loads(strJsonResult, {bOwnItem = bOwnItem, strID = strID, strErrMsg = strErrMsg});
            bOwnItem, strID, strErrMsg = tbJsonData.bOwnItem, tbJsonData.strID, tbJsonData.strErrMsg;
        end
        if strDLCID ~= strID then
            --- 可能有注册多个同名事件，会一次性回来，所以需要判断是否当时闭包的ID
            return false;
        end
        self:delEvent(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_QUERY_OWNERSHIP, _onQueryOwnership, self);
        if onresult and not context then
            onresult(bOwnItem, strID, strErrMsg);
        end
        if onresult and context then
            onresult(context, bOwnItem, strID, strErrMsg);
        end
    end
    self:addEvent(Define.EVENT_MODULE.XGSDKAGENT, Define.EVENTS.ON_QUERY_OWNERSHIP, _onQueryOwnership, nil);
    retval = self.pXGSDKAgent:QueryDlcOwnership(strDLCID);
    return retval;
end

---
--- 当用户获得DLC且该DLC安装后触发，安装成功后会触发sdkCallback回调，事件名：SteamDlcInstall
--- @param uAppID number
--- @return boolean
---
function LXGAgentManager:InstallDLC(uAppID)
    local retval = false;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] InstallDLC failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:InstallDLC(uAppID);
    return retval;
end

---
--- 获取可选DLC的下载进度
--- @param uAppID number
--- @param punBytesDownloaded number 已下载字节数
--- @param punBytesTotal number 全部字节数
--- @return boolean
---
function LXGAgentManager:GetDLCDownloadProgress(uAppID, punBytesDownloaded, punBytesTotal)
    local retval = false;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] GetDLCDownloadProgress failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:GetDLCDownloadProgress(uAppID, punBytesDownloaded, punBytesTotal);
    return retval;
end

---
--- 卸载指定DLC
--- @param uAppID number
--- @return boolean
---
function LXGAgentManager:UninstallDLC(uAppID)
    local retval = false;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] UninstallDLC failed. SDK not inited."));
        return retval;
    end
    retval = self.pXGSDKAgent:UninstallDLC(uAppID);
    return retval;
end

--- 
--- 脏话过滤
--- @param strInputWords string
--- @param cbFunc function
--- @param cbCtx table
--- @return boolean
--- 
function LXGAgentManager:DirtyWordsFilter(strInputWords, cbFunc, cbCtx)
    local retval = nil;
    if not self.pXGSDKAgent then
        LOG_W(string.format("[LXGAgentManager] DirtyWordsFilter failed. SDK not inited."));
        return retval;
    end
    self.fnDirtyWordsFilterCallbackFunc = cbFunc;
    self.tbDirtyWordsFilterCallbackCtx = cbCtx;
    retval = self.pXGSDKAgent:DirtyWordsFilter(strInputWords);
    return retval;
end

--- @type LXGAgentManager
_G.g_LXGAgentManager = _G.g_LXGAgentManager or LXGAgentManager:new();
