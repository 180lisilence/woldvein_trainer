---
--- Generated manually.
--- Created by liaogaocan.
--- DateTime: 2023-12-3 23:28:15
--- Desc: 启动游戏后最开始的状态，展示logo，播放开场影片，显示主菜单等等。
---
local LGameStateBase = ImportScript("script/core/game_state/game_state_base.lua").LGameStateBase;
---@class LWelcomeState
LWelcomeState = LWelcomeState or class("LWelcomeState", LGameStateBase);
function LWelcomeState:ctor()
    ---@type LGame
    self.m_game = nil;
    self.m_szLoginMapPath = "data\\source\\maps\\empty_launch\\empty_launch.jsonmap";
    self.m_nLoginSceneID = 0;
end
function LWelcomeState:dtor()
end
function LWelcomeState:IsCacheable()
    return false;
end
function LWelcomeState:GetKey()
    return g_Game.LGameDefine.STATE_KEY_LWelcomeState;
end
---@param globalSharedData any
---@param lastStateSharedData any
function LWelcomeState:OnInit(globalSharedData, lastStateSharedData)
    LOG_I("LWelcomeState:OnInit");
    return true;
end
function LWelcomeState:OnUninit()
    LOG_I("LWelcomeState:OnUninit");
end
---@param globalSharedData any
---@param lastStateSharedData any
function LWelcomeState:OnEnter(globalSharedData, lastStateSharedData)
    LOG_I("LWelcomeState:OnEnter");
    _G.g_CurrentGameState = self;
    self.m_game = globalSharedData;
    ---@type LSceneParam
    local tbSceneParam = {
        szResPath = self.m_szLoginMapPath,
        bMainScene = true,
        fnOnCreated = function (scene) self:_onStartSceneCreate(); end,
        fnOnProgress = function (scene, data) self:_onStartSceneLoadingProgress(scene, data); end,
        fnOnReady = function (scene) self:_onStartSceneReady(); end,
        fnOnDestroy = function (scene) self:_onStartSceneDestroy(); end
    };
    local lScene = g_SceneManager:CreateScene(tbSceneParam, nil);
    if lScene then
        self.m_nLoginSceneID = lScene:GetID();
        g_SceneManager:SetCurSceneByID(self.m_nLoginSceneID);
    else
        return false;
    end
    return true;
end
function LWelcomeState:OnLeave()
    if self.m_nLoginSceneID == g_SceneManager:GetCurSceneID() then
        g_SceneManager:SetCurSceneByID(0);
    end
    g_SceneManager:DestroyScene(self.m_nLoginSceneID);
    self.m_nLoginSceneID = 0;
    self.m_game = nil;
    LOG_I("LWelcomeState:OnLeave");
    _G.g_CurrentGameState = nil;
end
function LWelcomeState:OnTick(fDeltaTimeInSecs)
end
function LWelcomeState:OnGameDraw(fDeltaTimeInSecs)
end
function LWelcomeState:OnGameCrash()
    LOG_I("LWelcomeState:OnGameCrash");
end
---
--- @private
---
function LWelcomeState:_onStartSceneCreate()
    LOG_I("Start scene created");
    LOG_I("[LWelcomeState:_onStartSceneCreate] create initial map to:", util.a2u8(self.m_szLoginMapPath), "succeed!");
    g_PlayerController:SwitchMod("normal");
    local tbDefaultCameraInfo = self.m_game:GetDefaultCameraInfo();
    g_CameraController:SetFovAngleY(45.0);
    g_CameraController:SetAspectRatio(16.0/9.0);
    g_CameraController:SetNearPlane(tbDefaultCameraInfo.nNearPlane);
    g_CameraController:SetFarPlane(tbDefaultCameraInfo.nFarPlane);
    
    g_CameraController:SetRotation(45.0, 45.0, 0, true);
    local x,y,z = table.unpack_3(tbDefaultCameraInfo.CameraPos);
    
    g_CameraController:SetPosition(x,y,z, true);
    -- g_Cursor:SwitchMode(cursor_define.Mode.Normal);
    g_ClientSetting:ApplyAll();
    g_WindowManager:ResetWindowPos();
    g_LUiPageManager:To(g_LUiConst.Pages.BASETOOL);
    LOG_I("[LWelcomeState:_onStartSceneCreate] start ok!");
end
---
--- @private
---
function LWelcomeState:_onStartSceneLoadingProgress(scene, data)
    local fSceneLoadingProgress = scene:TryToCalculateFakeSceneLoadingProgress(data);
    g_EventDispatcherManager:DispatchEvent("scene", "loading", fSceneLoadingProgress);
end
---
--- @private
---
function LWelcomeState:_onStartSceneReady()
    LOG_I("Start scene readied");
    if g_LLocalization:IsLanguageChanged() then
        g_LRPDescManager:ReloadLocalization();
        g_LInputController:ReloadLocalization();
    end
    g_Cursor:SwitchMode(cursor_define.Mode.Normal);
end
---
--- @private
---
function LWelcomeState:_onStartSceneDestroy()
end
function LWelcomeState:OnLoadPrepareVideo()
    -- woldvein: always auto-fire login
    LOG_W("[WoldVein] welcome_state: auto TryLogin fired");
    g_LHBUIProvider:EmitTo("LCommonProvider", g_LHBUIEvents.UI2S_TryLogin, nil);
end