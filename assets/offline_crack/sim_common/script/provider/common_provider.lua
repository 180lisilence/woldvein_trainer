---
--- Date         : 2021-05-18 09:37:19
--- Author       : LICHAO7
--- Description  : LCommonProvider
---
local LCameraDefine = ImportScript("script/gameplay/camera/camera_define.lua").LCameraDefine;
local tbDefine = LCameraDefine:GetCurDefine();
--- @type LInputDefine
local InputDefine = ImportScript("script/gameplay/input/input_define.lua").LInputDefine;
local BuildingFuncDefine = ImportScript("script/gameplay/building/building_func/building_func_define.lua").LBuildingFuncDefine;
-- local tbDefine = ImportScript("script/gameplay/camera/camera_define.lua").CameraGodDefine;
local LTimeDefine = ReLoadScript("script/gameplay/time/time_define.lua").LTimeDefine;
local SettingsDefine = ImportScript("script/gameplay/settings/settings_define.lua").LSettingsDefine;
---
---
--- @class LCommonProvider:LBaseProvider
---
LCommonProvider = LCommonProvider or class("LCommonProvider", LBaseProvider);
function LCommonProvider:ctor()
    self.LastNpcAudioPlayingID = 0;
    self.m_nMinRadius = tbDefine.nMinRadius;
    self.m_nMaxRadius = tbDefine.nMaxRadius;
    self.m_nRayCastDistance = 200000; --cm
    self.m_uIgnoreMask = bit.ors(
            Core.enuGameGroup_CharacterController,
            Core.enuGameGroup_CharacterPart,
            Core.enuGameGroup_CharacterPartWithProxy,
            Core.enuGameGroup_CollidableWithCharacterController,
            Core.enuGameGroup_WHEEL,
            Core.enuGameGroup_CHASSIS,
            Core.enuGameGroup_Walkable,
            Core.enuGameGroup_NonWalkable,
            Core.enuGameGroup_Pushable
    );
    
    -- 不用存档
    self.hoverInfoTimerId = -1; -- 指示hover的建筑的延时器的id
    self.buildTipsLastInfo = {};  -- 存储上一次结果，判断这次是否要传送数据
    self.nCurrentOperatingWorldObjectUUID = nil;
    self.bHasTryLogin = false;
    self.nLastTryLoginTime = os.time();
    self.tbOriginGeo = {};
end
---
--- 在这里注册g_LHBUI:On事件
---
function LCommonProvider:Init()
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnFirstEmit, self.UI2S_OnFirstEmit, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GameStart, self.UI2S_GameStart, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GameStartLoad, self.UI2S_GameStartLoad, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GameReLoad, self.UI2S_GameReLoad, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_ArchiveDelete, self.UI2S_ArchiveDelete, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CoverBackUpToStorage, self.UI2S_CoverBackUpToStorage, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GameSave, self.UI2S_GameSave, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_ArchiveRename, self.UI2S_ArchiveRename, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GameEnd, self.UI2S_GameEnd, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GameQuit, self.UI2S_GameQuit, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_TryLogin, self.UI2S_TryLogin, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_IsLogin, self.UI2S_IsLogin, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_TryAuthorize, self.UI2S_TryAuthorize, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OpenUserCenter, self.UI2S_OpenUserCenter, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_TryCleanAuthorize, self.UI2S_TryCleanAuthorize, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetXGChannelType, self.UI2S_GetXGChannelType, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_EndGameCheckCanSave, self.UI2S_EndGameCheckCanSave, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CheckCanSave, self.UI2S_CheckCanSave, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_TriggerLoadPeriod, self.UI2S_TriggerLoadPeriod, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnShowHBUIAABB, self.UI2S_OnShowHBUIAABB, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnShowHBUIRect, self.UI2S_OnShowHBUIRect, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetGameState, self.UI2S_GetGameState, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetGameState, self.UI2S_SetGameState, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetStopGameProactive, self.UI2S_SetStopGameProactive, self);
    
    g_LHBUI:On(g_LHBUIEvents.UI2S_SwitchToMoveMode, self.UI2S_SwitchToMoveMode, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SwitchToNormalMode, self.UI2S_SwitchToNormalMode, self);
    
    g_LHBUI:On(g_LHBUIEvents.UI2S_SwitchToDismantleMode, self.UI2S_SwitchToDismantleMode, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SwitchToUpgradeMode, self.UI2S_SwitchToUpgradeMode, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnSoundsPostEvent, self.UI2S_OnSoundsPostEvent, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnSoundsPostEventByBnkEvent, self.UI2S_OnSoundsPostEventByBnkEvent, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnSoundsPostEmotionEvent, self.UI2S_OnSoundsPostEmotionEvent, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CloseSeasounSounds, self.UI2S_CloseSeasounSounds, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetInitErrors, self.UI2S_GetInitErrors, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetArchives, self.UI2S_GetArchives, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_PlayNpcAudio, self.UI2S_PlayNpcAudio, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CancelBuildMode, self.UI2S_CancelBuildMode, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_RestoreBuildingMoveMode, self.UI2S_RestoreBuildingMoveMode, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnHasEventFinished, self.UI2S_OnHasEventFinished, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SwitchMode, self.UI2S_SwitchMode, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnCloseMapByMouseWheel, self.UI2S_OnCloseMapByMouseWheel, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnOpenOrCloseWindow, self.UI2S_OnOpenOrCloseWindow, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnOpenOrCloseFullScreenMask, self.UI2S_OnOpenOrCloseFullScreenMask, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CheckUIModelState, self.UI2S_CheckUIModelState, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CheckUIWindowExist, self.UI2S_CheckUIWindowExist, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetHBUIInputHandled, self.UI2S_SetHBUIInputHandled, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_EnterPreparationPeriod,self.UI2S_EnterPreparationPeriod,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_EndPreparationPeriod,self.UI2S_EndPreparationPeriod,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OpenBigMapDuringPreparation,self.UI2S_OpenBigMapDuringPreparation,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetEnvironmentMoment, self.UI2S_SetEnvironmentMoment,self);
	g_LHBUI:On(g_LHBUIEvents.UI2S_GetOperationInfo,self.UI2S_GetOperationInfo,self);
	g_LHBUI:On(g_LHBUIEvents.UI2S_OnGUIReady,self.UI2S_OnGUIReady,self);
	g_LHBUI:On(g_LHBUIEvents.UI2S_UnlockBtn,self.UI2S_UnlockBtn,self);
	g_LHBUI:On(g_LHBUIEvents.UI2S_InitGamePlayerUI,self.UI2S_InitGamePlayerUI,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_LoadingUIMounted, self.UI2S_LoadingUIMounted, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_HoverProjectResource, self.UI2S_HoverProjectResource, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_UnhoverWorldObject, self.UI2S_UnhoverWorldObject, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetTeachingInfo, self.UI2S_GetTeachingInfo,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetTaught,self.UI2S_SetTaught,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetTeachingTipsConfig,self.UI2S_GetTeachingTipsConfig,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetNewGameModeList, self.UI2S_GetNewGameModeList, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetPlayModeTitle, self.UI2S_GetPlayModeTitle, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetSandboxMapList, self.UI2S_GetSandboxMapList, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetTimeContent, self.UI2S_GetTimeContent, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetConfirmInfo, self.UI2S_GetConfirmInfo, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetSettingConfirmInfo, self.UI2S_GetSettingConfirmInfo, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GamePlayerConfig,self.S2UI_GamePlayerConfig,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_ResourcesConfig,self.S2UI_ResourcesConfig,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_HotelConfig,self.S2UI_HotelConfig,self);
    g_LHBUI:On(g_LHBUIEvents.S2UI_OnUpdateTipsInfoPerDay,self.S2UI_OnUpdateTipsInfoPerDay,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_RecordKeyInput,self.UI2S_RecordKeyInput,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_RecordMouseInput,self.UI2S_RecordMouseInput,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_RecordKeyConflict,self.UI2S_RecordKeyConflict,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnOperateFullScreenInterface,self.UI2S_OnOperateFullScreenInterface,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnBuildUnHovered,self.UI2S_OnBuildUnHovered,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_WonderEntryTipsUpdatePerDay,self.UI2S_WonderEntryTipsUpdatePerDay,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetCursorShow,self.UI2S_SetCursorShow,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CloseSceneAudio,self.UI2S_CloseSceneAudio,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_StartTiltShiftStatus,self.UI2S_StartTiltShiftStatus,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_EndTiltShiftStatus,self.UI2S_EndTiltShiftStatus,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_StartTiltShiftStatusByESC,self.UI2S_StartTiltShiftStatusByESC,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_EndTiltShiftStatusByESC,self.UI2S_EndTiltShiftStatusByESC,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetSceneryStatus,self.UI2S_SetSceneryStatus,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnSetGameStateWhenScenery,self.UI2S_OnSetGameStateWhenScenery,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetEditModeStatus,self.UI2S_SetEditModeStatus,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_PreviewCardBuildTime,self.UI2S_PreviewCardBuildTime,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_UpdateHotelModuleInfo,self.UI2S_UpdateHotelModuleInfo,self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetHotelComment,   self.UI2S_GetHotelComment, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_RecieveReward,   self.UI2S_RecieveReward, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnConfirmFestivalRewardByType,   self.UI2S_OnConfirmFestivalRewardByType, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetGeologicMapLayerInfo,   self.UI2S_GetGeologicMapLayerInfo, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetGeologicMapLayerInfo,   self.UI2S_SetGeologicMapLayerInfo, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetCameraAutoMove,   self.UI2S_SetCameraAutoMove, self);
    
    g_LHBUI:On(g_LHBUIEvents.UI2S_ChangeSpecailHouse,   self.UI2S_ChangeSpecailHouse, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CheckCanStartTiltShift,   self.UI2S_CheckCanStartTiltShift, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CheckCanStartScenery,   self.UI2S_CheckCanStartScenery, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CloseOperateTips,   self.UI2S_CloseOperateTips, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnSandboxOpenedAni,   self.UI2S_OnSandboxOpenedAni, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_ReignTitleChangedCallback,   self.UI2S_ReignTitleChangedCallback, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_GetReignTitleList, self.UI2S_GetReignTitleList, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_ChangeWindLevel, self.UI2S_ChangeWindLevel, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_ChangeFilter, self.UI2S_ChangeFilter, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SetCameraSettingInfo, self.UI2S_SetCameraSettingInfo, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnOperateScreenShot, self.UI2S_OnOperateScreenShot, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_OnOperateScreenRecord, self.UI2S_OnOperateScreenRecord, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_UILoadingFinished, self.UI2S_UILoadingFinished, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_SwitchCameraMode, self.UI2S_SwitchCameraMode, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CoverAutoArchivesReminder, self.UI2S_CoverAutoArchivesReminder, self);
    g_LHBUI:On(g_LHBUIEvents.UI2S_CopyAutoArchive, self.UI2S_CopyAutoArchive, self);
    -- g_LHBUI:On(g_LHBUIEvents.S2UI_OnCancelUpdateTipsInfoPerDay,self.S2UI_OnCancelUpdateTipsInfoPerDay,self);
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.START_UI_DATA_SYNC, self._syncUIDisaster, self);
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.WEATHER_CHANGED,self.S2UI_OnUpdateWeather,self);
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.WIND_CHANGED,self.S2UI_OnUpdateWeather,self);
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_LOCALIZATION, g_LocalizationEventType.ON_LANGUAGE_CHANGED, self.S2UI_OnUpdateStartLocalization,self);
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_CAMERA, g_CameraEventType.FOVY_CHANGE, self.S2UI_OnUpdateCameraFovy,self);
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_CAMERA, g_CameraEventType.BLUR_SIZE_CHANGE, self.S2UI_OnUpdateCameraBlurSize,self);
end
function LCommonProvider:UnInit()
    g_LHBUI:Off(g_LHBUIEvents.UI2S_UILoadingFinished, self.UI2S_UILoadingFinished, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetReignTitleList, self.UI2S_GetReignTitleList, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_ReignTitleChangedCallback, self.UI2S_ReignTitleChangedCallback, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnSandboxOpenedAni, self.UI2S_OnSandboxOpenedAni, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CloseOperateTips, self.UI2S_CloseOperateTips, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnFirstEmit, self.UI2S_OnFirstEmit, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GameStart, self.UI2S_GameStart, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GameStartLoad, self.UI2S_GameStartLoad, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GameReLoad, self.UI2S_GameReLoad, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_ArchiveDelete, self.UI2S_ArchiveDelete, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CoverBackUpToStorage, self.UI2S_CoverBackUpToStorage, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GameSave, self.UI2S_GameSave, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_ArchiveRename, self.UI2S_ArchiveRename, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_TryLogin, self.UI2S_TryLogin, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_IsLogin, self.UI2S_IsLogin, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_TryAuthorize, self.UI2S_TryAuthorize, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OpenUserCenter, self.UI2S_OpenUserCenter, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_TryCleanAuthorize, self.UI2S_TryCleanAuthorize, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetXGChannelType, self.UI2S_GetXGChannelType, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GameEnd, self.UI2S_GameEnd, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GameQuit, self.UI2S_GameQuit, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_EndGameCheckCanSave, self.UI2S_EndGameCheckCanSave, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CheckCanSave, self.UI2S_CheckCanSave, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_TriggerLoadPeriod, self.UI2S_TriggerLoadPeriod, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnShowHBUIAABB, self.UI2S_OnShowHBUIAABB, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnShowHBUIRect, self.UI2S_OnShowHBUIRect, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnOpenOrCloseFullScreenMask, self.UI2S_OnOpenOrCloseFullScreenMask, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnOpenOrCloseWindow, self.UI2S_OnOpenOrCloseWindow, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CheckUIModelState, self.UI2S_CheckUIModelState, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CheckUIWindowExist, self.UI2S_CheckUIWindowExist, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetGameState, self.UI2S_GetGameState, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetGameState, self.UI2S_SetGameState, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SwitchToMoveMode, self.UI2S_SwitchToMoveMode, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SwitchToDismantleMode, self.UI2S_SwitchToDismantleMode, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SwitchToUpgradeMode, self.UI2S_SwitchToUpgradeMode, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnSoundsPostEvent, self.UI2S_OnSoundsPostEvent, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnSoundsPostEventByBnkEvent, self.UI2S_OnSoundsPostEventByBnkEvent, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnSoundsPostEmotionEvent, self.UI2S_OnSoundsPostEmotionEvent, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CloseSeasounSounds, self.UI2S_CloseSeasounSounds, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetInitErrors, self.UI2S_GetInitErrors, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetArchives, self.UI2S_GetArchives, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_PlayNpcAudio, self.UI2S_PlayNpcAudio, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CancelBuildMode, self.UI2S_CancelBuildMode, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_RestoreBuildingMoveMode, self.UI2S_RestoreBuildingMoveMode, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnHasEventFinished, self.UI2S_OnHasEventFinished, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SwitchMode, self.UI2S_SwitchMode, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnCloseMapByMouseWheel, self.UI2S_OnCloseMapByMouseWheel, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetHBUIInputHandled, self.UI2S_SetHBUIInputHandled, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_EnterPreparationPeriod,self.UI2S_EnterPreparationPeriod,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_EndPreparationPeriod,self.UI2S_EndPreparationPeriod,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OpenBigMapDuringPreparation,self.UI2S_OpenBigMapDuringPreparation,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetEnvironmentMoment, self.UI2S_SetEnvironmentMoment,self);
	g_LHBUI:Off(g_LHBUIEvents.UI2S_GetOperationInfo,self.UI2S_GetOperationInfo,self);
	g_LHBUI:Off(g_LHBUIEvents.UI2S_OnGUIReady,self.UI2S_OnGUIReady,self);
	g_LHBUI:Off(g_LHBUIEvents.UI2S_UnlockBtn,self.UI2S_UnlockBtn,self);
	g_LHBUI:Off(g_LHBUIEvents.UI2S_InitGamePlayerUI,self.UI2S_InitGamePlayerUI,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_LoadingUIMounted, self.UI2S_LoadingUIMounted, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_HoverProjectResource, self.UI2S_HoverProjectResource, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_UnhoverWorldObject, self.UI2S_UnhoverWorldObject, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetTeachingInfo, self.UI2S_GetTeachingInfo,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetTaught,self.UI2S_SetTaught,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetTeachingTipsConfig,self.UI2S_GetTeachingTipsConfig,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetNewGameModeList, self.UI2S_GetNewGameModeList, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetPlayModeTitle, self.UI2S_GetPlayModeTitle, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetSandboxMapList, self.UI2S_GetSandboxMapList, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetTimeContent, self.UI2S_GetTimeContent, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetConfirmInfo, self.UI2S_GetConfirmInfo, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetSettingConfirmInfo, self.UI2S_GetSettingConfirmInfo, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GamePlayerConfig,self.S2UI_GamePlayerConfig,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_ResourcesConfig,self.S2UI_ResourcesConfig,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_HotelConfig,self.S2UI_HotelConfig,self);
    g_LHBUI:Off(g_LHBUIEvents.S2UI_OnUpdateTipsInfoPerDay,self.S2UI_OnUpdateTipsInfoPerDay,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_RecordKeyInput,self.UI2S_RecordKeyInput,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_RecordMouseInput,self.UI2S_RecordMouseInput,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_RecordKeyConflict,self.UI2S_RecordKeyConflict,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnOperateFullScreenInterface,self.UI2S_OnOperateFullScreenInterface,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnBuildUnHovered,self.UI2S_OnBuildUnHovered,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_WonderEntryTipsUpdatePerDay,self.UI2S_WonderEntryTipsUpdatePerDay,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetCursorShow,self.UI2S_SetCursorShow,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CloseSceneAudio,self.UI2S_CloseSceneAudio,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_StartTiltShiftStatus,self.UI2S_StartTiltShiftStatus,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_EndTiltShiftStatus,self.UI2S_EndTiltShiftStatus,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_StartTiltShiftStatusByESC,self.UI2S_StartTiltShiftStatusByESC,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_EndTiltShiftStatusByESC,self.UI2S_EndTiltShiftStatusByESC,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetSceneryStatus,self.UI2S_SetSceneryStatus,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnSetGameStateWhenScenery,self.UI2S_OnSetGameStateWhenScenery,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetEditModeStatus,self.UI2S_SetEditModeStatus,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_PreviewCardBuildTime,self.UI2S_PreviewCardBuildTime,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_UpdateHotelModuleInfo,self.UI2S_UpdateHotelModuleInfo,self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_RecieveReward,   self.UI2S_RecieveReward, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnConfirmFestivalRewardByType,   self.UI2S_OnConfirmFestivalRewardByType, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_GetGeologicMapLayerInfo,   self.UI2S_GetGeologicMapLayerInfo, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetGeologicMapLayerInfo,   self.UI2S_SetGeologicMapLayerInfo, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetCameraAutoMove,   self.UI2S_SetCameraAutoMove, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_ChangeSpecailHouse,   self.UI2S_ChangeSpecailHouse, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_ChangeWindLevel, self.UI2S_ChangeWindLevel, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_ChangeFilter, self.UI2S_ChangeFilter, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SetCameraSettingInfo, self.UI2S_SetCameraSettingInfo, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnOperateScreenShot, self.UI2S_OnOperateScreenShot, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_OnOperateScreenRecord, self.UI2S_OnOperateScreenRecord, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_SwitchCameraMode, self.UI2S_SwitchCameraMode, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CoverAutoArchivesReminder, self.UI2S_CoverAutoArchivesReminder, self);
    g_LHBUI:Off(g_LHBUIEvents.UI2S_CopyAutoArchive, self.UI2S_CopyAutoArchive, self);
    g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.START_UI_DATA_SYNC, self._syncUIDisaster, self);
    g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.WEATHER_CHANGED,self.S2UI_OnUpdateWeather,self);
    g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.WIND_CHANGED,self.S2UI_OnUpdateWeather,self);
    g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_LOCALIZATION, g_LocalizationEventType.ON_LANGUAGE_CHANGED, self.S2UI_OnUpdateStartLocalization,self);
    g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_CAMERA, g_CameraEventType.FOVY_CHANGE, self.S2UI_OnUpdateCameraFovy,self);
    g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_CAMERA, g_CameraEventType.BLUR_SIZE_CHANGE, self.S2UI_OnUpdateCameraBlurSize,self);
    self.LastNpcAudioPlayingID = 0;
    -- self.m_nMinRadius = g_CameraDefine:GetCurDefine().nMinRadius;
    -- self.m_nMaxRadius = g_CameraDefine:GetCurDefine().nMaxRadius;
    self.m_nRayCastDistance = 200000; --cm
    self.m_uIgnoreMask = nil;
    
    -- 不用存档
    self.hoverInfoTimerId = -1; -- 指示hover的建筑的延时器的id
    self.buildTipsLastInfo = {};  -- 存储上一次结果，判断这次是否要传送数据
end
function LCommonProvider:UI2S_ChangeSpecailHouse(tbData)
    local g,d,p,l  = tbData.G, tbData.D, tbData.P, tbData.L;
    local cType    = tbData.CType;
    local tbParam  = {
        [1]  = cType,
        [2]  = {g, d, p, l},
        [3]  = tbData.ID; --建筑id
    }
    g_EventDispatcherManager:DispatchEvent(g_EventModel.LEVENT_GAMEPLAY, g_BuildingEventType.ON_HOUSE_CHANGE_SPECIAL, tbParam);
end
function LCommonProvider:UI2S_SetCursorShow(state)
    g_Cursor:Show(state);
end
function LCommonProvider:UI2S_OnFirstEmit(data)
    _G["__APP_INFO__"] = data or {};
    LOG_FOR_PUBLISH_MSG("APP_VERSION:", _G.__APP_INFO__.APP_VERSION);
    LOG_FOR_PUBLISH_MSG("LOG:", _G.__APP_INFO__.LOG);
    LOG_FOR_PUBLISH_MSG("APP_ROOT:", _G.__APP_INFO__.APP_ROOT);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnFirstRecv, {
        ["LuaApp"] = "Got an app info.",
    });
end
function LCommonProvider:S2UI_SetIsInTest(bIntest)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_SetIsInTest, bIntest);
end
---
--- UI G Readied
---
function LCommonProvider:UI2S_OnGUIReady()    
    -- local bRet, w, h = g_WindowManager:GetWindowSize();
    -- g_LHBUIProvider:EmitTo("LSettingsProvider", g_LHBUIEvents.UI2S_ChangeResolutionRatio, {
    --     width      = w,
    --     height     = h,
    --     fullScreen = true,
    --     bFit       = true
    -- });
    g_ClientSetting:Apply();
    -- TODO:!!! 解决窗口卡死后位置不对的问题（lichao7，这是打补丁，应该从根源解决
    g_WindowManager:ResetWindowPos();
    -- woldvein: auto login (bypass 3s throttle)
    LOG_W("[WoldVein] OnGUIReady -> auto TryLogin");
    self.nLastTryLoginTime = os.time() - 999;
    self:UI2S_TryLogin();
end
---
--- UI2S_GameStart
---
--- @param data any
---
function LCommonProvider:UI2S_GameStart(tData)
    local playMode = tData.PlayMode;
    local nSceneCfgId = tonumber(tData.SceneId) or 1;
    local lastArchiveId = tData.LastArchive or "";
    if  playMode == g_Game.LGameDefine.PLAY_MOD.SANDBOX then
        if not nSceneCfgId or  nSceneCfgId < 0  then
            LOG_E("Error Start SceneId In SANDBOX Mode!");
            return;
        end
    end
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.LEVEL_READY, self.S2UI_OnGameLoaded, self);
    g_EventDispatcherManager:AddEventListener("scene", "loading", self.S2UI_OnGameLoading, self);
    g_Game:NewGame(nSceneCfgId, playMode, lastArchiveId);
end
function LCommonProvider:UI2S_ArchiveDelete(uuid)
    g_Game:DeleteArchive(uuid);
end
function LCommonProvider:UI2S_ArchiveRename(data)
    g_Game:ReNameArchive(data.archiveId, data.name);
end
function LCommonProvider:UI2S_CoverBackUpToStorage(data)
    g_ArchiveMgr:CoverBackUpToStorage(data);
end
---
--- UI2S_GameSave
---
--- @param data any
---
function LCommonProvider:UI2S_GameSave(data)
    local arInfo = {
        playMode = g_GameWorld:GetPlayMod(),
        year     = data.time[1],
        month    = data.time[2],
        day      = data.time[3],
        season   = data.time[4],
        inputName = data.name,
    }
    local arData = {
        arUUID = data.archiveId,
        arInfo = arInfo,
    }
    
    -- g_Game:SaveArchive(arData);
    if g_Game:IsMainGame() then
        local bRetCode = g_Game:SaveMainArchive(arData);
        LOG_I("[LCommonProvider:UI2S_GameSave]", bRetCode);
    else
        local bRetCode = g_Game:SaveSubArchive(arData);
        LOG_I("[LCommonProvider:UI2S_GameSave]", bRetCode);
    end
end
---
--- UI2S_GameReLoad
---
function LCommonProvider:UI2S_GameReLoad(uuid)
    g_GameWorld:ResetPreparationPeriod();
    self:UI2S_EndTiltShiftStatusByESC();
    g_Game:GetStateMachine():SetNextState("LWelcomeState", nil, true);
    LOG_I("[LCommonProvider:UI2S_GameReLoad]");
end
---
--- UI2S_GameEnd
---
--- @param data any
---
function LCommonProvider:UI2S_GameEnd(data)
    -- 退出到主菜单时触发
    local nTime, strTime = g_Game:GetGameStartTime();
    local tbBuildingCount = {};
    local strArchiveId = g_Game:GetArchiveUUID() or "NEW_GAME|NO_ARCHIVE";
    local tbGDPList = g_BuildingWorldModule.BuildingMgr:GetBuildingGDPList();
    for nBlockId, tbBlock in pairs(tbGDPList) do
        for nG, tbGDict in pairs(tbBlock) do
            for nD, tbDDict in pairs(tbGDict) do
                for nP, tbPDict in pairs(tbDDict) do
                    for strUUID, nLevel in pairs(tbPDict) do
                        local strGDPL = nBlockId .. "@" .. util.GDPLStringify(nG, nD, nP, nLevel);
                        tbBuildingCount[strGDPL] = (tbBuildingCount[strGDPL] or 0) + 1;
                    end
                end
            end
        end
    end
    local tbGDPL = {};
    for k, v in pairs(tbBuildingCount) do
        local tbKeySplited, bEmpty = string.split(k, "@");
        local strGDPL = #tbKeySplited > 1 and tbKeySplited[2] or k;
        local strBlockId = #tbKeySplited > 0 and tbKeySplited[1] or "0";
        local tbItem = {
            GDPL = { util.GDPLParse(strGDPL) },
            Count = v,
            Block = tonumber(strBlockId)
        };
        table.insert(tbGDPL, tbItem);
    end
    self:UI2S_EndTiltShiftStatusByESC();
    g_LXGAgentManager:SendEvent(g_LXGStatistics.MakeBuildingCountEventData(strArchiveId, os.time() - nTime, strTime, tbGDPL, g_GameWorld:GetPlayMod()));
    g_GameWorld:ResetPreparationPeriod();
    g_Game:GetStateMachine():SetNextState("LWelcomeState", nil, true);
    LOG_I("[LCommonProvider:UI2S_GameEnd]");
end
---
--- UI2S_GameQuit
---
--- @param data any
---
function LCommonProvider:UI2S_GameQuit(data)
    local bRetCode = g_Game:EndUp();
    LOG_I("[LCommonProvider:UI2S_GameQuit]", bRetCode);
end
---
--- UI2S_TryLogin
---
function LCommonProvider:UI2S_TryLogin()
    self:UI2S_TryAuthorize();
    -- if not self.bHasTryLogin then
    -- else
    --     LOG_FOR_PUBLISH_MSG("Has Try Login, waiting...");
    -- end
end
---
--- UI2S_IsLogin
---
function LCommonProvider:UI2S_IsLogin()
    local bRetCode = g_LXGAgentManager:BUserLoggedOn();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetIsLogin, bRetCode);
    LOG_FOR_PUBLISH_MSG("Is Login", bRetCode);
end
--- #region 0130 login
function LCommonProvider:UI2S_TryAuthorize()
    local nCurTime = os.time();
    local CHANNEL_DEFINE = g_LXGAgentManager.IXGSDKChannelType;
    local bXGJinShanLogin = g_LXGAgentManager:GetChannelOf(CHANNEL_DEFINE.XGJinShan);
    local nWaitTime = bXGJinShanLogin and 15 or 3;
    if nCurTime - self.nLastTryLoginTime < nWaitTime then
        LOG_FOR_PUBLISH_MSG(string.format("Has Try Authorize, waiting %ds...", nWaitTime));
        return false;
    end
    self.bHasTryLogin = true;
    self.nLastTryLoginTime = nCurTime;
    g_LXGAgentManager:SetLogoutHandle(self._onCleanAuthorization, self);
    local bRetCode = g_LXGAgentManager:TryLogin(self._onGetAuthorization, self);
    LOG_FOR_PUBLISH_MSG("UI2S_TryAuthorize", bRetCode);
end
function LCommonProvider:_onGetAuthorization(tbLoginData)
    local CHANNEL_DEFINE = g_LXGAgentManager.IXGSDKChannelType;
    if g_LXGAgentManager:GetChannelOf(CHANNEL_DEFINE.XGJinShan) then
        g_LXGAgentManager:GetPurchasedItems(self._ongetaccountinfo, self);
    else
        self:_ongetaccountinfo(tbLoginData, nil);
    end
end
function LCommonProvider:_ongetaccountinfo(tbLoginData, tbPurchaseItemData)
    local CHANNEL_DEFINE = g_LXGAgentManager.IXGSDKChannelType;
    local bXGJinShanLogin = g_LXGAgentManager:GetChannelOf(CHANNEL_DEFINE.XGJinShan);
    local tbAccountData = {
        bLogin = false,
        code   = "",
        msg    = "",
        name   = "",
        uid    = "",
    };
    -- local bLogin = tbLoginData.bLogin;
    -- local code   = tbLoginData.code;
    -- local msg    = tbLoginData.msg;
    -- local name   = tbLoginData.name;
    -- local uid = tbLoginData.uid;
    local strAccount = tbLoginData.bLogin and tbLoginData.uid or nil;
    if bXGJinShanLogin then
        local bGetSucceed = tbPurchaseItemData ~= nil and tbPurchaseItemData.bSucc;
        local tbPurchasedContent = bGetSucceed and tbPurchaseItemData.PurchasedContent or nil;
        local tbPurchasedAppIDs = tbPurchasedContent and tbPurchasedContent.purchasedProductIds or nil;
        local strInfaceVersion = tbPurchasedAppIDs and g_LXGAgentManager.LXGAgentDefine.GetInfactAppVersion(tbPurchasedAppIDs) or nil;
        tbAccountData.bLogin = tbLoginData.bLogin and not string.isempty(strInfaceVersion);
    else
        tbAccountData.bLogin = tbLoginData.bLogin;
        tbAccountData.name = g_LXGAgentManager:GetPersonName();
        tbAccountData.uid  = strAccount;
    end
    if tbAccountData.bLogin then
        if string.isempty(strAccount) or strAccount == "NULL" then
            strAccount = nil;
        end
        g_ClientSetting:SetRecentSteamAccountId(strAccount);
        g_ArchiveMgr:SetUserFolderName(g_LXGGameplay:GetUserFolderName());
        g_ArchiveMgr:RefreshArchiveList();
        g_ArchiveMgr:RefreshBackupList();
        
        self:UI2S_GetArchives();
        if g_LXGAgentManager:GetChannelOf(CHANNEL_DEFINE.XGJinShanWithSteamV2) or 
            g_LXGAgentManager:GetChannelOf(CHANNEL_DEFINE.XGJinShanWithSteamV2ByDebug) then
            if game_world_define then
                game_world_define.HREFS.PRIVACY_POLICY = game_world_define.HREFS.PRIVACY_POLICY_OUTER;
                game_world_define.HREFS.GAME_AGREEMENT = game_world_define.HREFS.GAME_AGREEMENT_OUTER;
            end
        end
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnLogin, tbAccountData);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetAuthorization, tbAccountData);
end
---
--- UI2S_OpenUserCenter
---
function LCommonProvider:UI2S_OpenUserCenter()
    local bRetCode = g_LXGAgentManager:OpenUserCenter();
    LOG_FOR_PUBLISH_MSG("UI2S_OpenUserCenter", bRetCode);
end
function LCommonProvider:UI2S_TryCleanAuthorize()
    local bRetCode = g_LXGAgentManager:TryLogout(self._onCleanAuthorization, self);
    LOG_FOR_PUBLISH_MSG("UI2S_TryCleanAuthorize", bRetCode);
end
function LCommonProvider:_onCleanAuthorization(loginData)
    -- g_ClientSetting:SetRecentSteamAccountId("offlineuser");
    -- g_ArchiveMgr:SetUserFolderName(g_LXGAgentManager:GetUserFolderName());
    -- g_ArchiveMgr:RefreshArchiveList();
    -- self:UI2S_GetArchives();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnCleanAuthorization, loginData);
end
function LCommonProvider:UI2S_GetXGChannelType()
    return g_LXGAgentManager.LXGAgentDefine.XGSDKChannelType;
end
--- #endregion
---
--- UI2S_CheckCanSave
---
--- @param data any
---
function LCommonProvider:UI2S_CheckCanSave()
    local  bRetCode = g_Game:CheckIsCanSave();
    LOG_I("[LCommonProvider:UI2S_CheckCanSave]", bRetCode);
    if bRetCode == 0 then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_CheckCanSave, bRetCode);
    end
end
--- 
--- UI2s_EndGameCheckSave 退回主菜单的时候检测能否保存
---
function LCommonProvider:UI2S_EndGameCheckCanSave()
    local nRectCode, sErrorTxtCode = g_Game:GetIsCanSaveErrorInfo();
    if  nRectCode == 0 then
        if  g_Game:GetAllowAutoSaveBeforeExit() == true then
            g_Game:AutoSaveArchive();
            g_Game:SetAllowAutoSaveBeforeExit(false);
        end
    end
    local tbSourceType = {
        block_define.SOURCE.MONEY,
        block_define.SOURCE.MINERAL,
        block_define.SOURCE.WOOD,
        block_define.SOURCE.CLOTH,
        block_define.SOURCE.FOOD,
        block_define.SOURCE.WATER,
        block_define.SOURCE.SALT,
        block_define.SOURCE.LIQUOR,
        block_define.SOURCE.QUINTESSENCE
    }
    local tbSource = {};
    local selectBlock = g_blockMgr:GetSelectedBlock();
    if  selectBlock then
        local nBlockId = selectBlock:GetBlockID();
        for index, type in ipairs(tbSourceType) do
            local value = selectBlock:GetSourceValue(type) or 0;
            table.insert(tbSource, math.floor(value));
        end
        g_LXGAgentManager:SendEvent(g_LXGStatistics.MakeReourcesCountEventData( g_GameWorld:GetPlayMod(), nBlockId, tbSource));
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_EndGameCheckCanSave, nRectCode);
end
---
--- S2UI_OnGameEnded
---
--- @param data any
---
function LCommonProvider:S2UI_OnGameEnded(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGameEnded, data);
end
---
--- S2UI_OnGameEndLoading
---
--- @param data any
---
function LCommonProvider:S2UI_OnGameEndLoading(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGameEndLoading, data);
end
---
--- UI2S_TriggerLoadPeriod
---
--- @param strPeriod string
---
function LCommonProvider:UI2S_TriggerLoadPeriod(strPeriod)
    local fnPeriod = g_CurrentGameState[define.LOAD_PERIOD[strPeriod]];
    if type(fnPeriod) == "function" then
        pcall(fnPeriod, g_CurrentGameState);
    end
end
---
--- UI2S_GetArchives
---
function LCommonProvider:UI2S_GetArchives()
    local archives = {};
    local archiveList = g_ArchiveMgr:GetArchiveList();
    local backUpList = g_ArchiveMgr:GetBackUpArchiveList();
    for nIdx, ar in ipairs(archiveList) do
        if nil ~= ar then  
            table.insert(archives, ar:DumpArchive());
        end
    end
    local data = {
        archives = archives,
        backUpList = backUpList
    }
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetArchives, data);
end
function LCommonProvider:UI2S_MoveAutoArchiveToNormal(data)
    local strUUID, strNewName = data.strUUID, data.strNewName;
    local findArchive = g_ArchiveMgr:GetArchive(strUUID);
    if findArchive then
        findArchive:SetArchiveType(setting_define.ArchiveType.NORMAL_SAVE);
        g_ArchiveMgr:SetArchiveName(strUUID, strNewName);
        self:UI2S_GetArchives();
        local successCopyTip = g_LRPDescManager:GetRPTextFormated("E_SUCCESS_AUTOSAVE_OVERWRITE", {DataName = data.strNewName});
        g_LHBUIProvider:EmitTo("LCommonProvider", g_LHBUIEvents.S2UI_OnPushSystemTip, successCopyTip);
    end
end
-- 还是需要拷贝一份存档并重命名
function LCommonProvider:UI2S_CopyAutoArchive(data)
    local strUUID, strNewName = data.strUUID, data.strNewName;
    local findArchive = g_ArchiveMgr:GetArchive(strUUID);
    if findArchive then
        local archiveData = table.copy(findArchive:ToData(), true);
        local szSubUUID = util.GenerateUuid();
        g_ArchiveMgr:CreateAndCopySaveArchiveBOH(strNewName, szSubUUID, archiveData, SettingsDefine.ArchiveType.NORMAL_SAVE);
        local successCopyTip = g_LRPDescManager:GetRPTextFormated("E_SUCCESS_AUTOSAVE_OVERWRITE", {DataName = data.strNewName});
        g_LHBUIProvider:EmitTo("LCommonProvider", g_LHBUIEvents.S2UI_OnPushSystemTip, successCopyTip);
    end
end
---
--- UI2S_GetNewGameModeList
---
function LCommonProvider:UI2S_GetNewGameModeList()
    local dumpData = {};
    local bChallengeModeUnlocked = g_ClientSetting:GetIsChallengeModeUnlocked();
    for i, mode in pairs(g_Game.LGameDefine.NEW_GAME_MOD) do
        local info = g_Game.LGameDefine.GAME_MOD_INFO[mode];
        local bUnlocked = true;
        if not bChallengeModeUnlocked and (mode == g_Game.LGameDefine.PLAY_MOD.COUNTRYSIDE or mode == g_Game.LGameDefine.PLAY_MOD.HIGH_WIND) then
            bUnlocked = false;
        end
        dumpData[i] = {
            mode = mode,
            title = g_LRPDescManager:GetRPTextFormated(info.TitleText),
            desc = g_LRPDescManager:GetRPTextFormated(info.DescText),
            difficulty = g_LRPDescManager:GetRPTextFormated(info.DifficultyText),
            type = g_LRPDescManager:GetRPTextFormated(info.TypeText),
            limit = g_LRPDescManager:GetRPTextFormated(info.LimitText),
            bgPath = util.a2u8(info.BgPath),
            bRecommend = info.Recommend,
            bUnlocked = bUnlocked,
        }
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetNewGameModeList, dumpData);
end
---
--- UI2S_GetPlayModeTitle
---
function LCommonProvider:UI2S_GetPlayModeTitle()
    local highWindTitle = g_LRPDescManager:GetRPTextFormated("HIGNWIND_MODE_TITLE");
    local countrysideTitle = g_LRPDescManager:GetRPTextFormated("COUNTRYSIDE_MODE_TITLE");
    local leisureTitle = g_LRPDescManager:GetRPTextFormated("LEISURE_MODE_TITLE");
    local sandBoxTitle = g_LRPDescManager:GetRPTextFormated("SANDBOX_MODE_TITLE");
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetPlayModeTitle, {
        hWT = highWindTitle,
        cST = countrysideTitle,
        mMT = leisureTitle,
        sBT = sandBoxTitle,
    });
end
---
--- 获取沙盒模式地图信息
---
function LCommonProvider:UI2S_GetSandboxMapList()
    local mapList = {};
    local tbSceneList = g_scenesCfg:GetSceneCfgListByType(g_scenesCfg.SCENCE_TYPE.SANDBOX);
    for i, info in ipairs(g_Game.LGameDefine.SANDBOX_MAP_INFO) do
        local mapSceneId = info.sceneId;
        if tbSceneList[mapSceneId] ~= nil then
            local data = {
                mapSceneId = mapSceneId,
                name = g_LRPDescManager:GetRPTextFormated(info.NameText),
                title = g_LRPDescManager:GetRPTextFormated(info.TitleText),
                desc = g_LRPDescManager:GetRPTextFormated(info.DescText),
                iconPath = util.a2u8(info.IconPath);
                bgPath = util.a2u8(info.BgPath);
                bRecommend = info.Recommend;
            };
            table.insert(mapList, data);
        end
    end
    
    local dumpData = {};
    dumpData.mapList = mapList;
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetSandboxMapList, dumpData);
end
---
--- UI2S_GetTimeContent
---
function LCommonProvider:UI2S_GetTimeContent()
    local data={
        year = "",
        month = "",
        day = "",
        day_common="",
    };
    data.year = g_LRPDescManager:GetRPTextFormated("TXT_YEAR");
    data.month = g_LRPDescManager:GetRPTextFormated("TXT_MONTH");
    data.day = g_LRPDescManager:GetRPTextFormated("TXT_DAY");
    data.day_common = g_LRPDescManager:GetRPTextFormated("TXT_DAY_COMMON");
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_GetTimeContent,data);
end
---
--- UI2S_GetConfirmInfo
---
function LCommonProvider:UI2S_GetConfirmInfo(confirmIndex)
    local dataset = {};
    local confirmInfo = setting_define.SaveConfirmInfo[confirmIndex];
    dataset.title = g_LRPDescManager:GetRPTextFormated(confirmInfo.title);
    dataset.content = g_LRPDescManager:GetRPTextFormated(confirmInfo.content);
    dataset.yes = g_LRPDescManager:GetRPTextFormated(confirmInfo.yes);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_GetConfirmInfo,dataset);
end
---
--- UI2S_GetSettingConfirmInfo
---
function LCommonProvider:UI2S_GetSettingConfirmInfo(data)
    local confirmIndex = data.confirmIndex;
    if confirmIndex == setting_define.SettingConfirmType.DLSS_CLOSE then
        local sw, sh = g_WindowManager:GetScreenSize();
        local bSupport = g_ClientSetting:GetVideoSetting():IsSupportDLSS();
        if not bSupport or sw < 2000 then
            g_LHBUI:Emit(g_LHBUIEvents.S2UI_GetSettingConfirmInfo,{bShowConfirm = false});
            return;
        end
    end
    local dataset = {};
    local confirmInfo = setting_define.SettingConfirmInfo[confirmIndex];
    dataset.title = g_LRPDescManager:GetRPTextFormated(confirmInfo.title);
    if confirmIndex == setting_define.SettingConfirmType.CONTROL_CONFLICT then
        local input = g_LInputController:Getinput(g_LInputController:GetConflictInputID());
        dataset.content = g_LRPDescManager:GetRPTextFormated(confirmInfo.content, {
            KeyName = g_LInputController:GetKeyName(input:GetFirstKeyID()),
            KeyFunc = input:GetFuncName(),
        });
    elseif confirmIndex == setting_define.SettingConfirmType.SETTING_CLOSE or confirmIndex == setting_define.SettingConfirmType.CHANGE_CATEGORY then
        local categoryName = g_LRPDescManager:GetRPTextFormated(setting_define.SETTINGS_KEY_NAME[data.category]);
        dataset.content = g_LRPDescManager:GetRPTextFormated(confirmInfo.content, {
            CategoryName = categoryName or "",
        });
    elseif confirmIndex == setting_define.SettingConfirmType.SETTING_CLOSE_RESTART or confirmIndex == setting_define.SettingConfirmType.CHANGE_CATEGORY_RESTART then
        local nRectCode, sErrorTxtCode, sNoSaveText = g_Game:GetIsCanSaveErrorInfo();
        if nRectCode == 0 then
            dataset.content = g_LRPDescManager:GetRPTextFormated(confirmInfo.content);
        else
            confirmInfo = setting_define.SettingConfirmInfo[setting_define.SettingConfirmType.CHANGE_CATEGORY_RESTART_NO_SAVE];
            dataset.content = g_LRPDescManager:GetRPTextFormated(confirmInfo.content, {
                CantSave = g_LRPDescManager:GetRPTextFormated(sNoSaveText),
            });
        end
    else
        dataset.content = g_LRPDescManager:GetRPTextFormated(confirmInfo.content);
    end
    dataset.yes = g_LRPDescManager:GetRPTextFormated(confirmInfo.yes);
    dataset.no = g_LRPDescManager:GetRPTextFormated(confirmInfo.no);
    dataset.bShowConfirm = true;
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_GetSettingConfirmInfo,dataset);
end
function LCommonProvider:S2UI_GetSettingSystemTipContent(content)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_GetSettingSystemTipContent,content);
end
---
--- UI2S_GameStartLoad
---
--- @param data any
---
function LCommonProvider:UI2S_GameStartLoad(data)
    local sceneCfg = g_scenesCfg:GetSceneCfg(1);
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.LEVEL_READY, self.S2UI_OnGameLoaded, self);
    g_EventDispatcherManager:AddEventListener("scene", "loading", self.S2UI_OnGameLoading, self);
    g_Game:LoadArchive(data);
end
---
--- S2UI_OnGameStart
---
--- @param data any
---
function LCommonProvider:S2UI_OnGameStart(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGameStart, data);
    if not g_LGuideManager:IsGuideEnd() then
        -- 新手引导打点
        g_LXGAgentManager:SendEvent(g_LXGStatistics.MakeNewGuideEventData(
            g_LXGStatistics.EventTypeFields.NEWGUIDE.ENUM_NEWGUIDEID.NPCTALKSTART,
            g_GameWorld:GetPlayMod()
        ));
    end
end
---
--- S2UI_OnUnInit
---
function LCommonProvider:S2UI_OnUnInit()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUnInit);
end
---
--- S2UI_OnGameLoaded
---
function LCommonProvider:S2UI_OnGameLoaded()
    LOG_I(">>>>>>>>>>>>>>>>>>>>>>>>>>>> [S2UI_OnGameLoaded] ");
    --- 同步一波数据到UI做提前处理 
    local data = {
        -- 引导状态
        [1] = g_Game:IsNewLevel();
        [2] = g_ClientSetting:GetPlayedGame();
        [3] = g_GameWorld.bSkipSandboxGuide;
    }     
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGameLoaded, data);
    g_EventDispatcherManager:RemoveEventListener("scene", "loading", self.S2UI_OnGameLoading, self);
    g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.LEVEL_READY, self.S2UI_OnGameLoaded, self);
    
    self:S2UI_OnGameStart({playMode = g_GameWorld:GetPlayMod()});
end
---
--- S2UI_OnGameLoading
---
--- @param data any
---
function LCommonProvider:S2UI_OnGameLoading(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGameLoading, data > 0.7 and 0.7 or data);
end
---
--- UI2S_OnShowHBUIAABB
---
--- @param data boolean
---
function LCommonProvider:UI2S_OnShowHBUIAABB(data)
    local piCoherentApp = g_Core:GetICoherentApp();
    if nil == piCoherentApp then
        return false
    end
    piCoherentApp:ShowElementAABBs(not not data);
end
---
--- UI2S_OnShowHBUIAABB
---
--- @param data boolean
---
function LCommonProvider:UI2S_OnShowHBUIRect(data)
    local piCoherentApp = g_Core:GetICoherentApp();
    if nil == piCoherentApp then
        return false
    end
    piCoherentApp:ShowPaintRectangles(not not data);
end
---
--- 更新天气和风力
---`
function LCommonProvider:S2UI_OnUpdateWeather(weatherType)
    local weatherId = weatherType or g_WeatherLogicMgr:GetCurrentWeather() or nil;
    local weatherName = block_define.WEATHER_CFG[weatherId+1].Name or nil;
    local windLevel = g_WeatherLogicMgr:GetCurrentWind() or nil;
    local windName = block_define.WIND_LEVEL_CFG[windLevel+1].Name or nil;
    local weatherTitle = g_LRPDescManager:GetRPTextFormated("MINITIPS_TITLE_WEATHER");
    local weatherDesc = g_LRPDescManager:GetRPTextFormated("MINITIPS_LEVEL_WEATHER",{weatherName = weatherName}); 
    local windDesc = g_LRPDescManager:GetRPTextFormated("MINITIPS_LEVEL_WIND",{windName = windName}); 
    local data = {
        weatherTitle = weatherTitle,
        weatherId   = weatherId,
        weatherName   = weatherName,
        windLevel   = windLevel, 
        windName   = windName, 
        weatherDesc = weatherDesc .."<br>".. windDesc,
    };
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateWeather, data);
end
function LCommonProvider:UI2S_PlayNpcAudio(data)
    local nNpcResID = data.NpcResID;
    LOG_I("UI2S_PlayNpcAudio  nNpcResID:"..nNpcResID);
    local res = g_LNPCManager:GetNpcRes(nNpcResID) or g_LNPCManager:GetNPC(nNpcResID);
    if not res or not next(res) then
        return;
    end
    local tbBreatheAudio = res:Get(res.ATTRS.BreatheAudio);
    if not tbBreatheAudio or not next(tbBreatheAudio) then
        return;
    end
    local nRandomIndex = g_Random:Random(#tbBreatheAudio);
    local szBankName, szEventName = table.unpack(tbBreatheAudio[nRandomIndex]);
    if not szBankName or not szEventName then
        return;
    end
    g_AudioManager:LoadBank(szBankName);
    local t = KTransform:new_local();
    if self.LastNpcAudioPlayingID > 0 then
        g_AudioManager:StopPlayingID(self.LastNpcAudioPlayingID);
    end
    self.LastNpcAudioPlayingID = g_AudioManager:PostEventAtLocation(szEventName, t);
end
function LCommonProvider:S2UI_OnBlackLoading()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBlackLoading);
end
function LCommonProvider:UI2S_OnHasEventFinished(eventType)
    if eventType == LBlackCurtainDefine.STATE.FADEIN then
        LBlackCurtainManager:CheckCondition();
    end
end
function LCommonProvider:S2UI_OnUnSelectSystem()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUnSelectSystem);
end
function LCommonProvider:StartBlackCurtain(time)
    local lastTime = time or 4;
    
    -- 黑屏保持后淡出
    local function blackDuration()
        local timer;
        timer = g_timer:Register(g_timer.TT_DEFAULT, lastTime, function ()
            local tbDuration = {
                state = LBlackCurtainDefine.STATE.DURATION,
            }
            LBlackCurtainManager:TriggerBlackCurtain(tbDuration, self.EndBlackCurtain);
        end);
        
    end
    -- 触发黑屏淡入
    local tbFadeIn = {
        state = LBlackCurtainDefine.STATE.FADEIN,
    }
    LBlackCurtainManager:TriggerBlackCurtain(tbFadeIn, blackDuration);
end
function LCommonProvider:EndBlackCurtain()
    LBlackCurtainManager:ResetState();
end
function LCommonProvider:UI2S_UnlockBtn(funcId)
    local tbdata = {
        funcID = funcId,
        callBack = nil,
    }
    self:S2UI_UnlockBtn(tbdata);
end
function LCommonProvider:S2UI_UnlockBtn(data)
    local funcID = data.funcID or nil;
    local callBackFunc = data.callBack or nil;
    local funcUnlock = g_FunctionManager:GetFunctionUnlock() or nil;
    local tbData = funcUnlock:GetFunctionByID(funcID) or {};
    tbData.newVersion = false;
    if tbData.showUnlock == 1 then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_UnlockBtn, tbData);
        if callBackFunc then
            local cb;
            cb = function ()
                xpcall(callBackFunc, Traceback);
                g_LHBUI:Off(g_LHBUIEvents.UI2S_UnlockFinished, cb);
            end
            g_LHBUI:On(g_LHBUIEvents.UI2S_UnlockFinished, cb);
        end
    else
        if callBackFunc then
            callBackFunc();
        end
    end
end
function LCommonProvider:S2UI_UnlockFengshui(data)
    local funcID = data.funcID or nil;
    local callBackFunc = data.callBack or nil;
    local funcUnlock = g_FunctionManager:GetFunctionUnlock() or nil;
    local tbData = funcUnlock:GetFunctionByID(funcID) or {};
    tbData.newVersion = false;
    if tbData.showUnlock == 1 then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_UnlockFengshui, tbData);
        if callBackFunc then
            local cb;
            cb = function ()
                xpcall(callBackFunc, Traceback);
                g_LHBUI:Off(g_LHBUIEvents.UI2S_UnlockFengshuiFinished, cb);
            end
            g_LHBUI:On(g_LHBUIEvents.UI2S_UnlockFengshuiFinished, cb);
        end
    else
        if callBackFunc then
            callBackFunc();
        end
    end
end
function LCommonProvider:UI2S_SetLocale(locale)
end
function LCommonProvider:S2UI_OnSetLocale(i18nTable)
end
function LCommonProvider:S2UI_OnUpdateTime()
    local block = g_blockMgr:HasSelectedBlock() and g_blockMgr:GetSelectedBlock() or g_blockMgr:GetBlock(block_define.CAMP_ID);
    local passedDay      = block:GetPassedDay();
    local accumulatedDay = (passedDay + 1);
    local blockY, blockM, blockD = g_Time:AccumulatedDay2Year(accumulatedDay), g_Time:AccumulatedDay2Month(accumulatedDay), g_Time:AccumulatedDay2Day(accumulatedDay);
    local tbTime = g_Time:GetTime();
    local reignTitle = g_timeLogicCfg:GetReignTitleCfgById(tbTime.reignId);
    if g_GameWorld:GetPlayMod() == g_Game.LGameDefine.PLAY_MOD.HIGH_WIND then
        -- *lichao7:这里是因为只有挑战地块的时间，需要设置在失败后，不能进行到第13个月第一天而设置，
        -- *lichao7:如果检查失败是在最后一天检查，并且弹出失败界面，并且直接暂停游戏，那么就是正确的，那样就不用设置这个限制
        if accumulatedDay > g_TimeDefine.DAY_PER_YEAR and blockM == 1 then
            blockM = g_TimeDefine.MONTH_PER_YEAR;
            blockD = g_TimeDefine.DAY_PER_MONTH;
        end
    end
    local tbData = {
        day = tbTime.day,
        month = tbTime.month,
        year = tbTime.year,
        blockYear = blockY,
        blockMonth = blockM,
        blockDay = blockD,
        season = g_Time:GetCurSeason(),
        seasonPercentege = g_Time:GetSeasonPercentege(),
        reignName = reignTitle.Name,
        reignTime = tbTime.reignYear,
    };
    if g_GameWorld:GetPlayMod() == g_Game.LGameDefine.PLAY_MOD.HIGH_WIND then
        tbData.remainDay = block:GetRemainDay();
    else
        tbData.totalMonth = (g_TimeDefine.MONTH_PER_YEAR*(blockY -1))+blockM;
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateTime, tbData);
end
function LCommonProvider:S2UI_UpdateReignTitle(reignTitle)
    if not reignTitle then
        return;
    end
    local data = {
        ReignId = reignTitle.Id,
        Name    = reignTitle.Name,
        Desc    = reignTitle.Desc,
        Time    = g_Time:GetReignYear(),
        LargeIcon = reignTitle.LargeIcon,
    };
    local setting = g_timeLogicCfg:GetReignTitleCfgById(reignTitle.Id);
    local rewards = {};
    for index, value in ipairs(setting.UIRewards[1] or {}) do
        local reward = g_timeLogicCfg:GetReignTitleFuncCfgByKey(value);
        if reward then
            table.insert(rewards, reward);
        end
    end
    data.rewards = self:GetReignReward(rewards);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateReignTitle, data);
end
function LCommonProvider:UI2S_ReignTitleChangedCallback(reignId)
    local setting = g_timeLogicCfg:GetReignTitleCfgById(reignId);
    local rewards = setting.Rewards;
    for _,reward in ipairs(rewards or {}) do
        if reward and #reward>0 then
            local rewardType,reward = table.unpack(reward);
            if rewardType == "unlock" then
                local className = reward[1];
                local funcId = reward[2];
                if className and _G[className] and _G[className].UnLockCallback then
                    _G[className]:UnLockCallback();
                end
                if funcId then
                    local bIsUnlock = g_FunctionManager:CheckFuncIsUnlock(funcId);
                    if bIsUnlock == g_functionState.CLOSE then
                        g_FunctionManager:SetFucntionState(funcId, g_functionState.OPEN);
                        -- g_FunctionManager:DoTriggleFunc(funcId);
                    end
                end
            elseif rewardType == "buildingCard" then
                if g_blockMgr:GetSelectedBlock().nId == block_define.CAMP_ID then
                    g_LHBUIProvider:EmitTo("LBuildingProvider", g_LHBUIEvents.S2UI_OnUpdateBuildingCards, block_define.CAMP_ID);
                end
            elseif rewardType == "customFunc" then
                local customFuncName = reward[1][1];
                if customFuncName == "AdviserSlot" then
                    -- 解锁挑战按钮显示
                    if g_GameWorld:GetPlayMod() ~= g_Game.LGameDefine.PLAY_MOD.SANDBOX and g_GameWorld:GetPlayMod() ~= g_Game.LGameDefine.PLAY_MOD.SANDBOX_AGO then
                        g_camp:SetCanStartChallenge(true);
                    end
                    -- 播放谋士府解锁动画
                    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnSetDisableStaffState, false);
                elseif customFuncName == "Council" then
                    g_LCouncilManager:SetCouncilUnlock(true);
                end
            end
        end
    end
    -- 资源奖励
    local resourceReward = setting.ResourceReward;
    local campBlock = g_camp;
    for _, resource in ipairs(resourceReward or {}) do
        campBlock:ModifySourceValue(resource[1], resource[2], true);
        g_LHBUIProvider:EmitTo("LBlockProvider", g_LHBUIEvents.S2UI_OnUpdateBaseBlockSources, campBlock.nId);
        if resource[1] == block_define.SOURCE.MONEY then
            g_BuildingWorldModule.BuildingMgr.Statistics:ModifyBuildingExpendisture(block_define.CAMP_ID, resource[2]);
        end
    end
end
function LCommonProvider:UI2S_GetReignTitleList()
    self:S2UI_GetReignTitleList();
end
function LCommonProvider:S2UI_GetReignTitleList()
    local tbReigns = {};
    local tbTime = g_Time:GetTime();
    if tbTime.reignId <= 0 then
        LOG_W("[LCommonProvider][UI2S_GetReignTitleList] reignId is invalid.");
        return;
    end
    local nReignNum = g_timeLogicCfg:GetReignTitleNumber();
    for id = 1, nReignNum do
        local reign = {};
        local rewards = {};
        local setting = g_timeLogicCfg:GetReignTitleCfgById(id);
        for index, value in ipairs(setting.UIRewards[1] or {}) do
            local reward = g_timeLogicCfg:GetReignTitleFuncCfgByKey(value);
            if reward then
                table.insert(rewards, reward);
            end
        end
        reign.Id = setting.Id;
        reign.name = setting.Name;
        reign.desc = setting.Desc;
        reign.rewards = self:GetReignReward(rewards);
        table.insert(tbReigns, reign);
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_GetReignTitleList, {
        tbReigns = tbReigns,
        reignId = tbTime.reignId,
        icon = g_Time:GetReignIcon(),
    });
end
function LCommonProvider:S2UI_GamePlayerConfig()
    local data={
        year = "",
        month = "",
        day = "",
        day_common="",
        numbers = true
    };
    local tbTranslatedTimeForm = g_Time:GetTranslateTimeForm();
    data.year = tbTranslatedTimeForm.YEAR;
    data.month = tbTranslatedTimeForm.MONTH;
    data.day = tbTranslatedTimeForm.DAY;
    data.day_common = tbTranslatedTimeForm.DAY_COMMON;
    data.numbers = g_Time:GetBaseTimeNumber();
    data.btnName = {
        g_LRPDescManager:GetRPTextFormated("FAMOUS_TIPS_TITLE"),
        g_LRPDescManager:GetRPTextFormated("FAMOUS_CITY_RANK"),
        g_LRPDescManager:GetRPTextFormated("ANECDOTE_TITLE"),
        g_LRPDescManager:GetRPTextFormated("PROPAGANDA_TITLE"),
        g_LRPDescManager:GetRPTextFormated("HANDBOOK_BOOKNAME"),
        g_LRPDescManager:GetRPTextFormated("EXPLORATION_MAP_TITLE"),
    }
    data.reigns={};
    local reignDefine = g_TimeDefine.REIGN;
    local prefix = reignDefine.Prefix;
    local playMode = g_GameWorld:GetPlayMod();
    if playMode == g_Game.LGameDefine.PLAY_MOD.SANDBOX then
        reignDefine = g_TimeDefine.SANDBOX_REIGN;
        prefix = reignDefine.Prefix;
    end
    for i=1,reignDefine.Count do
        table.insert(data.reigns,g_LRPDescManager:GetRPTextFormated(prefix .. i));
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_GamePlayerConfig,data);
end
function LCommonProvider:S2UI_ResourcesConfig()
    local data={
        g_LRPDescManager:GetRPTextFormated("TXT_CHALLENGE_DATE"),
        g_LRPDescManager:GetRPTextFormated("REMAIN_TIME_BLOCK"),
        g_LRPDescManager:GetRPTextFormated("QIAN"),
        g_LRPDescManager:GetRPTextFormated("WAN"),
        g_LRPDescManager:GetRPTextFormated("YI"),
        g_LRPDescManager:GetRPTextFormated("ZHAO"),
    };
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_ResourcesConfig,data);
end
function LCommonProvider:S2UI_HotelConfig()
    local data={
        strReviewNum = g_LRPDescManager:GetRPTextFormated("HOTEL_EVALUATOR_NUM"),
        strReviewTime = g_LRPDescManager:GetRPTextFormated("HOTEL_EVALUATION_TIME"),
        strPositiveRatio = g_LRPDescManager:GetRPTextFormated("HOTEL_POSITIVE_RATIO"),
        strCUnOpen = g_LRPDescManager:GetRPTextFormated("HOTEL_COMMENT_UNOPENED"), -- 酒店未达到一星
        strCEmpty = g_LRPDescManager:GetRPTextFormated("HOTEL_TIP_LIKES_EMPTY"), -- 暂无顾客评价
        strApplyName = g_LRPDescManager:GetRPTextFormated("HOTEL_APPLY_NAME"),
    };
    data.tbTipInfo = g_HotelManager:DumpHotelTipInfo();
    data.tbTourStrings = g_HotelManager:DumpTourStrings();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_HotelConfig, data);
end
function LCommonProvider:S2UI_ArbitrationtipsConfig()
    local data={
        title = g_LRPDescManager:GetRPTextFormated("ARBITRATION_LABORJUDGE_TITLE");
    };
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_ArbitrationtipsConfig, data);
end
function LCommonProvider:UI2S_UpdateHotelModuleInfo()
    local data = g_HotelManager:GetHotelModuleInfo();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateHotelModuleInfo, data);
end
--- 分页获取评论
function LCommonProvider:UI2S_GetHotelComment(data)
    local nMainType  = data.MainIndex or 0
    nMainType = nMainType + 1;
    local nPageIndex = data.CurPage;
    local tRetCommentData = g_HotelManager:GetHotelCommentByPage(nMainType, nPageIndex);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetHotelCommentRet, tRetCommentData);
end
function LCommonProvider:UI2S_RecordKeyInput(inputID)
    if inputID > 0 then
        g_LInputController:BeginRecordKeyInput(inputID);
    else
        g_LInputController:EndRecordKeyInput();
    end
end
function LCommonProvider:S2UI_RecordKeyInput(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_RecordKeyInput,data);
end
function LCommonProvider:UI2S_RecordMouseInput(data)
    g_LInputController:ProcessCurrentRecordMouseInput(data);
end
function LCommonProvider:S2UI_RecordKeyConflict(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_RecordKeyConflict,data);
end
function LCommonProvider:UI2S_RecordKeyConflict(data)
    g_LInputController:SetConflictKeyInput();
end
function LCommonProvider:S2UI_RecordKeyEnd()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_RecordKeyEnd);
end
-- 更改游戏模式
function LCommonProvider:S2UI_OnGetPlayMode()
    local playMode = g_GameWorld:GetPlayMod();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetPlayMode, playMode);
end
-- 更改打开全屏界面状态
function LCommonProvider:UI2S_OnOperateFullScreenInterface(bEnable)
    g_CameraController:EnableControl(bEnable and (not g_LGuideManager or g_LGuideManager:GetCanHandle()));
    g_CameraController:InterruptMouseWheelSmooth();
end
function LCommonProvider:UI2S_GetGameState()
    self:S2UI_OnGetGameState();
end
function LCommonProvider:UI2S_SetGameState(state)
    state = not state;
    local canPause = not g_PublicityManager or not g_PublicityManager:IsPlayingRoadSpeech();
    canPause = canPause and (not g_LGuideManager or g_LGuideManager:GetCanPause());
    if canPause then
        if state then
            g_Game:LogicTickPause();
        else
            g_Game:LogicTickResume();
        end
        
    end
    self:S2UI_OnGetGameState();
end
function LCommonProvider:UI2S_SetStopGameProactive()
    
end
function LCommonProvider:S2UI_OnGetGameState()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGetGameState, not g_Game:IsPaused());
end
function LCommonProvider:S2UI_ShowContextMenu(bShow)
    local _, x, y = g_WindowManager:GetClientMousePos();
    local block = g_blockMgr:GetSelectedBlock();
    local office = g_LOfficeManager:GetAdviserOfficeByBlockGDPL(block:GetGDPL());
    local bShowRoad, bShowCanal, bShowUpgrade = false, false, true;
    local warnMsg = "";
    if g_GameWorld:IsInEditStatus() then
        bShowUpgrade = false;
        warnMsg = g_LRPDescManager:GetRPTextFormated("CANT_USE_HANDLE_WARNING");
    else
        if office then
            local scheme = office:GetScheme();
            if scheme then
                local cardRoad = scheme:GetBuildingCardByGDPL(2, 1000, 5, 1);
                if cardRoad then
                    bShowRoad = cardRoad:GetUnlockState();
                end
                
                local cardCanal = scheme:GetBuildingCardByGDPL(2, 1001, 1, 1);
                if cardCanal then
                    bShowCanal = cardCanal:GetUnlockState();
                end
            end
        end
        warnMsg = g_LRPDescManager:GetRPTextFormated("CANT_BULDING_WARNING");
    end
    
    local data = {
        cursorMode = world_define.ModeToCursor[g_World:GetMode()],
        show = (bShow and g_LGuideManager:GetCanHandle()),
        left = x,
        top = y,
        bShowCanal = bShowCanal,
        bShowRoad = bShowRoad,
        bShowUpgrade = bShowUpgrade,
        strWarning = warnMsg,
    };
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_ShowContextMenu, data);
end
function LCommonProvider:UI2S_SwitchToNormalMode()
    g_World:SwitchMode(world_define.Mode.NORMAL);
end
function LCommonProvider:UI2S_SwitchToMoveMode()
    g_World:SwitchMode(world_define.Mode.MOVE);
    -- self:S2UI_SwitchToMoveMode();
    self:S2UI_UpdateBuildModeKeys(world_define.Mode.MOVE);
end
function LCommonProvider:S2UI_SwitchToMoveMode()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_SwitchToMoveMode);
    self:S2UI_UpdateBuildModeKeys(world_define.Mode.MOVE);
end
function LCommonProvider:UI2S_SwitchToDismantleMode()
    g_World:SwitchMode(world_define.Mode.DESTROY);
    self:S2UI_SwitchToDismantleMode();
end
function LCommonProvider:S2UI_SwitchToDismantleMode()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_SwitchToDismantleMode);
    self:S2UI_UpdateBuildModeKeys(world_define.Mode.DESTROY);
end
function LCommonProvider:UI2S_SwitchToUpgradeMode()
    g_World:SwitchMode(world_define.Mode.UPGRADE);
    self:S2UI_SwitchToUpgradeMode();
end
function LCommonProvider:S2UI_SwitchToUpgradeMode()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_SwitchToUpgradeMode);
    self:S2UI_UpdateBuildModeKeys(world_define.Mode.UPGRADE);
end
function LCommonProvider:S2UI_UpdateBuildModeKeys(mode)
    if g_GameWorld:IsInEditStatus() then
        return;
    end
    local tbAllKeys = self:GetAllBuildModeKeyInfo();
    if mode == world_define.Mode.DESTROY then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateBuildModeKeys, {
            tbKeys = {5,6,2},
            tbAllKeys = tbAllKeys,
        });
    elseif mode == world_define.Mode.MOVE then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateBuildModeKeys, {
            tbKeys = {1,2},
            tbAllKeys = tbAllKeys,
        });
    elseif mode == world_define.Mode.ATTACH then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateBuildModeKeys, {
            tbKeys = {3,4,2},
            tbAllKeys = tbAllKeys,
        });
    elseif mode == world_define.Mode.UPGRADE then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateBuildModeKeys, {
            tbKeys = {7,8,2},
            tbAllKeys = tbAllKeys,
        });
    end
end
-- 获取建造模式所有快捷键信息
function LCommonProvider:GetAllBuildModeKeyInfo()
    local tbKeyList = {};
    for _, key in ipairs(InputDefine.BUILD_MODE_KEY_INFO or {}) do
        table.insert(tbKeyList, {
            name = g_LRPDescManager:GetRPTextFormated(key.name),
            func =  g_LRPDescManager:GetRPTextFormated(key.func),
        })
    end
    return tbKeyList;
end
function LCommonProvider:S2UI_OnPushSystemTip(msg)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnPushSystemTip, msg);
end
--- 是否是产出人口建筑
---@param building any
function LCommonProvider:CheckIsProductPopulationBuilding(building)
    if building.__cname == "LBuildingHouse" or 
            building.__cname == "LBuildingCarftsMan" or 
                building.__cname == "LBuildingScholar" or  
                    building.__cname == "LBuildingRefugee" or  
                        building.__cname == "LBuildingMaid"  then 
        return true;
    end
    return false;
end
--- 是否是转换民居的建筑
---@param building any
function LCommonProvider:CheckIsChangeHouseBuilding(building)
    if building.__cname == "LBuildingHouse" or 
        building.__cname == "LBuildingCarftsMan" or 
            building.__cname == "LBuildingScholar" then
        return true;
    end
    return false;
end
function LCommonProvider:_GetBuildingCardInfo(building, bUpgrade)
    local wo = building and building:GetWorldObject();
    local bStatus, wx, wy, wz = wo:GetWorldPosition();
    local tileX, tileZ = wo:GetBoxTileNum();
    local bOk, nScreenX, nScreenY = g_CameraController:World2ScreenPos(wx,wy,wz);
    local _, x, y = g_WindowManager:GetClientMousePos();
    local data = {
        show = true,
        left = nScreenX,
        top  = nScreenY,
        bUpgrade = not not bUpgrade,
    };
    local isShowUpgrade = false;
    local nCurSeason            = g_Time:GetCurSeason();
    local buildingCard          = g_LBuildingCardManager:GetBuildingCardByGDPL(building:GetGDPL());
    local nextBuildingCard      = g_LBuildingCardManager:GetBuildingCardByGDPL(building:GetNextLevelGDPL());
    local metaData              = {};
    local tbProductVals         = building:GetAllResourceProduceValue();
    local tbNextProductVals     = building:GetAllResourceProduceValue(true);      -- 获取下一等级的卡面增益
    local tbGHProductVals       = building:GetAllResourceGreenHouseProduceValue(true);-- 获取开启大棚的卡面增益
    local tbNGHProductVals      = building:GetAllResourceGreenHouseProduceValue(false);-- 获取关闭大棚的卡面增益
    local tbMaintainCost        = building:GetAllResourceMaitenanceValue();
    local tbNextMaintainCost    = building:GetAllResourceMaitenanceValue(true);
    --local tbUpgradeCost         = building:GetAllUpgradeResourceValue();
    local uuid                  = building:GetWorldObject():GetWOUUID();
    local curPopulation         = building:GetCurPopulation();
    if self:CheckIsProductPopulationBuilding(building) then
        curPopulation = building:GetCurAllPopulation();
    end
    local canUpgrade, err       = g_BuildingWorldModule.BuildingMgr:CheckCanUpgradeBuilding(building);
    local canDestroy            = g_BuildingWorldModule:IsDestroyable(wo);
    local isShowProducts        = g_BuildingDefine.IS_SHOW_BUILDING_PRODUCTS(buildingCard);
    local isRuin                = building:GetWorldObject():IsRuin();
    local nReturnRatio          = building:GetReturnRatio();
    local nSpecialBuilding      = building.m_bIsSpecialBuilding;
    local DestroyTurnToRuin     = g_BuildingWorldModule:DestroyTurnToRuin(wo);
    local onPeaceBlock          = building:IsPeaceBlockBuilding();
    local demandContent         = g_DemandManager:GetDemandContent(building);
    local bFertilizerBuild      = building.m_bFertilizer or building.m_bFertilizerCollector;
    local bShowLevelInfo, strLevelInfo = g_HotelManager:GetBuildingLevelInfo(building);
        
    -- 判断buildtips升级栏是否可以显示，建筑资源不够等原因导致的无法升级需要显示升级栏
    local tbCanShowUpgradeErr = {
        "E_RESOURCES_NOT_ENOUGH",
        "E_UPGRADE_CHALLENGEBLOCK_SYNTHESIS",
        "E_UPGRADE_WHEN_TALENT_NOT_UNLOCKED",
        "E_UPGRADE_WHEN_TIME_NOT_ENOUGH",
    }
    for i,v in pairs(tbCanShowUpgradeErr) do
        if err == v then
            isShowUpgrade = true;
            break;
        end
        isShowUpgrade = canUpgrade;
        local blockId = building:GetBelongBlock();
        local block = g_blockMgr:GetBlock(blockId);
        if not block:IsPeaceBlock() then
            -- 判断是不是民居或谋士府
            for index, gdpl in ipairs(g_BuildingDefine.NormalUpgradeHideList or {}) do
                if ((gdpl[1] == 0) or gdpl[1] == building.G)
                and ((gdpl[2] == 0) or gdpl[2] == building.D)
                and ((gdpl[3] == 0) or gdpl[3] == building.P)
                and ((gdpl[4] == 0) or gdpl[4] == building.L) then
                    isShowUpgrade = false;
                    break;
                end
            end 
        end
    end
    if buildingCard then
        -- 这里card的数据只是用个结构
        metaData = table.copy(buildingCard:GetMetaData(), true);
        metaData.Desc     = building:ModifyCardDesc(metaData.Desc);
        metaData.ID       = uuid;
        metaData.L        = building.L;
        metaData.NextL    = nextBuildingCard:GetLevel();
        metaData.IsCard   = false;
        metaData.SizeX    = tileX or 0;
        metaData.SizeZ    = tileZ or 0;
        metaData.CurProducts        = building:GetCardProductInfo();                               -- 当前生产数值
        metaData.TabProducts        = building:GetCardProductInfo();                               -- 卡面原始生产数值
        metaData.NoGHProducts       = buildingCard:GetProductInfo();                               -- 建筑关闭大棚的实际产生数值
        metaData.NextProducts       = building:GetCardProductInfo(true);                           -- 建筑下一级别的实际生产数值，加了当前增益
        metaData.NextTabProducts    = building:GetCardProductInfo(true);                           -- 建筑下一级别的卡面生产数值
        metaData.GreenHouseProduct  = building:GetCardGreenHouseProductInfo();                     -- 建筑开启大棚的实际生产数值
        metaData.Maintain           = building:GeCardMaintainInfo();                               -- 建筑当前的维护费
        metaData.NextMaintain       = building:GeCardMaintainInfo(true);                           -- 建筑下一级别的维护费
        metaData.GreenHouseMaintain = building:GeCardGreenHouseMaintainInfo(true);                 -- 建筑开启大棚的维护费
        metaData.NoGHMaintain       = building:GeCardGreenHouseMaintainInfo(false);                -- 建筑关闭大棚的维护费
        metaData.DestroyCost        = building:GetBuildingDestroyInfo();                           -- 建筑拆除费用
        metaData.RebuildCost        = buildingCard:GetRebuildInfo();                               -- 季节产出查询
        metaData.ProductSeasonReivse = buildingCard:GetSeasonRevise();
        for k,v in pairs(metaData.RebuildCost) do 
            v.ResourceCost = building:CalculateAdviserAttributeInfluence(v.ResourceCost);           --计算收谋士属性影响后的值
        end
        metaData.BuildCost          = buildingCard:GetBuildCostInfo();
        metaData.CurPopulation      = math.floor(curPopulation);
        metaData.NextMaxPopulation  = math.floor(nextBuildingCard:GetMaxPopulation());                         -- 卡面下一等级的需求人口
        metaData.Upgrade            = buildingCard:GetUpgradeInfo();                                         -- 表示当前等级 升级到 下一个等级所需要的消耗
        for k,v in pairs(metaData.Upgrade) do 
            v.ResourceCost = building:CalculateAdviserAttributeInfluence(v.ResourceCost);           --计算收谋士属性影响后的值
        end
        metaData.BuildCost          = buildingCard:GetBuildCostInfo();
        metaData.Skills             = buildingCard:GetSkillsInfo();
        metaData.Type               = buildingCard:GetType();
        metaData.IsBlueprint        = buildingCard:IsBlueprint();
        metaData.IsUpgradable       = isShowUpgrade;
        metaData.IsDestroyable      = canDestroy;
        metaData.IsShowProducts     = isShowProducts;
        metaData.IsRuin             = isRuin;
        metaData.bIsPostStation     = building.bIsPostStation;
        if metaData.bIsPostStation then
            local obj = building:GetWorldObject();
            local platforms = obj:GetPlatformObject();
            metaData.nPlatformCount      = #platforms;
            metaData.nPlatformTotalCount = 4;
            metaData.bIsLackResources = building:IsShowLackResourceHeadEffect();
        end
        local nRuinId               = building:GetRuinsReason();
        if nRuinId == g_BuildingDefine.RuinsReason.Default then
            metaData.strRuinReason      = "";
        else
            metaData.strRuinReason      = g_LRPDescManager:GetRPTextFormated("RUIN_REASON_"..nRuinId);
        end
        metaData.WorldObjectUUID    = uuid;
        metaData.RuinName           = g_LRPDescManager:GetRPTextFormated("RUIN_NAME", {BuildingName = metaData.Name});
        metaData.nReturnRatio       = nReturnRatio;
        metaData.DestoryCost        = g_LRPDescManager:GetRPTextFormated("DEMOLITION_OF_THE_COST");
        metaData.ReturnCost         = g_LRPDescManager:GetRPTextFormated("DEMOLITION_OF_RETURN");
        metaData.MigrateCost        = g_LRPDescManager:GetRPTextFormated("COSTS_OF_MIGRATION");
        metaData.DisbandCost        = g_LRPDescManager:GetRPTextFormated("COSTS_OF_DISBAND");
        metaData.nSpecialBuilding   = nSpecialBuilding;
        metaData.onPeaceBlock       = onPeaceBlock;
        metaData.bAddProduction     = false;
        metaData.bAddRangeSkill     = false;
        metaData.bAddMarketStok     = false;
        metaData.AddRangeDesc       = "";
        metaData.AddProductionDesc  = "";
        metaData.AddMarketStokDesc  = "";
        metaData.DestroyTurnToRuin  = DestroyTurnToRuin;
        metaData.IsMaxLevel         = building:CheckIsMaxLevel();
        metaData.bContinueUpgrade   = building.L < g_BuildingDefine.NORMAL_MAX_LEVEL or g_BuildingWorldModule.BuildingMgr:GetAdvancedUpgrade();
        metaData.GreenHouseSeasonControlSwitch = building:GetGreenHouseControlSwitch();
        metaData.isGreenHouseControl = building and building:IsGreenHouseControl() or false;
        metaData.DemandContent      = demandContent;
        metaData.FertilizerInfo     = {
            bFertilizerBuild = bFertilizerBuild or false;
            bFertilizer = building.m_bFertilizer or false;
            bFertilizerCollector = building.m_bFertilizerCollector or false;
            nFertilizer = bFertilizerBuild and math.floor(building:GetCollectedFertilizer()) or 0;
            nFertilizerLimit = bFertilizerBuild and building:GetCollectedLimit() or 0;
            nFertilizerLevel = building.m_bFertilizer and building:GetFertilizerLevel() or 0;
            FertilizerDesc = bFertilizerBuild and g_LRPDescManager:GetRPTextFormated("FERTILIZER_TIPS_DISPLAYNUMBERINFO", {
                CurrentNumber = math.floor(building:GetCollectedFertilizer()),
                MaxNumber = building:GetCollectedLimit(),
            });
        };
        metaData.bExploration = building.m_bExploration or false;
        metaData.nSkinId = building:GetSkinId() or 0;
        if  building.G == g_BuildingDefine.EXPLORATION_MARKER_GDPL[1] and building.D == g_BuildingDefine.EXPLORATION_MARKER_GDPL[2] and building.P == g_BuildingDefine.EXPLORATION_MARKER_GDPL[3] then
            metaData.bExplorationMarker = true;
        else
            metaData.bExplorationMarker = false;
        end
        if self:CheckIsProductPopulationBuilding(building) then
            metaData.MaxPopulation = building:GetFullMaxPopulation();    
            metaData.NextMaxPopulation = building:GetNextFullMaxPopulation();
        end
        -- 活动建筑建筑不显示拆除按钮
        if (building.D == g_BuildingDefine.detail.FESTIVAL) then
            metaData.IsDestroyable = false;
        end
        -- 户籍司需要实时显示建造进度
        if self:_IsAddBuildProgressInDesc(building) then
            local addText = "";
            if building:GetStatus() == g_BuildingStatus.BS_BUILDING then
                local function transTime(sec)
                    return math.ceil((sec or 0) / LTimeDefine.SECONDS_PER_DAY);
                end
            
                local totalTime = wo and wo.TotalBuildTime or 0;
                -- local curBuildTime = math.max(g_Time:GetCurTime() - wo.BuildTimestamp, 0);
                local leftProgress = 0;
                local progressBar = wo and wo.m_ProgressBar;
                if progressBar then
                    leftProgress = math.max(1 - progressBar:GetProgress(), 0);
                end
                local leftSec = math.roundf(leftProgress / progressBar.m_fAdvanceStep);
                -- local curBuildDay = transTime(leftSec);
                local leftDay = transTime(leftSec);
                local totalDay = transTime(totalTime);
                addText = g_LRPDescManager:GetRPTextFormated("CENSUS_PROGRESS_LEFT", {leftBuildTime = math.max(leftDay, 0)});
            end
            if addText and addText ~= "" then
                metaData.Desc = metaData.Desc .. "<br>" .. addText;
            end
        end
        
        -- 奇观建筑需要返回实际数据(包含子建筑),不能只返回卡牌(奇观底座)的数据
        if wo.bIsWonderBuild then
            local wonder = wo:GetWonder();
            local desc = building:GetMergeDescEnhanced();
            metaData.Desc = building:ModifyCardDesc(desc);
            -- 修改产出数值(当前产出和基础产出)
            for index, vItem in ipairs(metaData.CurProducts) do
                local typeItem = metaData.CurProducts[index] and metaData.CurProducts[index][1];
                if typeItem then
                    for i = 2, #(metaData.CurProducts[index]) do
                        metaData.CurProducts[index][i] = math.floor(tbProductVals[typeItem.ResourceID][3]);
                        metaData.TabProducts[index][i] = math.floor(tbProductVals[typeItem.ResourceID][3]);
                    end
                end
            end
            -- 修改最大人口数
            metaData.MaxPopulation = building:GetMaxPopulation();
            if wonder:IsWonderFinish() and building.P == 7 then
                local rpdesc = g_LRPDescManager:GetRPTextFormated("CONFIRM_SPECTACLE_SQ_CONTENT");
                metaData.RpDesc = rpdesc;
            end
            if not wonder:IsWonderFinish() and not wonder:IsTempWorking() then
                metaData.WonderTips = g_LRPDescManager:GetRPTextFormated("WONDER_NOT_WORKING_TIPS");
            end
        end
        if building.D == g_BuildingDefine.detail.HOTEL then
            if building.P == 1 then
                local landMarkBuilding = g_HotelManager:GetLandMarkBuilding();
    
                -- 修改产出数值(当前产出和基础产出)
                for index, vItem in ipairs(metaData.CurProducts) do
                    local typeItem = metaData.CurProducts[index] and metaData.CurProducts[index][1];
                    if typeItem then
                        for i = 2, #(metaData.CurProducts[index]) do
                            metaData.CurProducts[index][i] = math.floor(tbProductVals[typeItem.ResourceID][3]);
                            metaData.TabProducts[index][i] = math.floor(tbProductVals[typeItem.ResourceID][3]);
                        end
                    end
                end
    
                -- 修改最大人口数
                metaData.MaxPopulation = landMarkBuilding:GetMaxPopulation();
            else
                metaData.MaxPopulation = 0;
            end
        end
        -- 景区大门
        if building.D == g_BuildingDefine.detail.BASICS and building.P == g_BuildingDefine.ATTRACTION_GATE_GDPL[3] then
            -- 修改产出数值(当前产出和基础产出)
            for index, vItem in ipairs(metaData.CurProducts) do
                local typeItem = metaData.CurProducts[index] and metaData.CurProducts[index][1];
                if typeItem then
                    for i = 2, #(metaData.CurProducts[index]) do
                        metaData.CurProducts[index][i] = math.floor(tbProductVals[typeItem.ResourceID][3]);
                        metaData.TabProducts[index][i] = math.floor(tbProductVals[typeItem.ResourceID][3]);
                    end
                end
            end
        end
        -- 景点
        if building.D == g_BuildingDefine.detail.SITE then
            local siteId = building.P;
            local scenicSpot = g_LSightSeeingManager:GetScenicSpot();
            if scenicSpot then
                local addDesc = scenicSpot:GetScenicSiteDecs(siteId) or "";
                local connectDesc = "";
                if not building:IsRuin() then
                    local isConnect = scenicSpot:GetSiteBuildingIsConnect(siteId);
                    connectDesc = g_LRPDescManager:GetRPTextFormated(isConnect and "SCENIC_SPOT_CONNECTED_ATTRACTION_TIPS" or "SCENIC_SPOT_UNCONNECTED_ATTRACTION_TIPS");
                end
                metaData.Desc = metaData.Desc .. addDesc .. connectDesc;
            end
            metaData.ScenicInfo = true;
        end
        --- 留民营显示落户信息
        if building.bRefugee then
            metaData.bRefugee = true;
            metaData.SettleDataDesc = building:GetRefugeeSettleDataDesc();
        end
            
        if bShowLevelInfo then
            metaData.LevelInfo = strLevelInfo;
        end
        if building.m_bExploration then
            metaData.explorationResult = g_LExplorationManager:GetBuildTipsContent(building);
        end
        -- 获取当前等级products增益后的值
        for index, vItem in ipairs(metaData.CurProducts) do
            local typeItem = metaData.CurProducts[index] and metaData.CurProducts[index][1];
            if typeItem then
                metaData.CurProducts[index][nCurSeason + 1] = math.floor(tbProductVals[typeItem.ResourceID][1]);
            end
        end
        -- 获取下一等级products增益后的值
        for index, vItem in ipairs(metaData.NextProducts) do
            local typeItem = metaData.NextProducts[index] and metaData.NextProducts[index][1];
            if typeItem then
                metaData.NextProducts[index][nCurSeason + 1] = math.floor(tbNextProductVals[typeItem.ResourceID][1]);
            end
        end
        -- 获取开启大棚products增益后的值
        for index, vItem in ipairs(metaData.GreenHouseProduct) do
            local typeItem = metaData.GreenHouseProduct[index] and metaData.GreenHouseProduct[index][1];
            if typeItem then
                metaData.GreenHouseProduct[index][nCurSeason + 1] = math.floor(tbGHProductVals[typeItem.ResourceID][1]);
            end
        end
        -- 获取关闭大棚products增益后的值
        for index, vItem in ipairs(metaData.NoGHProducts) do
            local typeItem = metaData.NoGHProducts[index] and metaData.NoGHProducts[index][1];
            if typeItem then
                metaData.NoGHProducts[index][nCurSeason + 1] = math.floor(tbNGHProductVals[typeItem.ResourceID][1]);
            end
        end
        for index, vItem in ipairs(tbMaintainCost) do
            local nResourceId, nResourceV = table.unpack(vItem);
            if metaData.Maintain[index] then
                metaData.Maintain[index].ResourceCost = nResourceV;
            else
                local resource = g_LResourceManager:GetResource(nResourceId);
                metaData.Maintain[index] = {
                    ResourceName = resource:Get(resource.ATTRS.ResourceName),
                    ResourceIcon = resource:Get(resource.ATTRS.ResourceIcon),
                    ResourceCost = nResourceV,
                    ResourceId = nResourceId,
                };
                
            end
        end
        for index, vItem in ipairs(tbNextMaintainCost) do
            local nResourceId, nResourceV = table.unpack(vItem);
            if metaData.NextMaintain[index] then
                metaData.NextMaintain[index].ResourceCost = nResourceV;
            else
                local resource = g_LResourceManager:GetResource(nResourceId);
                metaData.NextMaintain[index] = {
                    ResourceName = resource:Get(resource.ATTRS.ResourceName),
                    ResourceIcon = resource:Get(resource.ATTRS.ResourceIcon),
                    ResourceCost = nResourceV,
                    ResourceId = nResourceId,
                };
                
            end
        end
        -- 净收入
        metaData.Pure = self:_CalculatePureProduct(metaData.CurProducts,metaData.Maintain);
        metaData.NextPure = self:_CalculatePureProduct(metaData.NextProducts,metaData.NextMaintain);
        metaData.GreenHousePure = self:_CalculatePureProduct(metaData.GreenHouseProduct,metaData.GreenHouseMaintain);
        metaData.NoGHPure = self:_CalculatePureProduct(metaData.NoGHProducts,metaData.NoGHMaintain);
        metaData.belongblockId = building:GetBelongBlock();
        local block = g_blockMgr:GetSelectedBlock();
        metaData.CardChain, metaData.AffectBuilding = g_BuildingIndustryChain:GetUniqueBuildingMap(block,metaData.G, metaData.D, metaData.P);
        metaData.IsHaveContent = g_LRPDescManager:GetRPTextFormated("UNOWNED_CARD");
        metaData.bConnectedToPost = building:GetIsConnectedToPost(true);
        metaData.bInOutsideCanalRange = not building.bInCanalRange;
        metaData.bIsGreenHouse = building.GreenHouse and true or false;
        metaData.bIsShipyard = building.bShipyard or false;
        -- 是否是造船坊
        if metaData.bIsShipyard then
            metaData.bUnlockSailing = g_ChartArea:IsUnlockSailing();
            metaData.ShipLockData = building:GetCanCreateShipData();
            metaData.bCreatingShip = building.bCreating;
            metaData.nCreateShipType = building:GetCreatingShipType();
            metaData.nProgressPercent = building:GetShipCreatePercent() or 0; 
            metaData.CreateShipNumber = building:GetCreateShipNumber() or {};
            metaData.ShipQuantity = g_ShipTemplate:GetShipMapQuantity() or {};
            -- 是否显示遮罩
            local working = true;
            working = working and building:GetStatus() == g_BuildingStatus.BS_FINISHED;
            local nNeedPopulation = building:GetNeedPopulation();
            working = working and nNeedPopulation <= 0;
            working = working and not building:IsInNormalDisaster();
            metaData.bShowShipyardMask = not working;
        end
        metaData.bShwoDrawWaterLevel = g_BuildingWorldModule.BuildingMgr:CheckIsLandDrawWaterBuilding(building.G,building.D,building.P);
        if metaData.bShwoDrawWaterLevel then
            metaData.nDrawWaterLevel = wo:GetWaterLevel();
            if building.AddWaterNum == wo:GetMaxAddWaterCount() then
                metaData.addWaterNum = g_LRPDescManager:GetRPTextFormated("PUMP_WATERUSAGE_DISPLAYMAX", {
                    CurrentNum = building.AddWaterNum,
                    MaxNum = wo:GetMaxAddWaterCount()
                });
            else
                metaData.addWaterNum = g_LRPDescManager:GetRPTextFormated("PUMP_WATERUSAGE_DISPLAY", {
                    CurrentNum = building.AddWaterNum,
                    MaxNum = wo:GetMaxAddWaterCount()
                });
            end
            
        end
        --- 获取产业链总加成
        if g_BuildingIndustryChain:GetIsUnlock() then
            metaData.nAllIndustryChainAddProduct =( building.GetAllIndustryChainAddProduct and building:GetAllIndustryChainAddProduct() or 0)/ define.CARDINAL_NUMBER * 100;
            if metaData.nAllIndustryChainAddProduct > 0 then
                metaData.IndustryChainTitle = g_LRPDescManager:GetRPTextFormated("BUILDING_TIPS_INDUSTRY_CHAIN_TITLE");
                metaData.IndustryChainDesc = g_LRPDescManager:GetRPTextFormated("BUILDING_TIPS_INDUSTRY_CHAIN_ADDOUTPUT",{Attribute = metaData.nAllIndustryChainAddProduct});
                metaData.bShowFullIndustryChainIcon = building:GetFullIndustryChainCuont() > 0;
            end
        end
        --------- 精华建筑的数据---------------
        metaData.bQuintessence = building.bQuintessence and true or false; -- 是否是精华萃取建筑
        if metaData.bQuintessence then
            metaData.QuintessenceProductSpeed = math.floor(building:GetQuintessenceProductionSpeed()) ; -- 获取精华产出速度
            metaData.QuintessenceProductPercent = math.floor(building:GetCurQuintessenceProductionPercent() / 100) /100 ; -- 获取精华产出的百分比(保留小数点后两位)
            metaData.QuintessenceConsume = building:GetPerDayConsumeSourceValue();
            metaData.StoreSourceMaxValue = building:GetStoreSourceMaxValue();   -- 精华萃取器存储资源的最大值
            metaData.StoreSource = building:GetStoreSource();   -- 获取存储的资源
            metaData.bCanGenerateQuintessence = building:CanGenerateQuintessence();
            metaData.LackSourceDesc = building:GetLackSourceDesc(); -- 缺乏资源的描述
            metaData.bShowLackSourceDesc = building:GetCurCanConsumeStoreTypeNum() ~= table.getSize(metaData.StoreSource);
            metaData.dayDesc = g_LRPDescManager:GetRPTextFormated("TXT_DAY_COMMON");
            metaData.CarDataDesc = building:DumpCarDataDesc();
            metaData.CarDataTitle = g_LRPDescManager:GetRPTextFormated("BUILDING_TIPS_QUINTESSENCE_CAR_INF_TITLE");
            metaData.hintDesc = g_LRPDescManager:GetRPTextFormated("BUILDING_TIPS_QUINTESSENCE_WARNING_02",{
                ProductionSpeed = math.floor(building:GetPerDayAddMaxPercent()),
                Productivity = building:GetQuintessenceProductionSpeedBySourceTypeNum()/define.CARDINAL_NUMBER * 100,
                Cost = building:GetPerDayConsumeSourceValue();
            });
            metaData.hintTitle = g_LRPDescManager:GetRPTextFormated("BUILDING_TIPS_QUINTESSENCE_RESOURCE_INF_TITLE")
        end
        -- 码头
        metaData.bIsHarbour = building.bIsHarbour or false;
        if metaData.bIsHarbour then
            metaData.tbResource = building:GetCurAllSource();
            metaData.bInPrepare = building:GetIsInPrepare();
            if metaData.bInPrepare then
                metaData.preparingNum = building:GetCurAllSourceNum();
                metaData.preparingMax = building:GetPreparingTargetNum();
                metaData.prepareTip = g_LRPDescManager:GetRPTextFormated("TXT_BUILDING_WHARF_TEXT_01");
            end
        end
        -- 驿站
        metaData.bIsPostStation = building.bIsPostStation or false;
        if not metaData.bIsHarbour and metaData.bIsPostStation then
            local name = building:GetStationName();
            if name and name == "" then
                name = g_LRPDescManager:GetRPTextFormated("TRAIN_SANDBOX_POST_NAME",{Index = ""});
            end
            metaData.Name = name;
        end
        --- 是否是防汛所
        metaData.bIsFloodControl = false;
        metaData.bShowGrayRepairBtn = false;
        if building.D == g_BuildingDefine.FLOOD_CONTROL[2] and building.P == g_BuildingDefine.FLOOD_CONTROL[3] then
            metaData.bIsFloodControl = true;
            metaData.bShowGrayRepairBtn = building:IsFullHp();
            metaData.RepairSourceData = {};
            for sourceType,sourceValue in pairs(g_BuildingDefine.RepairFloodControlSource) do 
                -- table.insert(metaData.RepairSourceData,{sourceType,sourceValue})
                local resource = g_LResourceManager:GetResource(sourceType);
                table.insert(metaData.RepairSourceData,{icon = resource:Get(resource.ATTRS.ResourceIcon),targetVal = sourceValue})
            end
            
            metaData.RepairTitle = g_LRPDescManager:GetRPTextFormated("BUILDING_REPAIR_TITLE");
        end
        -- 宗教建筑
        metaData.bIsReligion = building.m_bReligion or false;
        if metaData.bIsReligion then
            metaData.religionType = building:GetReligionType();
            metaData.incenseValue = building:GetIncenseValue();
            metaData.incenseValueMax = building:GetIncenseValueMax();
            metaData.religionDecs = g_LRPDescManager:GetRPTextFormated("RELIGION_BUILDING_DECS");
            metaData.bIncenseFull = building:IsFull();
            metaData.tbReligionSkills = building:DumpReligionSkillsInfo();
        end
        -- 风水
        metaData.bFSOpened = false;
        local fsComponent = wo:GetFengshuiComponent();
        if not not fsComponent then
            metaData.bUnActiveInHotel = fsComponent:IsUnActiveInHotel();
            metaData.tbFengshuiState = fsComponent:GetFengShuiStates();
            metaData.bFSOpened = g_LFengshuiManager:IsUnlock() and (not not metaData.tbFengshuiState or not not metaData.bUnActiveInHotel);
            if metaData.tbFengshuiState ~= nil then
                local fierceNum = fsComponent:GetFierceFengShuiCount();
                if fierceNum == 3 then -- 三凶
                    metaData.fsStateDesc = g_LRPDescManager:GetRPTextFormated("FS_RESULT_FIERCE_3");
                elseif fierceNum == 4 then -- 四凶
                    metaData.fsStateDesc = g_LRPDescManager:GetRPTextFormated("FS_RESULT_FIERCE_4");
                elseif fierceNum == 5 then -- 五凶
                    metaData.fsStateDesc = g_LRPDescManager:GetRPTextFormated("FS_RESULT_FIERCE_5");
                end
            end
        end
        --繁荣度加成
        local tbDevelopment = building:GetDevelopment();
        if  tbDevelopment and #tbDevelopment > 0 then
            for _, info in pairs(tbDevelopment) do
                local text = "PROSPERITY_AGRIGULTURAL_ADD";
                if info[1] == 2 then
                    text = "PROSPERITY_AGRIGULTURAL_ADD";
                elseif info[1] == 3 then
                    text = "PROSPERITY_MANUAL_ADD";
                elseif info[1] == 4 then
                    text = "PROSPERITY_BUSINESS_ADD";
                elseif info[1] == 5 then
                    text = "PROSPERITY_ENTERTAINMENT_ADD";
                elseif info[1] == 6 then
                    text = "PROSPERITY_CULTURE_ADD";
                elseif info[1] == 11 then
                    text = "PROSPERITY_LANDSCAPE_ADD";
                end
                local data = g_LRPDescManager:GetRPTextFormated(text, {
                    value = info[2],
                });
                metaData.prosperity = metaData.prosperity or {};
                table.insert(metaData.prosperity, data);
            end
        else
            metaData.prosperity = nil;
        end
    end
    data.card = metaData;
    return data;
end
function LCommonProvider:_CalculatePureProduct(CurProducts, MaintainMonth)
    local nCurSeason = g_Time:GetCurSeason();
    local tbMaintainMonth = {};
    for index, vItem in ipairs(MaintainMonth) do
        tbMaintainMonth[vItem.ResourceId] = vItem.ResourceCost;
    end
    local tbPure = {};
    for index,curProduct in ipairs(CurProducts) do
        local nResourceId = CurProducts[index][1].ResourceID;
        local maintainSingle =  tbMaintainMonth[nResourceId] or 0;
        local resourceSingle = math.floor((CurProducts[index][nCurSeason + 1]) -  maintainSingle);
        if nResourceId <= block_define.SOURCE_NORMAL_END 
            or nResourceId == block_define.SOURCE.SALT or nResourceId == block_define.SOURCE.LIQUOR then -- CurProducts[index][nCurSeason + 1] ~= 0
            local resource = g_LResourceManager:GetResource(nResourceId);
            table.insert(tbPure,{
                ResourceName = resource:Get(resource.ATTRS.ResourceName),
                ResourceIcon = resource:Get(resource.ATTRS.ResourceIcon),
                ResourceCost = resourceSingle,
                ResourceId = nResourceId,
            });
        end
    end
    return tbPure;
end
---
--- @param data table
--- @param building LBuilding
---
function LCommonProvider:_ModifySpecialEffectBuildingTips(data, building)
    if building and data then
        data = building:ModifyTips(data);
    end
    return data;
end
function LCommonProvider:_IsAddBuildProgressInDesc(building)
    local retBool = false;
    for index, GDPLs in ipairs(g_BuildingDefine.BuildingNeedPreviewBuildTime or {}) do
        local GDPL = GDPLs[1];
        if (building.G == GDPL[1] and 
            building.D == GDPL[2] and 
            building.P == GDPL[3]) then
                retBool = true;
                break;
        end
    end
    return retBool;
end
function LCommonProvider:GetBuildTipsInfo(building,bUpgrade)
    local data = self:_GetBuildingCardInfo(building, bUpgrade) ;
    local tbProductVals   = building:GetAllResourceProduceValue();
    local nCurSeason            = g_Time:GetCurSeason();
    data.tbProductVals = tbProductVals;
    data.seasonText = g_LRPDescManager:GetRPTextFormated("SEASON_FOR_PRODUCT_"..nCurSeason);
    local belongBlock = building:GetBelongBlock();
    local challengeBlock = g_blockMgr:GetChallengingBlock();
    local wo = building:GetWorldObject();
    data.buildingUUID = building:GetUUID();
    data.isBelongChallenge = challengeBlock and belongBlock == challengeBlock:GetBlockID() or false;
    data.Skin = g_LSkinManager:GetCurSkinByGDPL(building.G,building.D,building.P,building.L);
    data.isGreenHouseType =  building:CheckHaveGreenHouseIcon();
    local bOpenGreenHouse = building and building:IsShowGreenHouseOpen() or false;
    data.isGreenHouseControl = building and building:IsGreenHouseControl() or false;
    data.isOpenGreenHouse = bOpenGreenHouse;
    data.isOffice = building and building:IsOfficeBuilding() or false;
    data.isShowRoadSpeech = false;
    data.isRSUnlock = g_FunctionManager:CheckFuncIsUnlock(g_functionType.RIDE_HORSE) == g_functionState.OPEN;
    data.isAttackObservatory = false;
    data.curSoldier = building:GetCurSoldier();
    data.maxSoldier = building:GetMaxSoidler();
    data.isShowSoldier = building:IsShowSoldier();
    data.isEnemy = building:IsEnemy();
    data.WorkingPopulation = 0;
    data.isProductPopulation = false;
    data.isChangeHouse  = false;
    data.buildingStatus = building:GetStatus() or g_BuildingStatus.BS_BUILDING;
    data.nSelectHouseType = g_BuildingDefine.UNIVERISTY_TYPE.NORMAL;
    local layerId = building:GetGeologicMapLayerID();
    local bShowLayerInfo = true;
    bShowLayerInfo = bShowLayerInfo and layerId ~= g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE.DEFAULT;
    bShowLayerInfo = bShowLayerInfo and layerId ~= g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE.GRIDMASK;
    bShowLayerInfo = bShowLayerInfo and layerId ~= g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE.DEEPMINE;
    bShowLayerInfo = bShowLayerInfo and layerId ~= g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE.DEEPWATER;
    bShowLayerInfo = bShowLayerInfo and not building.m_bExploration;
    if bShowLayerInfo then
        data.layerId = layerId;
        local suffix = g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE_Suffix[layerId];
        local desc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_TITLE_"..suffix)
        local lWorldObject = building:GetWorldObject();
        data.icon = lWorldObject:GetGeologicMapLayerIcon();
        ---如果建筑是抽水机 并且全部在水上时 资源分布要显示丰富
        if lWorldObject.bBuildOnWater and lWorldObject:CheckTilesOnWater() then
            local capacity = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_LEVEL0"..5)
            data.layerDesc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_DESC", {
                Layer = desc,
                Level = capacity,
            });
        else
            local suffix = g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE_Suffix[data.layerId];
            local desc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_TITLE_"..suffix.."_STICKY")
            local capacity = lWorldObject:GetGeologicMapCapacityLevel(true);
            data.layerDesc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_DESC", {
                Layer = desc,
                Level = capacity,
            })
            local wo = building:GetWorldObject();
            ---林地加成显示
            local bSawmill = g_BuildingWorldModule:CheckMouseObjectIsSawillBuilding(wo);
            if bSawmill then
                g_BuildingWorldModule:ForceGetCacheObjectRangeBuildingObjects(wo);
                local nSawmillEffectValue = g_BuildingWorldModule:FrameGetIsProductAddOrDown();
                local strSawmillEffectDesc = "";
                if nSawmillEffectValue == 1 then
                    strSawmillEffectDesc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_FOREST_EX_01");
                elseif nSawmillEffectValue == 2 then
                    strSawmillEffectDesc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_FOREST_EX_02");
                end
                data.layerDesc = string.format("%s%s", data.layerDesc, strSawmillEffectDesc);
                g_BuildingWorldModule:ClearCacheMouseObjectRangeBuilding();
            end
            data.icon = wo:GetGeologicMapLayerIcon();
            -- if not setDesc then
            --     data.layerDesc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_DESC", {
            --         Layer = desc,
            --         Level = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_LEVEL0"..maxLevel),
            --     })
            -- end
        end     
    end
    if self:CheckIsProductPopulationBuilding(building) then
        data.WorkingPopulation    = building:GetWorkingPopulation();
        data.isProductPopulation  = true;
    end
    ---产出型建筑并且
    local nTipsType = building:GetBuildingTipsType();
    if nTipsType == g_BuildingDefine.BuildTipsType.Product then
        local bForest = g_LBuildingFuncManager:IsCheckFuncBuilding(BuildingFuncDefine.FUNC_TYPE.FOREST, building.G, building.D, building.P);
        data.bForest = bForest;
    end
    --天工坊建筑
    if nTipsType == g_BuildingDefine.BuildTipsType.Research then
        data.tbRdData = g_LWorkShopManager:DumpWorkShopBuildingInfo(building);
    end
    if nTipsType == g_BuildingDefine.BuildTipsType.Jisi then
        data.tbSacrificeData = building:DumpSacrificeInfo();
    end
    if self:CheckIsChangeHouseBuilding(building) then
        if building.__cname == "LBuildingHouse" then
            data.nSelectHouseType = g_BuildingDefine.UNIVERISTY_TYPE.NORMAL;
        elseif building.__cname == "LBuildingCarftsMan" then
            data.nSelectHouseType = g_BuildingDefine.UNIVERISTY_TYPE.CRAFTSMAN;
        elseif building.__cname == "LBuildingScholar" then
            data.nSelectHouseType = g_BuildingDefine.UNIVERISTY_TYPE.SCHOOLER;
        end
        data.isChangeHouse = g_LPopulationManager:CheckIsUnlockChangeHouse();
        -- 民居升级资源百分比
        data.UpgredeSourcePercent = building:GetUpgradeSourcePercent();
        -- 民居降级相关数据
        data.DowngradeInfo = building:GetDowngradeInfo();
    end
    if building.__cname == "LBuildingObservatory" then
        if  building:GetBattleCamp() == g_Battle_define.BATTLE_CAMP_TYPE.PEACE and building:IsFullCD() and not building:IsEmpty() then
            data.isAttackObservatory = true;
        end
    end
    if data.isOffice then
        data.UpgradeInfo = building:DumpUpgradeInfo();
        local wo = building:GetWorldObject();
        local _, bHasRoad = wo:GetSurroundingRoadTiles();
        if bHasRoad then
            data.isShowRoadSpeech = true;
        else
            data.roadSpeechTips = g_LRPDescManager:GetRPTextFormated("ROADSPEECH_START_WARNING2");
        end
    end
    
    if building.isFestival and g_LGuideManager:IsGuideEnd() then
        data.isShowGift = true;
    end
    data.buildStateDesc = self:_GetBuildStateDesc(building, bUpgrade);
    
    self:_ModifySpecialEffectBuildingTips(data, building);
    return data;
end
function LCommonProvider:_CheckIsSameTable(tb1, tb2)
    local bRet = true;
    bRet = bRet and self:_SubCheckIsSameTable(tb1, tb2);
    bRet = bRet and self:_SubCheckIsSameTable(tb2, tb1);
    return bRet;
end
function LCommonProvider:_SubCheckIsSameTable(tb1, tb2)
    local bRet = true;
    if type(tb1) ~= type(tb2) then
        bRet = false;
        return bRet;
    end
    if type(tb1) ~= "table" then
        return tb1 == tb2;
    end
    for k,v in pairs(tb1) do
        if bRet and type(tb2[k]) ~= type(v) then
            bRet = false;
            break;
        end
        if bRet and type(v) ~= "table" and v ~= tb2[k] then
            bRet = false;
            break;
        end
        if bRet and type(v) == "table" then
            bRet = self:_CheckIsSameTable(v, tb2[k]);
        end
        if not bRet then
            break;
        end
    end
    return bRet;
end
function LCommonProvider:_UpdateTipsInfoPerDay()
    local wouuid = g_World:GetSelectedWOUUID();
    local wo = g_World:GetWorldObject(wouuid);
    if not wo then
        return;
    end
    local nWorldModuleId = g_World:GetWorldObjectModuleId(wouuid);
    if nWorldModuleId ~= world_define.ModuleID.BUILDING_MGR then
        return;
    end
    local sBuild = wo and wo:GetBuilding();
    if not sBuild then
        wouuid = g_World:GetMouseHoverWOUUID();
        wo = g_World:GetWorldObject(wouuid);
        sBuild = wo and wo.GetBuilding and wo:GetBuilding();
    end
    local data = sBuild and sBuild:GetUpdateTipsInfo();
    if sBuild and next(data or {}) then
        if not self:_CheckIsSameTable(data, self.updatedTipsInfo) then
            g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateBuildTipsSelectedInfo, data);
        end
        self.updatedTipsInfo = data;
    else
        g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_TIME, g_TimeEventType.NEW_DAY, self._UpdateTipsInfoPerDay, self);    
        self.updatedTipsInfo = nil;
    end
end
function LCommonProvider:S2UI_OnUpdateTipsInfoPerDay()
    g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_TIME, g_TimeEventType.NEW_DAY, self._UpdateTipsInfoPerDay, self);
    g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_TIME, g_TimeEventType.NEW_DAY, self._UpdateTipsInfoPerDay, self);
end
function LCommonProvider:UI2S_WonderEntryTipsUpdatePerDay(state)
    if state then
        g_EventDispatcherManager:AddEventListener(g_EventModel.LEVENT_TIME, g_TimeEventType.NEW_DAY, g_LWonderManager.UI2S_GetWonderInfos, g_LWonderManager);
    else
        g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_TIME, g_TimeEventType.NEW_DAY, g_LWonderManager.UI2S_GetWonderInfos, g_LWonderManager);
    end
end
-- function LCommonProvider:S2UI_OnCancelUpdateTipsInfoPerDay()
--     g_EventDispatcherManager:RemoveEventListener(g_EventModel.LEVENT_TIME, g_TimeEventType.NEW_DAY, self._UpdateTipsInfoPerDay, self);
-- end
---
--- @param building LBuilding
--- @param bUpgrade boolean
---
function LCommonProvider:S2UI_OnBuildingSelected(building, bUpgrade)
    if not building then
        return;
    end
    if building:IsGenerateAdviser() then
        return;
    end
    
    local data = self:GetBuildTipsInfo(building,bUpgrade);
    if building:NeedUpdateTipsInfo() then
        g_LHBUIProvider:EmitTo("LCommonProvider", g_LHBUIEvents.S2UI_OnUpdateTipsInfoPerDay, building);
    end
    local nBlock = building:GetBelongBlock();
    local sBlock = g_blockMgr:GetBlock(nBlock);
    if g_LGuideManager:IsGuiding() then
        local wo = building:GetWorldObject();
        local uuid = wo:GetWOUUID();
        if g_LGuideManager:IsCheckLimit("Destroy",uuid) then
            data.bIsLimitDestroy = true;
        end
        if g_LGuideManager:IsCheckLimit("Rebuild",uuid) then
            data.bIsLimitRebuild = true;
        end
        if g_LGuideManager:IsCheckLimit("Upgrade",uuid) then
            data.bIsLimitUpgrade = true;
        end
    end
    if sBlock:IsPeaceBlock() then
        repeat
            local buildingWO = building:GetWorldObject();
            if buildingWO.configShowBuildTips == false then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnNeutralBuildUnHovered);
                return;
            elseif buildingWO.configShowBuildTips == true then
                break;
            end
            if not g_LGuideManager:IsGuideEnd() then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnNeutralBuildUnHovered);
                return;
            end
            if not sBlock:IsShowBuildTips()
            and not building.isFestival 
            and not building.m_bExplorationCenter then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnNeutralBuildUnHovered);
                return;
            end
            
        until true
    end
    ---- 区分建筑tips类型 拆分tips
    local nTipsType = building:GetBuildingTipsType();
    if sBlock:IsPeaceBlock() then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnNeutralBuildingSelected,data);
    elseif nTipsType == g_BuildingDefine.BuildTipsType.House then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingHouseSelected,data);
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Product then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingProductSelected,data);  
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Religion then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingReligionSelected,data);  
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Barn then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingBarnSelected,data); 
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Ship then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingShipSelected,data);  
    elseif nTipsType == g_BuildingDefine.BuildTipsType.OverWinter then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingOverWinterSelected,data);
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Pick then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingPickSelected,data);
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Port then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingPortSelected,data);
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Manure then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingManureSelected,data);
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Research then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingResearchSelected,data);
    elseif nTipsType == g_BuildingDefine.BuildTipsType.Jisi then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingJisiSelected,data);
    else
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingSelected,data);
    end
end
function LCommonProvider:S2UI_UpdateBuildTipsInfo(building,bUpgrade)
    local data = self:GetBuildTipsInfo(building,bUpgrade);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateBuildTipsInfo,data);
end
function LCommonProvider:S2UI_OnBuildingUnSelected()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnNeutralBuildingUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingBarnUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingShipUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingOverWinterUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingPickUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingPortUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingManureUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingHouseUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingProductUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingReligionUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingResearchUnSelected);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingJisiUnSelected);
end
--- 获取建筑状态desc
---@param building any
---@param bUpgrade any
function LCommonProvider:_GetBuildStateDesc(building, bUpgrade)
    local tbbuildStateDesc = {};
    local data = self:_GetBuildingCardInfo(building, bUpgrade) ;
    -- 注意这是引用, 不要随意修改
    local buildingCard = data.card;
    local wo = building:GetWorldObject();
    if buildingCard.bConnectedToPost and not buildingCard.IsRuin then
        local PostConnectText = g_LRPDescManager:GetRPTextFormated("POST_NOPRODUCE_TIPS");
        table.insert(tbbuildStateDesc, {desc = PostConnectText});
    end
    if buildingCard.bIsPostStation and not buildingCard.IsRuin and buildingCard.bIsLackResources then
        local desc = g_LRPDescManager:GetRPTextFormated("E_LACK_OF_RESOURCE");
        table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.PostLackResources});
    end
    local demandContent = g_DemandManager:GetDemandContent(building);
    if demandContent ~= "" then
        table.insert(tbbuildStateDesc, {desc = demandContent, type = g_BuildingDefine.HintImgPathType.DemandContent});
    end
    if building:CheckIsNeedInCanalWater() then
        local OutsideCanalRangeDesc = g_LRPDescManager:GetRPTextFormated("BUILDINGWITHOUT_CANAL");
        data.OutsideCanalRangeDesc = OutsideCanalRangeDesc;
        if buildingCard.bInOutsideCanalRange and not buildingCard.IsRuin then
            table.insert(tbbuildStateDesc, {desc = OutsideCanalRangeDesc, type = g_BuildingDefine.HintImgPathType.NoInCanalRange});
        end
    end
    if building.m_bFertilizer then
        local FertilizerLowDesc = g_LRPDescManager:GetRPTextFormated("FERTILIZER_TIPS_FEW_SUPPLIES");
        data.FertilizerLowDesc = FertilizerLowDesc;
        if buildingCard.FertilizerInfo.nFertilizerLevel < 1 and not buildingCard.IsRuin then
            table.insert(tbbuildStateDesc, {desc = FertilizerLowDesc});
        end
    end
    --- 产业竞争描述
    if building:IsShowCompetitionHeadEffect() then
        local level = g_BuildingWorldModule.BuildingMgr.Statistics:GetBuildingCompetitionLevel(building:GetBelongBlock(), building.G, building.D, building.P) or 0;
        local szCompetitionDesc = g_LRPDescManager:GetRPTextFormated(level > g_BuildingDefine.ShowCompetitionHeadEffectLevel and "BUILDINGTIPS_UNABLEWORK_REASON_08" or "BUILDINGTIPS_UNABLEWORK_REASON_07");
        if szCompetitionDesc ~= "" then
            table.insert(tbbuildStateDesc, {desc = szCompetitionDesc, type = g_BuildingDefine.HintImgPathType.Competition});
        end
    end
    if building:IsMourningFlag() then
        local szCompetitionDesc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_09");
        if szCompetitionDesc ~= "" then
            table.insert(tbbuildStateDesc, {desc = szCompetitionDesc});
        end
    end
    --- 优先显示 道路未连接 然后到 工作人口不足----
    --- 未联通道路提示
    local workingState = building:GetWorkingState(); 
    local nCostType = building:GetCostPopulationType();
    if wo and wo:CheckIsShowNoConnectRoadHeadPresentation() then
        local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_02");
        table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NoConnectRoad});
    else
        if  workingState == g_BuildingDefine.STOP_WORKING_STATE.WORKING then
            --- 工作人口不足提示
            if building:GetMaxPopulation() > 0 and building:GetNeedPopulation() > 0 then 
                local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_01");
                if nCostType == block_define.SOURCE.CRAFTSMAN then
                    table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NoCraftsManStop});
                elseif nCostType == block_define.SOURCE.SCHOOLER then
                    table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NoSchoolerStop});
                else
                    table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NoWorkingPeople});
                end
            end
        elseif workingState == g_BuildingDefine.STOP_WORKING_STATE.NO_POPULATION then
           ---没有工作人口
            local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_04");
            if nCostType == block_define.SOURCE.CRAFTSMAN then
                table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NeedCraftsManStop});
            elseif nCostType == block_define.SOURCE.SCHOOLER then
                table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NeedSchoolerStop});
            else
                table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NoPopulationStop});
            end
        elseif workingState == g_BuildingDefine.STOP_WORKING_STATE.NO_RESOURCE then
            local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_05");
            table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NoResourceStop});
        elseif workingState == g_BuildingDefine.STOP_WORKING_STATE.NEED_POPULATION then
            local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_06");
            if nCostType == block_define.SOURCE.CRAFTSMAN then
                table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NeedCraftsManStop});
            elseif nCostType == block_define.SOURCE.SCHOOLER then
                table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NeedSchoolerStop});
            else
                table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NeedPopulationStop});
            end
        end
    end
    --- 民居未满负荷工作提示
    if building:IsShowFreePeopleHeadEffect() then
        local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_03",{
            Num = building:GetFreePeopleNum();
        });
        table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.HouseHasFreePeople});
    end
    -- 精华萃取器 出口未连接
    if building.bQuintessence then
        local nNotConnectNum = building:GetNotConnectRoadAnchorNum();
        if nNotConnectNum > 0 then
            local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_10",{
                Num = nNotConnectNum;
            });
            table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.QuintessenceNotConnect});
        else
            if not building:CanGenerateQuintessence() then
                local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGTIPS_UNABLEWORK_REASON_11");
                table.insert(tbbuildStateDesc, {desc = desc});
            end
        end
    end
    if wo and wo.bPump and g_EnvironmentMgr:GetFrozenArea() > 0.5 then
        local desc = g_LRPDescManager:GetRPTextFormated("CANAL_FROZEN_TIPS");
        table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.PumpInWinter});
    end
    if wo.isIrrigete then
        if not wo:GetConnectChannel() then
            local desc = g_LRPDescManager:GetRPTextFormated("BUILDINGWITHOUT_FULLWATER");
            table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.NoInCanalRange});
        end
        if wo:GetIsFreeze() then
            local desc = g_LRPDescManager:GetRPTextFormated("BUILDING_FROZEN");
            table.insert(tbbuildStateDesc, {desc = desc, type = g_BuildingDefine.HintImgPathType.PumpInWinter});
        end
    end
    return tbbuildStateDesc;
end
function LCommonProvider:S2UI_OnBuildHovered(building, bUpgrade)
    if g_timer:IsAlive(self.hoverInfoTimerId) then
        g_timer:Close(self.hoverInfoTimerId);
    end
    local mode = g_World:GetMode();
    if mode == world_define.Mode.UPGRADE and g_World:IsLongPressShift() then
        g_BuildingWorldModule:BatchOpreationCost(building);
    else
        g_BuildingWorldModule:UpdateBuildCost(building);
    end
    self.hoverInfoTimerId = g_timer:Register(g_timer.TT_DEFAULT, 1, function()
        local wo = building and building:GetWorldObject();
        local hoverWouuid = g_World:GetMouseHoverWOUUID() or -1;
        local wouuid = wo and wo:GetWOUUID() or -2;
        local nBlock = building:GetBelongBlock();
        local sBlock = g_blockMgr:GetBlock(nBlock);
        if hoverWouuid == wouuid then
            local data = self:_GetBuildingCardInfo(building, bUpgrade);
            self:_ModifySpecialEffectBuildingTips(data, building);
            -- 判断是否是民居
            if self:CheckIsProductPopulationBuilding(building) then
                -- 民居升级资源百分比
                data.UpgredeSourcePercent = building:GetUpgradeSourcePercent();
                data.WorkingPopulation = building:GetWorkingPopulation();
                data.isProductPopulation = true;
                -- 民居降级相关数据
                data.DowngradeInfo = building:GetDowngradeInfo();
            end
            if self:CheckIsChangeHouseBuilding(building) then
                if building.__cname == "LBuildingHouse" then
                    data.nSelectHouseType = g_BuildingDefine.UNIVERISTY_TYPE.NORMAL;
                elseif building.__cname == "LBuildingCarftsMan" then
                    data.nSelectHouseType = g_BuildingDefine.UNIVERISTY_TYPE.CRAFTSMAN;
                elseif building.__cname == "LBuildingScholar" then
                    data.nSelectHouseType = g_BuildingDefine.UNIVERISTY_TYPE.SCHOOLER;
                end
                data.isChangeHouse = g_LPopulationManager:CheckIsUnlockChangeHouse();
            end
            if building:IsOfficeBuilding() then
                data.UpgradeInfo = building:DumpUpgradeInfo();
            end
            
            local layerId = building:GetGeologicMapLayerID();
            local bShowLayerInfo = true;
            bShowLayerInfo = bShowLayerInfo and layerId ~= g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE.DEFAULT;
            bShowLayerInfo = bShowLayerInfo and layerId ~= g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE.GRIDMASK;
            bShowLayerInfo = bShowLayerInfo and layerId ~= g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE.DEEPMINE;
            bShowLayerInfo = bShowLayerInfo and layerId ~= g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE.DEEPWATER;
            bShowLayerInfo = bShowLayerInfo and not building.m_bExploration;
            if bShowLayerInfo then
                data.layerId = layerId;
                local suffix = g_LGeologicMap.LGeologicMapDefine.E_LAYER_TYPE_Suffix[layerId];
                local desc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_TITLE_"..suffix)
                local capacity = wo:GetGeologicMapCapacityLevel(true);
                data.layerDesc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_DESC", {
                    Layer = desc,
                    Level = capacity,
                })
                ---林地加成显示
                local bSawmill = g_BuildingWorldModule:CheckMouseObjectIsSawillBuilding(wo);
                if bSawmill then
                    g_BuildingWorldModule:ForceGetCacheObjectRangeBuildingObjects(wo);
                    local nSawmillEffectValue = g_BuildingWorldModule:FrameGetIsProductAddOrDown();
                    local strSawmillEffectDesc = "";
                    if nSawmillEffectValue == 1 then
                        strSawmillEffectDesc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_FOREST_EX_01");
                    elseif nSawmillEffectValue == 2 then
                        strSawmillEffectDesc = g_LRPDescManager:GetRPTextFormated("GEOLOGY_BUILDTIPS_FOREST_EX_02");
                    end
                    data.layerDesc = string.format("%s%s", data.layerDesc, strSawmillEffectDesc);
                    g_BuildingWorldModule:ClearCacheMouseObjectRangeBuilding();
                end
                data.icon = wo:GetGeologicMapLayerIcon();
            end
            data.buildStateDesc = self:_GetBuildStateDesc(building, bUpgrade)
            local nTipsType = building:GetBuildingTipsType();
              ---产出型建筑并且
            if nTipsType == g_BuildingDefine.BuildTipsType.Product then
                local bForest = g_LBuildingFuncManager:IsCheckFuncBuilding(BuildingFuncDefine.FUNC_TYPE.FOREST, building.G, building.D, building.P);
                data.bForest = bForest;
            end
            --天工坊建筑
            if nTipsType == g_BuildingDefine.BuildTipsType.Research then
                data.tbRdData = g_LWorkShopManager:DumpWorkShopBuildingInfo(building);
            end
            if sBlock:IsPeaceBlock() then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnNeutralBuildHovered, data);
            elseif nTipsType == g_BuildingDefine.BuildTipsType.House then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildHouseHovered, data);
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Product then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildProductHovered, data);
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Religion then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingReligionHovered, data);
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Barn then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingBarnHovered, data);
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Ship then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingShipHovered,data);  
            elseif nTipsType == g_BuildingDefine.BuildTipsType.OverWinter then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingOverWinterHovered,data); 
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Pick then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildPickHovered,data); 
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Port then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildPortHovered,data); 
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Manure then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildManureHovered,data); 
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Research then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildResearchHovered,data);
            elseif nTipsType == g_BuildingDefine.BuildTipsType.Jisi then
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildJisiHovered,data);
            else
                g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildHovered, data);
            end
            if building:NeedUpdateTipsInfo() then
                g_LHBUIProvider:EmitTo("LCommonProvider", g_LHBUIEvents.S2UI_OnUpdateTipsInfoPerDay, building);
            end
        end
    end)
end
function LCommonProvider:S2UI_ShowBuildingModelSkin(data)
    if not data.sourceTitle or data.sourceTitle == "" then
        local title = g_LRPDescManager:GetRPTextFormated("BUILD_MODE_SOURCETITLE1");
        data.sourceTitle = title;
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_ShowBuildingModelSkin,data);
end
function LCommonProvider:S2UI_OnStaticHovered(nType)
    if g_timer:IsAlive(self.hoverInfoTimerId) then
        g_timer:Close(self.hoverInfoTimerId);
    end
    self.hoverInfoTimerId = g_timer:Register(g_timer.TT_DEFAULT, 1, function()
    
        local _, x, y = g_WindowManager:GetClientMousePos();
        local data = {
            left = x,
            top = y,
        };
        if nType == world_define.STATIC_TYPE.BRIDGE then
            data.content = g_LRPDescManager:GetRPTextFormated("STATIC_TIPS_BRIDGE");
            g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnStaticHovered, data);
        end
    end)
end
function LCommonProvider:S2UI_OnStaticUnHovered()
    if self.hoverInfoTimerId and g_timer:IsAlive(self.hoverInfoTimerId) then
        g_timer:Close(self.hoverInfoTimerId);
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnStaticUnHovered);
end
function LCommonProvider:UI2S_PreviewCardBuildTime(GDPL)
    local G,D,P,L = GDPL.G,GDPL.D,GDPL.P,GDPL.L;
    self:S2UI_PreviewCardBuildTime({G,D,P,L});
end
function LCommonProvider:S2UI_PreviewCardBuildTime(cardGDPL)
    local buildingCard = g_LBuildingCardManager:GetBuildingCardByGDPL(table.unpack_4(cardGDPL));
    local previewTime = buildingCard:PreviewCardBuildTime();
    local desc = buildingCard:GetDesc();
    
    if previewTime then
        local buildTimeDesc = g_LRPDescManager:GetRPTextFormated("CENSUS_PROGRESS_TOTAL",{totalBuildTime = math.ceil((previewTime or 0) / LTimeDefine.SECONDS_PER_DAY);});
        desc = desc .. "<br>" .. buildTimeDesc;
    end
    local data = {
        desc = desc,
        cardGDPL = cardGDPL,
    }
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_PreviewCardBuildTime, data);
end
function LCommonProvider:S2UI_OnBuildUnHovered(bSelect)
    bSelect = not not bSelect;
    if self.hoverInfoTimerId and g_timer:IsAlive(self.hoverInfoTimerId) then
        g_timer:Close(self.hoverInfoTimerId);
    end
    if not bSelect then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnNeutralBuildUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingBarnUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingShipUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingOverWinterUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildPickUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildPortUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildManureUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildHouseUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildProductUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildingReligionUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildResearchUnHovered);
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnBuildJisiUnHovered);
    end
    ---升级、拆除模式的时候  需要悬浮建筑显示建造费用 所以移出建筑的时候 需要隐藏掉hotelSkin.fla
    local mode = g_World:GetMode();
    if  mode == world_define.Mode.UPGRADE or mode == world_define.Mode.DESTROY  then
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_HideBuildingModelSkin);
    end
end
-- 主动取消建筑的悬浮态
function LCommonProvider:UI2S_UnhoverWorldObject()
    if g_timer:IsAlive(self.hoverInfoTimerId) then
        g_timer:Close(self.hoverInfoTimerId);
    end
    g_World:MouseUnHoverWorldObject();
end
---
--- UI 触发UI音效
---
--- @param data table
---
function LCommonProvider:UI2S_OnSoundsPostEvent(data)
    local triggerName, status = data.TriggerName, not not data.Status;
    local sounds = g_LUISoundsManager:GetSounds(triggerName);
    if sounds then
        sounds:PostEvent(status, data.Options);
    end
end
function LCommonProvider:UI2S_OnSoundsPostEventByBnkEvent(data)
    local szBnkName = data.BnkName;
    local szEventName = data.EventName;
    local status = not not data.Status;
    g_LUISoundsManager:PostSoundsByBnkEvent(szBnkName,szEventName,status)
end
function LCommonProvider:UI2S_OnSoundsPostEmotionEvent(data)
    local emotionId = data.EmotionId;
    local npcResId = data.NpcResId;
    local status = not not data.Status;
    
    local szBnkName, szEventName = g_LNPCManager:GetNpcEmotionAudio(npcResId,emotionId);
    if szBnkName and szEventName then
        g_LUISoundsManager:PostSoundsByBnkEvent(szBnkName,szEventName,status);
    end
end
function LCommonProvider:UI2S_CloseSeasounSounds(bEnable)
    if bEnable then
        g_GameWorld.GameWorldAudio:StopSeasonStateAudio();
    else
        g_GameWorld.GameWorldAudio:StartSeasonStateAudio();
    end
end
function LCommonProvider:UI2S_CloseSceneAudio(bEnable)
    g_Game:TempCloseSceneAudio(not bEnable);
end
function LCommonProvider:S2UI_UpdateCursor(szMode)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateCursor, {
        mode = szMode,
    });
end
--- 暂时废弃
function LCommonProvider:S2UI_OnDay(day)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnDay, day);
end
function LCommonProvider:S2UI_OnMonth(month)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnMonth, month);
end
function LCommonProvider:S2UI_OnYear(year)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnYear, year);
end
function LCommonProvider:S2UI_OnSeason(season)
    self:S2UI_OnChangeSkinByEvent("season",season);
    g_GameWorld:SetIsUpdateBuildCard(true);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnSeason, season);
end
function LCommonProvider:S2UI_UpdateTalkContents(contents)
    -- contents = g_Talk:GetCurContents()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateTalkContents, contents);
end
function LCommonProvider:UI2S_GetInitErrors()
    self:S2UI_OnInitErrors();
end
function LCommonProvider:S2UI_OnInitErrors()
    local rpdescs = g_LRPDescManager:GetAllByType(g_LRPDescManager.types.ERR);
    local descTexts = {};
    for key, rpdesc in pairs(rpdescs) do
        descTexts[key] = rpdesc:Format();
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnInitErrors, descTexts);
end
function LCommonProvider:S2UI_OnChangeSkinByEvent(eventType,eventKey)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnChangeSkinByEvent, {
        eventType = eventType,
        eventKey  = eventKey,
    });
end
function LCommonProvider:S2UI_OnSwitchGUI(bShow)
    g_LInputController.bKeyBoard = true;
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnSwitchGUI, bShow);
end
function LCommonProvider:S2UI_RefugeeShowUI(bShow)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_RefugeeShowUI, bShow);
end
function LCommonProvider:S2UI_OnHiddenBackgroundUI()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnHiddenBackgroundUI);
end
function LCommonProvider:S2UI_OnGameReady()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnGameReady);
end
function LCommonProvider:UI2S_UILoadingFinished()
    g_EventDispatcherManager:DispatchEvent(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.LOADING_FINISHED);
end
function LCommonProvider:UI2S_CloseOperateTips()
    local bNewGame = g_Game:IsNewLevel() == true;
    local bSkipGuide = g_LGuideManager:CheckSkipGuide();
    if bNewGame and bSkipGuide then
        g_Game:AutoSaveArchive();
        -- 更新城市品阶tips内容
        g_LHBUIProvider:EmitTo("LBlockProvider", g_LHBUIEvents.S2UI_UpdateBoomConditionState);
        if g_GameWorld:GetPlayMod() ~= g_Game.LGameDefine.PLAY_MOD.SANDBOX then
            g_LStoryManager:DoStory(1017);
        end
    else
        -- 关闭tips后通知剧情
        g_EventDispatcherManager:DispatchEvent(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.LOAD_TIPS_CLOSED);
    end
end
---
--- @param options table<string, string>
--- @field options.name string case名称
--- @field options.status boolean 状态
---
function LCommonProvider:S2UI_OnSwitchCase(options)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnSwitchCase, {
        caseName = options.name,
        status = options.status,
    });
end
function LCommonProvider:UI2S_CancelBuildMode(data)
    local wo = g_World:GetMouseWorldObject();
    if wo then
        self.nCurrentOperatingWorldObjectUUID = wo:GetWOUUID();
    end
    g_World:SaveBuildModeInfo(wo, data);
    g_World:CancelEmplace(g_World.m_emplaceData);
    g_World:CancelMove();
    g_World:CancelDragging();
    g_World:SwitchMode(world_define.Mode.NORMAL);
end
function LCommonProvider:UI2S_RestoreBuildingMoveMode(bRestore)
    if not not  bRestore then
        if g_World:GetWorldObject(self.nCurrentOperatingWorldObjectUUID) then
            g_World:SwitchMode(world_define.Mode.MOVE);
            g_World:TryToMoveWorldObject(self.nCurrentOperatingWorldObjectUUID);
        end
    end
    self.nCurrentOperatingWorldObjectUUID = nil;
end
function LCommonProvider:UI2S_SwitchMode(mode)
    local cursorMode = world_define.ModeToCursor[mode];
    g_Cursor:SwitchMode(cursorMode);
end
function LCommonProvider:S2UI_SwitchMode(mode)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_SwitchMode,mode);
end
function LCommonProvider:UI2S_OnBuildUnHovered()
    self:S2UI_OnBuildUnHovered();
end
function LCommonProvider:S2UI_OnUpdateBuildingCardAni(buildingCard)
    local dumpCard = {};
    if buildingCard then
        dumpCard.Name = buildingCard:Get(buildingCard.ATTRS.Name);
        dumpCard.Icon = util.a2u8(buildingCard:Get(buildingCard.ATTRS.Icon));
        dumpCard.Quality = buildingCard:Get(buildingCard.ATTRS.Quality);
    end
    
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateBuildingCardAni,dumpCard);
end
--- 触发快捷键
function LCommonProvider:S2UI_OnKeyboard(data)
    data.bGameReady = g_GameWorld:IsGameReady();
    -- if (data.func == "checkOutBlock" or data.func == "mapOpen") and g_PublicityManager and g_PublicityManager:IsPlayingRoadSpeech() then
    --     return;
    -- end
    if g_PublicityManager and g_PublicityManager:IsPlayingRoadSpeech() then
        if data.func == "checkOutBlock" or data.func == "mapOpen" or data.func == "Home" then
            return;
        end
    end
    if g_LStoryManager and g_LStoryManager:CheckIsDisableEsc() then
        if data.func == "esc" then
            return;
        end
    end
    -- 景观模式和移轴模式屏蔽除了ESC外所有的快捷键
    if g_GameWorld:IsInSceneryStatus() or g_GameWorld:IsInTiltShiftStatus() then
        if data.func ~= "esc" then
            return;
        end
    end
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnKeyboard,data);
    if g_GameWorld:IsGameReady() then
        if data.func == "esc" then
            g_World:UnselectWorldObject();
        end
    end
end
function LCommonProvider:S2UI_OnClickBlank()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnClickBlank);
end
function LCommonProvider:S2UI_OnMouseWheelToMaxRadius()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnMouseWheelToMaxRadius);
end
function LCommonProvider:UI2S_OnOpenOrCloseWindow(param)
    local  name = param.name;
    local state = param.state;
    g_EventDispatcherManager:DispatchEvent(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.ON_UI_WINDOW_CHANGE, param );
end
-- 需要单独写一个协议(因为开关太频繁, 需要等ui生命周期全部走完才能继续操作, onwindowChange是UI生命周期过程就抛回调了)
function LCommonProvider:UI2S_OnOpenOrCloseFullScreenMask(param)
    local state = param.state;
    g_EventDispatcherManager:DispatchEvent(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.ON_UI_FULLSCREENMASK_CHANGE, param );
end
function LCommonProvider:UI2S_CheckUIModelState(param)
    local  name = param.name;
    local state = param.state;
    g_EventDispatcherManager:DispatchEvent(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.ON_UI_WINDOW_CHECK, param );
end
function LCommonProvider:UI2S_CheckUIWindowExist(state)
    g_EventDispatcherManager:DispatchEvent(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.ON_UI_WINDOW_EXIST, state);
end
function LCommonProvider:UI2S_OnCloseMapByMouseWheel()
    local bOK, nWndW, nWndH = g_WindowManager:GetWindowSize();
    local nWndWHalf, nWndHHalf = nWndW * 0.5, nWndH * 0.5;
    local _,cx,cy,cz = g_CameraController:GetPosition();
    local bOK,x,y,z,_ = g_CameraController:Screen2WorldPos(nWndWHalf, nWndHHalf, self.m_uIgnoreMask, self.m_nRayCastDistance);
    if true == bOK then
        -- local fScale = -1 * 0.017 * 2;
        local nDx, nDy, nDz = (x - cx), (y - cy), (z - cz);
        local v3Dir = KVec3:new_local(nDx, nDy, nDz);
        local nDistance = v3Dir:Size();
        local v3Move = KVec3:new_local(nDx, nDy, nDz);
        local nDistanceNew = self.m_nMaxRadius;
        local nMoveDistance = nDistance - nDistanceNew;
        v3Dir:Normalize();
        KVec3MulNum3(v3Dir, nMoveDistance, nMoveDistance, nMoveDistance, v3Move);
        local xp = cx + v3Move.x;
        local yp = cy + v3Move.y;
        local zp = cz + v3Move.z;
        g_CameraController:SetPosition(xp, yp, zp);
        --以下计算方式是根据(3400,50)(12000,40)(34000,35)这三个点拟合出来的幂函数
        g_CameraController:SetFovAngleY(g_CameraDefine:CalcFovAngleYByRotationRadius(nDistanceNew));
    end
end
function LCommonProvider:UI2S_SetHBUIInputHandled(status)
    if not (
        g_GameWorld:IsInTiltShiftStatus() or
        g_GameWorld:IsInSceneryStatus() or
        g_GameWorld:IsInEditStatus()
    ) then
        g_World:SetTickable((not status) and g_GameWorld:IsGameReady());
    end
end
function LCommonProvider:UI2S_SetCameraAutoMove(bEnable)
    local lCameraMod = g_CameraController:GetCameraModCache(camera_define.Mod.GOD);
    if lCameraMod then
        lCameraMod:SetAutoMoveStatus(not not bEnable);
    end
end
function LCommonProvider:UI2S_EnterPreparationPeriod()
    -- 测试：只可挑战3关
    if g_GameWorld.m_bInTest and g_blockMgr:GetIsTestSussess() then
        -- local data = {
        --     content = g_LRPDescManager:GetRPDesc("TXT_TEST_END").vartext,
        --     title = g_LRPDescManager:GetRPDesc("TXT_TEST_END_TITLE").vartext,
        -- };
        -- g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdatePrepareTip, data);
        return ;
    end
    if g_GameWorld.PreparationTime > 0 then
        self:S2UI_EnterPreparationPeriod();
    end
end
-- 整备期开始
function LCommonProvider:S2UI_EnterPreparationPeriod()
    local function endingTalk()
        -- 结束对话回调
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_ShowPrepareStartTeaching);
    end
    g_GameWorld:SetIsPreparationPeriod(true);
    -- 暂时屏蔽整备期对话
    -- if g_GameWorld.bIsFirstPreparation then
    --     g_GameWorld.bIsFirstPreparation = false;
    --     local converId = g_LTalkDefine.DIALOGUE_PREPARATION_FIRST_START;
    --     local tbTalkList = g_LConverseManager:AnalysisConverseData(converId);
    --     g_LTalkManager:DoTriggerConverse(tbTalkList, endingTalk);
    -- end
    -- 整备期技能释放
    g_GameWorld:CastPreparationSkill();
    local content =  g_LRPDescManager:GetRPTextFormated("TXT_PREPARATION_CONTENT_RESOURCE", {time = g_GameWorld.PreparationTime});
    local preparation = {
        bPreparation = g_GameWorld.bPreparationPeriod,
        periodTime   = g_GameWorld.PreparationTime,
        content      = content,
    }
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_EnterPreparationPeriod, preparation);
end
-- 整备期期间
function LCommonProvider:S2UI_OnUpdatePreparationTime(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdatePreparationTime, data);
end
-- 整备期结束
function LCommonProvider:UI2S_EndPreparationPeriod()
    -- g_GameWorld:ClearPrepareTime();
end
function LCommonProvider:UI2S_OpenBigMapDuringPreparation()
    local periodTime = g_GameWorld.PreparationTime;
    local mapContent, systemContent, talkContent = "", "", "";
    mapContent = g_LRPDescManager:GetRPTextFormated("TXT_PREPARATION_CONTENT_BIGMAP", {time = periodTime});
    systemContent = g_LRPDescManager:GetRPTextFormated("TXT_PREPARATION_CONTENT_SYSTEMTIP", {time = periodTime});
    
    local tbContentParam = {[1] = {time = periodTime}};
    local ConverseId = g_LTalkDefine.OPEN_BIGMAP_IN_PREPARATION;
    local tbTalkList = g_LConverseManager:AnalysisConverseData(ConverseId, nil, tbContentParam);
    g_LTalkManager:DoTriggerConverse(tbTalkList);
    self:S2UI_OpenBigMapDuringPreparation({mapContent = mapContent, systemContent = systemContent});
end
function LCommonProvider:S2UI_ResetPreparationPeriod()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_ResetPreparationPeriod);
end
function LCommonProvider:UI2S_SetEnvironmentMoment(Type)
    self:StartBlackCurtain(1);
    if Type == environment_define.MomentType.EVENING and g_FestivalManager:IsInFestival(g_TimeDefine.FESTIVAL_KEY.SPRING_FESTIVAL) then
        g_FestivalManager:PlayFireworks();
        g_FestivalManager:PlayDragon();
    end
    -- local block = g_blockMgr:GetSelectedBlock();
    local block = g_blockMgr:GetCampBlock();
    block.m_nMomentType = Type;
    block.m_bOnclickMomentBtn = true;
end
function LCommonProvider:S2UI_UpdateMoment(nType)
    local CurMoment =nType or g_EnvironmentMgr:GetCurMoment();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateMoment,CurMoment);
end
function LCommonProvider:UI2S_LoadingUIMounted()
    g_Game:StartLoadingAudio();
end
function LCommonProvider:UI2S_HoverProjectResource(nType)
    -- body
    local desc = g_LRPDescManager:GetRPTextFormated(g_BuildingDefine.ResourceDesc[nType]);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateDesc,desc);
end
function LCommonProvider:S2UI_OpenBigMapDuringPreparation(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OpenBigMapDuringPreparation, data);
end
--- 对应JS的配置文件在 \coui\configs\Fragments.js
--- 图片视频资源配置在 \coui\assets\shared\images\Assets.js
function LCommonProvider:UI2S_GetOperationInfo()
    local data = g_LTutorialManager:GetTutorialOperationInfo();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateOperationInfo, data);
end
function LCommonProvider:S2UI_OnUpdateStartLocalization()
    local localRpDescMgr = g_LRPDescManager;
    local tl = {
        ["fix_month_1"] = "FIX_JAN",
        ["fix_month_2"] = "FIX_FEB",
        ["fix_month_3"] = "FIX_MAR",
        ["fix_month_4"] = "FIX_APR",
        ["fix_month_5"] = "FIX_MAY",
        ["fix_month_6"] = "FIX_JUN",
        ["fix_month_7"] = "FIX_JUL",
        ["fix_month_8"] = "FIX_AUG",
        ["fix_month_9"] = "FIX_SEP",
        ["fix_month_10"] = "FIX_OCT",
        ["fix_month_11"] = "FIX_NOV",
        ["fix_month_12"] = "FIX_DEC",
        ["fix_season_1"] = "FIX_SPRING",
        ["fix_season_2"] = "FIX_SUMMER",
        ["fix_season_3"] = "FIX_AUTUMN",
        ["fix_season_4"] = "FIX_WINTER",
    };
    for key,value in pairs(tl) do
        tl[key] = localRpDescMgr:GetRPTextFormated(value);
    end
    local data = {
        {
            model="Save",
            localization={
                ["fix_month_1"] = tl["fix_month_1"],
                ["fix_month_2"] = tl["fix_month_2"],
                ["fix_month_3"] = tl["fix_month_3"],
                ["fix_month_4"] = tl["fix_month_4"],
                ["fix_month_5"] = tl["fix_month_5"],
                ["fix_month_6"] = tl["fix_month_6"],
                ["fix_month_7"] = tl["fix_month_7"],
                ["fix_month_8"] = tl["fix_month_8"],
                ["fix_month_9"] = tl["fix_month_9"],
                ["fix_month_10"] = tl["fix_month_10"],
                ["fix_month_11"] = tl["fix_month_11"],
                ["fix_month_12"] = tl["fix_month_12"],
            }
        },
        {
            model = "Loading",
            localization={
                ["TipTitle1"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SETTING_TITLE"),
                ["TipContent1"] = localRpDescMgr:GetRPTextFormated("CONFIRM_LOADING_CG_CONTENT"),
                ["BtnOk1"] = localRpDescMgr:GetRPTextFormated("CONFIRM_CONTROL_CONFLICT_YES"),
                ["BtnCancel1"] = localRpDescMgr:GetRPTextFormated("ORDER_BTN_DELAY_CANCEL"),
                ["TipTitle2"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SETTING_TITLE"),
                ["TipContent2"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SKIP_GUIDE_CONTENT"),
                ["BlockName"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_1"),
                ["SandboxBlockName"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_SANDBOX_1"),
                ["BtnOk2"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SKIP_GUIDE_OK"),
                ["BtnCancel2"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SKIP_GUIDE_CANCEL"),  
            }
        },
        {
            model = "ModeSelect",
            localization = {
                ["TitleModeSelect"] = localRpDescMgr:GetRPTextFormated("TITLE_MODE_SELECT"),
                ["TitleSandboxMapSelect"] = localRpDescMgr:GetRPTextFormated("TIELE_SANDBOX_MAP_SELECT"),
                ["ChallengeModeUnlockedDesc"] = localRpDescMgr:GetRPTextFormated("GAME_MODE_UNLOCK_TEXT"),
            }
        }
    };
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateStartLocalization, data);
end
function LCommonProvider:S2UI_OnUpdateLocalization()
    local tl = {
        ["fix_security"] = "ASSEMBLY_SECURITY",
        ["fix_adviser"] = "FIX_ADVISER",
        ["fix_industry"] = "ASSEMBLY_INDUSTRY",
        ["fix_payloan"] = "FIX_PAY_LOAN",
        ["fix_loan"] = "FIX_LOAN",
        ["fix_month_1"] = "FIX_JAN",
        ["fix_month_2"] = "FIX_FEB",
        ["fix_month_3"] = "FIX_MAR",
        ["fix_month_4"] = "FIX_APR",
        ["fix_month_5"] = "FIX_MAY",
        ["fix_month_6"] = "FIX_JUN",
        ["fix_month_7"] = "FIX_JUL",
        ["fix_month_8"] = "FIX_AUG",
        ["fix_month_9"] = "FIX_SEP",
        ["fix_month_10"] = "FIX_OCT",
        ["fix_month_11"] = "FIX_NOV",
        ["fix_month_12"] = "FIX_DEC",
        ["fix_season_1"] = "FIX_SPRING",
        ["fix_season_2"] = "FIX_SUMMER",
        ["fix_season_3"] = "FIX_AUTUMN",
        ["fix_season_4"] = "FIX_WINTER",
        ["fix_age"] = "FIX_AGE",
        ["fix_research"] = "FIX_RESOURCHING",
        ["fix_di"] = "FIX_DI",
        ["fix_wave"] = "FIX_WAVE",
        ["fix_strategy"] = "FIX_STRATEGY",
        ["fix_mission_1"] = "FIX_ZENGWU",
        ["fix_mission_2"] = "FIX_YANJUAN",
        ["fix_mission_3"] = "FIX_XIAOMI",
        ["fix_mission_4"] = "FIX_DIMI",
        ["fix_mission_5"] = "FIX_SANMAN",
        ["fix_mission_6"] = "FIX_YINGFU",
        ["fix_mission_7"] = "FIX_YIBAN",
        ["fix_mission_8"] = "FIX_RENZHEN",
        ["fix_mission_9"] = "FIX_JINGYE",
        ["fix_mission_10"] = "FIX_JIJI",
        ["fix_mission_11"] = "FIX_GAOZHANG",
        ["fix_mission_12"] = "FIX_REZHONG",
        ["fix_mission_13"] = "FIX_XINYANG",
    }
    local localRpDescMgr = g_LRPDescManager;
    for key,value in pairs(tl) do
        tl[key] = localRpDescMgr:GetRPTextFormated(value);
    end
    local data = {
        {
            model="TalentMain",
            localization={
                ["fix_security"] = tl["fix_security"],
                ["fix_adviser"] = tl["fix_adviser"],
                ["fix_industry"] = tl["fix_industry"],
            }
        },
        {
            model="Loan",
            localization={
                ["fix_payloan"] = tl["fix_payloan"],
                ["fix_loan"] = tl["fix_loan"],
            }
        },
        {
            model="Project",
            localization={
                ["fix_month_1"] = tl["fix_month_1"],
                ["fix_month_2"] = tl["fix_month_2"],
                ["fix_month_3"] = tl["fix_month_3"],
                ["fix_month_4"] = tl["fix_month_4"],
                ["fix_month_5"] = tl["fix_month_5"],
                ["fix_month_6"] = tl["fix_month_6"],
                ["fix_month_7"] = tl["fix_month_7"],
                ["fix_month_8"] = tl["fix_month_8"],
                ["fix_month_9"] = tl["fix_month_9"],
                ["fix_month_10"] = tl["fix_month_10"],
                ["fix_month_11"] = tl["fix_month_11"],
                ["fix_month_12"] = tl["fix_month_12"],
                ["fix_season_1"] = tl["fix_season_1"],
                ["fix_season_2"] = tl["fix_season_2"],
                ["fix_season_3"] = tl["fix_season_3"],
                ["fix_season_4"] = tl["fix_season_4"],
            }
        },
        {
            model="GamePlayer",
            localization={
                ["fix_month_1"] = tl["fix_month_1"],
                ["fix_month_2"] = tl["fix_month_2"],
                ["fix_month_3"] = tl["fix_month_3"],
                ["fix_month_4"] = tl["fix_month_4"],
                ["fix_month_5"] = tl["fix_month_5"],
                ["fix_month_6"] = tl["fix_month_6"],
                ["fix_month_7"] = tl["fix_month_7"],
                ["fix_month_8"] = tl["fix_month_8"],
                ["fix_month_9"] = tl["fix_month_9"],
                ["fix_month_10"] = tl["fix_month_10"],
                ["fix_month_11"] = tl["fix_month_11"],
                ["fix_month_12"] = tl["fix_month_12"],
            }
        },
        {
            model="Propaganda",
            localization={
                ["fix_month_1"] = tl["fix_month_1"],
                ["fix_month_2"] = tl["fix_month_2"],
                ["fix_month_3"] = tl["fix_month_3"],
                ["fix_month_4"] = tl["fix_month_4"],
                ["fix_month_5"] = tl["fix_month_5"],
                ["fix_month_6"] = tl["fix_month_6"],
                ["fix_month_7"] = tl["fix_month_7"],
                ["fix_month_8"] = tl["fix_month_8"],
                ["fix_month_9"] = tl["fix_month_9"],
                ["fix_month_10"] = tl["fix_month_10"],
                ["fix_month_11"] = tl["fix_month_11"],
                ["fix_month_12"] = tl["fix_month_12"],
            }
        },
        {
            model="Save",
            localization={
                ["fix_month_1"] = tl["fix_month_1"],
                ["fix_month_2"] = tl["fix_month_2"],
                ["fix_month_3"] = tl["fix_month_3"],
                ["fix_month_4"] = tl["fix_month_4"],
                ["fix_month_5"] = tl["fix_month_5"],
                ["fix_month_6"] = tl["fix_month_6"],
                ["fix_month_7"] = tl["fix_month_7"],
                ["fix_month_8"] = tl["fix_month_8"],
                ["fix_month_9"] = tl["fix_month_9"],
                ["fix_month_10"] = tl["fix_month_10"],
                ["fix_month_11"] = tl["fix_month_11"],
                ["fix_month_12"] = tl["fix_month_12"],
            }
        },
        {
            model="StaffInfoTips",
            localization={
                ["fix_age"] = tl["fix_age"],
                ["mission_tip"] = localRpDescMgr:GetRPTextFormated("ADVISOR_MISSION_TIPS"),
                ["Level"] = localRpDescMgr:GetRPTextFormated("TEXT_ADVISER_LEVEL"),
            }
        },
        {
            model="JudgeInfoTipsH",
            localization={
                ["fix_age"] = tl["fix_age"],
            }
        },
        {
            model="Recommend",
            localization={
                ["fix_age"] = tl["fix_age"],
            }
        },
        {
            model="Research",
            localization={
                ["fix_research"] = tl["fix_research"],
            }
        },
        {
            model="BigMarketState",
            localization={
                ["fix_di"] = tl["fix_di"],
                ["fix_wave"] = tl["fix_wave"],
            }
        },
        {
            model="Business",
            localization={
                ["fix_strategy"] = tl["fix_strategy"],
            }
        },
        {
            model="MissionTips",
            localization={
                ["fix_mission_1"] = tl["fix_mission_1"],
                ["fix_mission_2"] = tl["fix_mission_2"],
                ["fix_mission_3"] = tl["fix_mission_3"],
                ["fix_mission_4"] = tl["fix_mission_4"],
                ["fix_mission_5"] = tl["fix_mission_5"],
                ["fix_mission_6"] = tl["fix_mission_6"],
                ["fix_mission_7"] = tl["fix_mission_7"],
                ["fix_mission_8"] = tl["fix_mission_8"],
                ["fix_mission_9"] = tl["fix_mission_9"],
                ["fix_mission_10"] = tl["fix_mission_10"],
                ["fix_mission_11"] = tl["fix_mission_11"],
                ["fix_mission_12"] = tl["fix_mission_12"],
                ["fix_mission_13"] = tl["fix_mission_13"],
            }
        },
        {
            model="MissionHome",
            localization={
                ["GoalTitle"] = localRpDescMgr:GetRPTextFormated("MISSION_HOME_TITLE"),
                ["GoalLevel_0"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_0"),
                ["GoalLevel_1"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_1"),
                ["GoalLevel_2"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_2"),
                ["GoalLevel_3"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_3"),
                ["GoalLevel_4"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_4"),
                ["GoalLevel_5"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_5"),
                ["GoalLevel_6"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_6"),
                ["GoalLevel_7"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_7"),
                ["GoalLevel_8"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_8"),
                ["GoalLevel_9"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_9"),
                ["GoalLevel_10"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_10"),
                ["GoalLevel_11"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_11"),
                ["GoalLevel_12"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_12"),
                ["GoalLevel_13"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_13"),
                ["GoalLevel_14"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_14"),
                ["GoalLevel_SANDBOX_0"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_0"),
                ["GoalLevel_SANDBOX_1"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_1"),
                ["GoalLevel_SANDBOX_2"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_2"),
                ["GoalLevel_SANDBOX_3"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_3"),
                ["GoalLevel_SANDBOX_4"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_4"),
                ["GoalLevel_SANDBOX_5"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_5"),
                ["GoalLevel_SANDBOX_6"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_6"),
                ["GoalLevel_SANDBOX_7"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_7"),
                ["GoalLevel_SANDBOX_8"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_8"),
                ["GoalLevel_SANDBOX_9"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_9"),
                ["GoalLevel_SANDBOX_10"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_10"),
                ["GoalLevel_SANDBOX_11"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_11"),
                ["GoalLevel_SANDBOX_12"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_12"),
                ["GoalLevel_SANDBOX_13"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_13"),
            }
        },
        {
            model="StageConditions",
            localization={
                ["fengshui_left"] = localRpDescMgr:GetRPTextFormated("FS_FIERCE_BUILDING_CONDITION_NUM"),
                ["fengshui_unit"] = localRpDescMgr:GetRPTextFormated("FS_FIERCE_BUILDING_CONDITION_UNIT"),
            }
        },
        {
            model="Contract",
            localization={
                ["fix_month_1"] = tl["fix_month_1"],
                ["fix_month_2"] = tl["fix_month_2"],
                ["fix_month_3"] = tl["fix_month_3"],
                ["fix_month_4"] = tl["fix_month_4"],
                ["fix_month_5"] = tl["fix_month_5"],
                ["fix_month_6"] = tl["fix_month_6"],
                ["fix_month_7"] = tl["fix_month_7"],
                ["fix_month_8"] = tl["fix_month_8"],
                ["fix_month_9"] = tl["fix_month_9"],
                ["fix_month_10"] = tl["fix_month_10"],
                ["fix_month_11"] = tl["fix_month_11"],
                ["fix_month_12"] = tl["fix_month_12"],
            }
        },
        {
            model="PayTips",
            localization={
                ["Salary"] = localRpDescMgr:GetRPTextFormated("FAMOUS_ADVISER_SALARY"),
                ["PlayerPayTitle"] = localRpDescMgr:GetRPTextFormated("PLAYER_PAY_TITLE", {campBlockName = g_camp:GetName()}),
            }
        },
        {
            model="AnecdoteCollection",
            localization={
                ["Progress"] = localRpDescMgr:GetRPTextFormated("ANECDOTE_READ_PROGRESS"),
                ["Empty"] = localRpDescMgr:GetRPTextFormated("MODE_HASNOT"),
                ["BookNameTask"] = localRpDescMgr:GetRPTextFormated("MODULENAME_BOOK_TASK"),
                ["BookNameFengshui"] = localRpDescMgr:GetRPTextFormated("MODULENAME_BOOK_FENGSHUI"),
            }
        },
        {
            model="HandControl",
            localization={
                ["OperationTips1"] = localRpDescMgr:GetRPTextFormated("HANDCONTROL_TIPS1"),
                ["OperationTips2"] = localRpDescMgr:GetRPTextFormated("HANDCONTROL_TIPS2"),
                ["Yes"] = localRpDescMgr:GetRPTextFormated("TXT_XUNCHENG_EXIT_YES"),
                ["No"] = localRpDescMgr:GetRPTextFormated("TXT_XUNCHENG_EXIT_NO"),
                ["Continue"] = localRpDescMgr:GetRPTextFormated("TXT_XUNCHENG_EXIT_CONTINUE"),
                ["End"] = localRpDescMgr:GetRPTextFormated("TXT_XUNCHENG_EXIT_END"),
                ["WTitle"]   = localRpDescMgr:GetRPTextFormated("BEGINNERS_RIDING_INSTRUCTION");
            }
        },
        {
            model="Celebrity",
            localization={
                ["CelebrityTitle"] = localRpDescMgr:GetRPTextFormated("FAMOUS_TIPS_TITLE"),
            }
        },
        {
            model="CelebrityTips",
            localization={
                ["Salary"] = localRpDescMgr:GetRPTextFormated("FAMOUS_ADVISER_SALARY"),
            }
        },
        {
            model="FunctionBtn",
            localization={
                ["wonderLayFinish"] = localRpDescMgr:GetRPTextFormated("WONDER_BUILD_LAYER_FINISH"),
                ["wonderPredictFinish"] = localRpDescMgr:GetRPTextFormated("WONDER_BUILD_PREDICT_FINISH"),
                ["OpenMarketTips"] = localRpDescMgr:GetRPTextFormated("MARKET_OPEN_TIPS"),
                ["HotelApplyStar"] = localRpDescMgr:GetRPTextFormated("HOTEL_CAN_APPLY_NEXT_STAR"),
            }
        },
        {
            model="SpectacleHintTips",
            localization={
                ["PredictingText"] = localRpDescMgr:GetRPTextFormated("WONDER_PREDICTING_TEXT"),
                ["Day"] = localRpDescMgr:GetRPTextFormated("TXT_DAY_COMMON"),
                ["Layer"] = localRpDescMgr:GetRPTextFormated("WODNER_UNIT_LAYER"),
                ["BuildRoof"] = localRpDescMgr:GetRPTextFormated("WODNER_ROOF"),
            }
        },
        {
            model="ResDeliver",
            localization = g_LPostManager:GetPostLocalization()
        },
        {
            model="NBuildTips",
            localization={
                ["PeaceBlockDesc"] = localRpDescMgr:GetRPTextFormated("PEACEBLOCK_BUILDING_WARNING"),
            }
        },
        {
            model="Reinforce",
            localization = {
                ["Content"] = localRpDescMgr:GetRPTextFormated("ENEMY_REINFORCE")
            }
        },
        {
            model="Repair",
            localization = {
                ["RepairRuinNum"] = localRpDescMgr:GetRPTextFormated("REMAIN_RUINS");
                ["RepairGraveNum"] = localRpDescMgr:GetRPTextFormated("REMAIN_GRAVES");
                ["RepairCanNotAffordRuin"] = localRpDescMgr:GetRPTextFormated("REPAIR_CAN_NOT_AFFORD_RUIN");
                ["RepairCanNotAffordGrave"] = localRpDescMgr:GetRPTextFormated("REPAIR_CAN_NOT_AFFORD_GRAVE");
                ["RepairCameraBlockNoBuilding"] = localRpDescMgr:GetRPTextFormated("REPAIR_CAMERA_BLOCK_NO_BUILDING");
                ["TXT_REPAIR_CONTRACT_FAIL"] = localRpDescMgr:GetRPTextFormated("TXT_REPAIR_CONTRACT_FAIL");
            }
        },
        {
            model="StageReward",
            localization = {
                ["BattleName"] = g_FunctionManager:GetFunctionInfoById(g_functionType.BATTLE) and g_FunctionManager:GetFunctionInfoById(g_functionType.BATTLE).funcName or ""
            }
        },
        {
            model="BuildTips",
            localization = {
                ["PostConnectText"] = localRpDescMgr:GetRPTextFormated("POST_NOPRODUCE_TIPS");
            }
        },
        {
            model="Shop",
            localization = {
                ["SoldOut"] = localRpDescMgr:GetRPTextFormated("SHOP_SOLD_OUT"),
                ["Own"] = localRpDescMgr:GetRPTextFormated("SHOP_OWN"),
            }
        },
        {
            model="Scandal",
            localization = {
                ["title"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SETTING_TITLE"),
                ["OkContent"] = localRpDescMgr:GetRPTextFormated("SCANDAL_PUBLICRELATION_YES_TIPS"),
                ["CancelContent"] = localRpDescMgr:GetRPTextFormated("SCANDAL_PUBLICRELATION_NO_TIPS"),
            }
        },
        {
            model="Market",
            localization = {
                ["ReconfirmTitle"] = localRpDescMgr:GetRPTextFormated("MARKET_ALLSALE_TITLE"),
                ["ReconfirmContent"] = localRpDescMgr:GetRPTextFormated("MARKET_ALLSALE_TIPS"),
                ["MarketInfoTips"] = localRpDescMgr:GetRPTextFormated("MARKET_INFO_TIPS"),
                ["MarketValidTitle"] = localRpDescMgr:GetRPTextFormated("MARKET_VALID_TITLE"),
                ["MarketInvalidTitle"] = localRpDescMgr:GetRPTextFormated("MARKET_INVALID_TITLE"),
                ["MarketUnit"] = localRpDescMgr:GetRPTextFormated("MARKET_UNIT"),
                ["BuyTitle"] = localRpDescMgr:GetRPTextFormated("MARKET_BUY_TITLE"),
                ["SellTitle"] = localRpDescMgr:GetRPTextFormated("MARKET_SELL_TITLE"),
            }
        },
        {
            model="SurpriseTips",
            localization = {
                ["Check"] = localRpDescMgr:GetRPTextFormated("SURPRISETIPS_BTN_TEX"),
                ["RewardBtnTips"] = localRpDescMgr:GetRPTextFormated("SURPRISETIPS_HIDE_BTN_TIPS"),
            }
        },
        {
            model="Message",
            localization = {
                ["filterName00"] = localRpDescMgr:GetRPTextFormated(g_LMessageDefine.FILTERNAME_RP[0]),
                ["filterName01"] = localRpDescMgr:GetRPTextFormated(g_LMessageDefine.FILTERNAME_RP[1]),
                ["remainDay"] = localRpDescMgr:GetRPTextFormated("MESSAGE_REMAIN_DAY"),
                ["mailBoxTitle"] = localRpDescMgr:GetRPTextFormated("MAIL_BOX_TITLE"),
                ["messageBtnSalaryRequestNo"] = localRpDescMgr:GetRPTextFormated("SALARY_REQUEST_NO"),
                ["messageBtnSalaryThink"] = localRpDescMgr:GetRPTextFormated("SALARY_REQUEST_THINK"),
                ["messageBtnConfirmQuestionYes"] = localRpDescMgr:GetRPTextFormated("CONFIRM_QUESTION_YES"),
                ["messageBtnDig"] = localRpDescMgr:GetRPTextFormated("BTN_TEXT_DIG"),
                ["messageBtnGo"] = localRpDescMgr:GetRPTextFormated("BTN_TEXT_GO"),
                ["messageBtnAddSalary"] = localRpDescMgr:GetRPTextFormated("BTN_TEXT_ADDSALARY"),
                ["messageBtnPleaseStay"] = localRpDescMgr:GetRPTextFormated("BTN_TEXT_PLEASESTAY"),
                ["messageBtnPleaseStay"] = localRpDescMgr:GetRPTextFormated("BTN_TEXT_PLEASESTAY"),
                ["messageBtnGoToResolve"] = localRpDescMgr:GetRPTextFormated("BTN_GO_TO_RESOLVE"),
                ["messageBtnIgnore"] = localRpDescMgr:GetRPTextFormated("BTN_IGNORE"),
                ["messageDemandRewardBtnText"] = localRpDescMgr:GetRPTextFormated("DEMAND_REWARD_BTN_TEXT"),
                ["messageDemandTipContent"] = localRpDescMgr:GetRPTextFormated("MAIL_DEMANDSTART_TIP_CONTENT"),
                ["messageFierceTipContent"] = localRpDescMgr:GetRPTextFormated("MAIL_FIERCE_BUILDING_TIP_CONTENT"),
            }
        },
        {
            model="StaffState",
            localization={
                ["strategyNotEnough"] = localRpDescMgr:GetRPTextFormated("COUNCIL_STRATEGY_NOT_ENOUGH"),
                ["teamLevelNotEnough"] = localRpDescMgr:GetRPTextFormated("COUNCIL_STRATEGY_NOT_ENOUGH_TEAMLEVEL"),
            }
        },
        {
            model="SalaryRaise",
            localization={
                ["think"] = localRpDescMgr:GetRPTextFormated("SALARY_REQUEST_THINK");
                ["no"] = localRpDescMgr:GetRPTextFormated("SALARY_REQUEST_NO");
                ["requestAdjust"] = localRpDescMgr:GetRPTextFormated("REQUEST_SALARY");
                ["curAddress"] = localRpDescMgr:GetRPTextFormated("CUR_ADDRESS");
            }
        },
        {
            model="Illustrate",
            localization={
                ["bookName1"] = localRpDescMgr:GetRPTextFormated("HANDBOOK_BOOKNAME_1"),
                ["bookName2"] = localRpDescMgr:GetRPTextFormated("HANDBOOK_BOOKNAME_2"),
                ["bookName3"] = localRpDescMgr:GetRPTextFormated("HANDBOOK_BOOKNAME_3"),
                ["bookName4"] = localRpDescMgr:GetRPTextFormated("HANDBOOK_BOOKNAME_4"),
                ["bookName5"] = localRpDescMgr:GetRPTextFormated("HANDBOOK_BOOKNAME_5"),
            }
        },
        {
            model="IllustrateStaffTips",
            localization={
                ["fix_age"] = tl["fix_age"],
                ["Level"] = localRpDescMgr:GetRPTextFormated("TEXT_ADVISER_LEVEL"),
            }
        },
        {
            model="Sandbox",
            localization={
                ["creativityName"] = localRpDescMgr:GetRPTextFormated("CREATIVITY_NAME"),
                ["creativityTip"] = localRpDescMgr:GetRPTextFormated("CREATIVITY_TIP"),
            }
        },
        {
            model="ExplorationMap",
            localization={
                ["mapSortName1"] = localRpDescMgr:GetRPTextFormated("EXPLORATION_MAPNAME_1"),
                ["mapSortName2"] = localRpDescMgr:GetRPTextFormated("EXPLORATION_MAPNAME_2"),
            }
        },
        {
            model="Talk",
            localization={
                ["title"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SKIPPLOT_TITLE"),
                ["content"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SKIPPLOT_CONTENT"),
            }
        },
        {
            model="TutorialsMouse",
            localization={
                ["clickMiddle"] = localRpDescMgr:GetRPTextFormated("TUTORIALS_MOUSE_CLICK_MIDDLE"),
                ["clickRight"] = localRpDescMgr:GetRPTextFormated("TUTORIALS_MOUSE_CLICK_RIGHT"),
                ["scroll"] = localRpDescMgr:GetRPTextFormated("TUTORIALS_MOUSE_SCROLL"),
            }
        },
        {
            model="GamePlayerTips",
            localization={
                ["title"] = localRpDescMgr:GetRPTextFormated("GAMEPLAYER_TIPS_TITLE"),
            }
        },
        {
            model="BigMapSuccess",
            localization={
                ["getBuildingCard"] = localRpDescMgr:GetRPTextFormated("BIGMAP_SUCCESS_TITLE_1"),
                ["challengeSuccess"] = localRpDescMgr:GetRPTextFormated("BIGMAP_SUCCESS_TITLE_2"),
            }
        },
        {
            model="FengShuiTipsFloat",
            localization={
                ["fs_hexagram_1"] = localRpDescMgr:GetRPTextFormated("FS_HEXAGRAM_BASE_TYPE_1"), -- 离
                ["fs_hexagram_2"] = localRpDescMgr:GetRPTextFormated("FS_HEXAGRAM_BASE_TYPE_2"),
                ["fs_hexagram_3"] = localRpDescMgr:GetRPTextFormated("FS_HEXAGRAM_BASE_TYPE_3"),
                ["fs_hexagram_4"] = localRpDescMgr:GetRPTextFormated("FS_HEXAGRAM_BASE_TYPE_4"),
                ["fs_hexagram_5"] = localRpDescMgr:GetRPTextFormated("FS_HEXAGRAM_BASE_TYPE_5"),
                ["fs_hexagram_6"] = localRpDescMgr:GetRPTextFormated("FS_HEXAGRAM_BASE_TYPE_6"),
                ["fs_hexagram_7"] = localRpDescMgr:GetRPTextFormated("FS_HEXAGRAM_BASE_TYPE_7"),
                ["fs_hexagram_8"] = localRpDescMgr:GetRPTextFormated("FS_HEXAGRAM_BASE_TYPE_8"), -- 艮
                ["fs_result_1"] = localRpDescMgr:GetRPTextFormated("FENG_SHUI_RESULT_1"), -- 大凶
                ["fs_result_2"] = localRpDescMgr:GetRPTextFormated("FENG_SHUI_RESULT_2"), 
                ["fs_result_3"] = localRpDescMgr:GetRPTextFormated("FENG_SHUI_RESULT_3"), 
                ["fs_result_4"] = localRpDescMgr:GetRPTextFormated("FENG_SHUI_RESULT_4"), 
                ["fs_result_5"] = localRpDescMgr:GetRPTextFormated("FENG_SHUI_RESULT_5"), -- 大吉
                ["fs_special_up"] = localRpDescMgr:GetRPTextFormated("FS_SPECIAL_POSITIVE"),
                ["fs_special_down"] = localRpDescMgr:GetRPTextFormated("FS_SPECIAL_NEGETIVE"),
            }
        },
        {
            model = "FengShuiDetailTips",
            localization = {
                ["fs_title"] = localRpDescMgr:GetRPTextFormated("RESOURCE_FENG_SHUI_TITLE"),
                ["fs_no_skill"] = localRpDescMgr:GetRPTextFormated("RESOURCE_FENG_SHUI_NO_SKILL"),
                ["fs_open"] = localRpDescMgr:GetRPTextFormated("RESOURCE_FENG_SHUI_OPEN"),
                ["fs_close_tips"] = localRpDescMgr:GetRPTextFormated("RESOURCE_FENG_SHUI_CLOSE_TIPS"),
                ["fs_open_tips"] = localRpDescMgr:GetRPTextFormated("RESOURCE_FENG_SHUI_OPEN_TIPS"),
            }
        },
        {
            model="BuildTipsResearch",
            localization={
                ["tipBtn_research"]     = localRpDescMgr:GetRPTextFormated("RESEARCH_BUTTON_TEXT_1"),
                ["tipBtn_researching"]  = localRpDescMgr:GetRPTextFormated("RESEARCH_BUTTON_TEXT_2"),
                ["tipBtn_success"]      = localRpDescMgr:GetRPTextFormated("RESEARCH_BUTTON_TEXT_3"),
                ["tipBtn_fail"]      = localRpDescMgr:GetRPTextFormated("RESEARCH_BUTTON_TEXT_4"),
                ["researchCardName"]      = localRpDescMgr:GetRPTextFormated("RESEARCH_CARD_TYPE_NAME"),
            }
        },
        {
            model="ResearchMain",
            localization={
                ["Day"] = localRpDescMgr:GetRPTextFormated("TXT_DAY_COMMON"),
                ["Times"] = localRpDescMgr:GetRPTextFormated("TXT_RESEARCH_INVEST_UNIT_NUM"),
                ["Researching"] = localRpDescMgr:GetRPTextFormated("TXT_RESEARCHING_BUILDING_NAME"),
                ["UnlockCards"] = localRpDescMgr:GetRPTextFormated("TXT_UNLOCK_RESEARCH_CARDS");
                ["NotReachLevel"] = localRpDescMgr:GetRPTextFormated("RESEARCH_NOT_REACH_BOOMLEVEL_TEXT");
                ["DevelopmentTitle"] = localRpDescMgr:GetRPTextFormated("RESEARCH_DEVELOPMENT_INF_TITLE"),
                ["RDAccelerateTitle"] = localRpDescMgr:GetRPTextFormated("TXT_BLUEPRINT_SKILL_ACTIVED_TITLE"),
                ["DevelopmentType_2"] = localRpDescMgr:GetRPTextFormated("RESEARCH_DEVELOPMENT_TYPE_2"),
                ["DevelopmentType_3"] = localRpDescMgr:GetRPTextFormated("RESEARCH_DEVELOPMENT_TYPE_3"),
                ["DevelopmentType_4"] = localRpDescMgr:GetRPTextFormated("RESEARCH_DEVELOPMENT_TYPE_4"),
                ["DevelopmentType_5"] = localRpDescMgr:GetRPTextFormated("RESEARCH_DEVELOPMENT_TYPE_5"),
                ["DevelopmentType_6"] = localRpDescMgr:GetRPTextFormated("RESEARCH_DEVELOPMENT_TYPE_6"),
                ["DevelopmentType_11"] = localRpDescMgr:GetRPTextFormated("RESEARCH_DEVELOPMENT_TYPE_11"),
                ["CardQuality_1"] = localRpDescMgr:GetRPTextFormated("BUILDING_QUALITY_NAME01"),
                ["CardQuality_2"] = localRpDescMgr:GetRPTextFormated("BUILDING_QUALITY_NAME02"),
                ["CardQuality_3"] = localRpDescMgr:GetRPTextFormated("BUILDING_QUALITY_NAME03"),
                ["CardQuality_4"] = localRpDescMgr:GetRPTextFormated("BUILDING_QUALITY_NAME04"),
                ["CardQuality_5"] = localRpDescMgr:GetRPTextFormated("BUILDING_QUALITY_NAME05"),
                ["GoalLevel_0"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_0"),
                ["GoalLevel_1"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_1"),
                ["GoalLevel_2"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_2"),
                ["GoalLevel_3"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_3"),
                ["GoalLevel_4"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_4"),
                ["GoalLevel_5"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_5"),
                ["GoalLevel_6"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_6"),
                ["GoalLevel_7"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_7"),
                ["GoalLevel_8"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_8"),
                ["GoalLevel_9"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_9"),
                ["GoalLevel_10"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_10"),
                ["GoalLevel_11"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_11"),
                ["GoalLevel_12"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_12"),
                ["GoalLevel_13"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_13"),
                ["GoalLevel_14"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_14"),
                ["GoalLevel_SANDBOX_0"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_0"),
                ["GoalLevel_SANDBOX_1"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_1"),
                ["GoalLevel_SANDBOX_2"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_2"),
                ["GoalLevel_SANDBOX_3"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_3"),
                ["GoalLevel_SANDBOX_4"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_4"),
                ["GoalLevel_SANDBOX_5"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_5"),
                ["GoalLevel_SANDBOX_6"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_6"),
                ["GoalLevel_SANDBOX_7"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_7"),
                ["GoalLevel_SANDBOX_8"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_8"),
                ["GoalLevel_SANDBOX_9"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_9"),
                ["GoalLevel_SANDBOX_10"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_10"),
                ["GoalLevel_SANDBOX_11"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_11"),
                ["GoalLevel_SANDBOX_12"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_12"),
                ["GoalLevel_SANDBOX_13"] = localRpDescMgr:GetRPTextFormated("BOOM_MISSION_TITLE_SANDBOX_13"),
            }
        },
        {
            model = "Bidding",
            localization = {
                ["baseMoneyTitle"] = localRpDescMgr:GetRPTextFormated("ADVISER_DIGCORNER_BASE_MONEY_TITLE"),
                ["selfAdviserPriceTitle"] = localRpDescMgr:GetRPTextFormated("ADVISER_DIGCORNER_PRICE_TITLE"),
                ["selfHotelPriceTitle"] = localRpDescMgr:GetRPTextFormated("TOUR_COMPETE_PRICE_TITLE"),
            }
        },
        {
            model = "Statistics",
            localization = {
                ["BlockName_1"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_1"),
                ["BlockName_2"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_2"),
                ["BlockName_3"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_3"),
                ["BlockName_4"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_4"),
                ["BlockName_5"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_5"),
                ["BlockName_6"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_6"),
                ["BlockName_7"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_7"),
                ["BlockName_8"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_8"),
                ["BlockName_9"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_9"),
                ["BlockName_10"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_10"),
                ["BlockNameSandbox_1"] = localRpDescMgr:GetRPTextFormated("BLOCKNAME_SANDBOX_1"),
            }
        },
        {
            model = "SaltDeal",
            localization = {
                ["sellButtonName"] = localRpDescMgr:GetRPTextFormated("SELL"),
                ["purchaseButtonName"] = localRpDescMgr:GetRPTextFormated("PURCHASE"),
                ["sellBalanceTitle"] = localRpDescMgr:GetRPTextFormated("SALT_TRADING_UI_TEXT_01"),
                ["purchaseBalanceTitle"] = localRpDescMgr:GetRPTextFormated("SALT_TRADING_UI_TEXT_02"),
                ["sellNumTitle"] = localRpDescMgr:GetRPTextFormated("SALT_TRADING_UI_TEXT_03"),
                ["purchaseNumTitle"] = localRpDescMgr:GetRPTextFormated("SALT_TRADING_UI_TEXT_04"),
                ["sellCheckoutTitle"] = localRpDescMgr:GetRPTextFormated("SALT_TRADING_UI_TEXT_05"),
                ["purchaseCheckoutTitle"] = localRpDescMgr:GetRPTextFormated("SALT_TRADING_UI_TEXT_06"),
            }
        },
        {
            model = "RECHUD",
            localization = {
                ["FilterType_0"] = localRpDescMgr:GetRPTextFormated("RECHUD_FILTER_TYPE01"),
                ["FilterType_1"] = localRpDescMgr:GetRPTextFormated("RECHUD_FILTER_TYPE02"),
                ["FilterType_2"] = localRpDescMgr:GetRPTextFormated("RECHUD_FILTER_TYPE03"),
                ["FilterType_3"] = localRpDescMgr:GetRPTextFormated("RECHUD_FILTER_TYPE04"),
                ["FilterType_4"] = localRpDescMgr:GetRPTextFormated("RECHUD_FILTER_TYPE05"),
            }
        },
        {
            model = "ScenicTips",
            localization = {
                ["TouristsNumTitle"] = localRpDescMgr:GetRPTextFormated("TOURISTS_NUM_TITEL"),
                ["CurrentTouristsNumTitle"] = localRpDescMgr:GetRPTextFormated("CURRENT_TOURISTS_NUM_TITEL"),
                ["TotalTouristsNumTitle"] = localRpDescMgr:GetRPTextFormated("TOTAL_TOURISTS_NUM_TITEL"),
                ["MoodTitle"] = localRpDescMgr:GetRPTextFormated("MOOD_TITEL"),
                ["CurrentMoodTitle"] = localRpDescMgr:GetRPTextFormated("CURRENT_MOOD_TITEL"),
                ["TotalMoodTitle"] = localRpDescMgr:GetRPTextFormated("TOTAL_MOOD_TITEL"),
            }
        },
        {
            model = "ConfirmSwitch",
            localization = {
                ["DefaultYes"] = localRpDescMgr:GetRPTextFormated("CONFIRM_SWITCH_YES"),
                ["DefaultNo"] = localRpDescMgr:GetRPTextFormated("ORDER_BTN_DELAY_CANCEL"),
            }
        },
    };
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateLocalization, data);
    self:UIConfigInit();
end
function LCommonProvider:UIConfigInit()
    self:S2UI_ResourcesConfig();
    self:S2UI_GamePlayerConfig();
    self:S2UI_MarketConfig();
    self:S2UI_OrderTipsConfig();
    self:S2UI_AccoundBookConfig();
    self:UI2S_GetTeachingTipsConfig();
    self:S2UI_LeaderboardTipsConfig();
    self:S2UI_ScreenOrderConfig();
    self:S2UI_ArbitrationtipsConfig();
    g_FamousCityMgr:S2UI_FamousCityConfig();
    g_LTeachingTipsMgr:ResetUI();
    g_LHBUIProvider:EmitTo("LOfficeProvider", g_LHBUIEvents.UI2S_GetProsperityTitles);
end
function LCommonProvider:S2UI_ScreenOrderConfig()
    local orderdefine = ImportScript("script/gameplay/order/order_define.lua").LOrderDefine;
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_ScreenOrderConfig,{
        rp={
            delay = g_LRPDescManager:GetRPTextFormated("ORDER_DELAY_DAY"),
            day = g_LRPDescManager:GetRPTextFormated("TXT_DAY_COMMON"),
        },
        delayDay = orderdefine.DelayDay,
    })
end
function LCommonProvider:S2UI_LeaderboardTipsConfig()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_LeaderboardTipsConfig,{
        none = g_LRPDescManager:GetRPTextFormated("ZANWU")
    });
end
function LCommonProvider:S2UI_AccoundBookConfig()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_AccoundBookConfig, {
        [g_BuildingCompetition.TYPE.NORMAL] = g_LRPDescManager:GetRPTextFormated("TXT_BUILDING_COMPETITION_NORMAL"),
        [g_BuildingCompetition.TYPE.INTENSE] = g_LRPDescManager:GetRPTextFormated("TXT_BUILDING_COMPETITION_INTENSE"), 
        [g_BuildingCompetition.TYPE.CRUEL] = g_LRPDescManager:GetRPTextFormated("TXT_BUILDING_COMPETITION_CRUEL"),
        ["Money"]=g_LRPDescManager:GetRPTextFormated("PROB_EVENT_RESOURCE_MONEY"),
        ["Mineral"]=g_LRPDescManager:GetRPTextFormated("PROB_EVENT_RESOURCE_MINERAL"),
        ["Wood"]=g_LRPDescManager:GetRPTextFormated("PROB_EVENT_RESOURCE_WOOD"),
        ["Cloth"]=g_LRPDescManager:GetRPTextFormated("PROB_EVENT_RESOURCE_CLOTH"),
        ["Food"]=g_LRPDescManager:GetRPTextFormated("PROB_EVENT_RESOURCE_FOOD"),
        ["Water"]=g_LRPDescManager:GetRPTextFormated("PROB_EVENT_RESOURCE_WATER"),
        ["Salt"]=g_LRPDescManager:GetRPTextFormated("PROB_EVENT_RESOURCE_SALT"),
        ["Liquor"]=g_LRPDescManager:GetRPTextFormated("PROB_EVENT_RESOURCE_LIQUOR"),
        MainTitle = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_MAIN_TITLE"),
        Detail = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_MAIN_ROW_DETAIL"),
        AccoundNum = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_MAIN_ROW_NUM"),
        DetailContent1 = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_MAIN_DETAIL_CONTENT_01"),
        DetailContent2 = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_MAIN_DETAIL_CONTENT_02"),
        DetailContent3 = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_MAIN_DETAIL_CONTENT_03"),
        DetailContent4 = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_MAIN_DETAIL_CONTENT_04"),
        TotalContent = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_MAIN_TOTAL_CONTENT"),
        BuildingTitle = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_TITLE"),
        BuildingName = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_ROW_NAME"),
        BuildingNum = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_ROW_NUM"),
        BuildingPopulation = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_ROW_POPULATION"),
        BuildingBonus = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_ROW_BONUS"),
        BuildingStand = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_ROW_PRODUCT_RATED"),
        BuildingReal = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_ROW_PRODUCT_CURRENT"),
        BuildingMaint = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_ROW_MAINTENANCE"),
        BuildingPure = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_ROW_PRODUCT_NET"),
        BuildingContent = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_BUILDING_TOTAL_CONTENT"),
        AdviserInc = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_ADVISER_DESC"),
        AdviserTitle = g_LRPDescManager:GetRPTextFormated("ACCOUNDBOOK_ADVISER_TITLE"),
    });
end
function LCommonProvider:S2UI_MarketConfig()
    local OrderDefine = ImportScript("script/gameplay/order/order_define.lua").LOrderDefine;
    local allRpdesc = {
        RESOURCE_MARKET_TREND = g_LRPDescManager:GetRPTextFormated("RESOURCE_MARKET_TREND"),
        PURCHASE = g_LRPDescManager:GetRPTextFormated("PURCHASE"),
        SELL = g_LRPDescManager:GetRPTextFormated("SELL"),
        PURCHASE_NUMBER = g_LRPDescManager:GetRPTextFormated("PURCHASE_NUMBER"),
        SELL_NUMBER = g_LRPDescManager:GetRPTextFormated("SELL_NUMBER"),
        REMAIN_TIME = g_LRPDescManager:GetRPTextFormated("ORDER_REMAIN_TIME"),
        ORDER_DELAY_TIP = g_LRPDescManager:GetRPTextFormated("ORDER_DELAY_TIPS"),
        ORDER_OVER_TIP = g_LRPDescManager:GetRPTextFormated("ORDER_OVER_TIPS"),
        ORDER_HOVER_TIP = g_LRPDescManager:GetRPTextFormated("ORDER_DELAY_HOVER_TIPS"),
        ORDER_BTN_CANCEL = g_LRPDescManager:GetRPTextFormated("ORDER_BTN_DELAY_CANCEL"),
        ORDER_BTN_DELAYOK = g_LRPDescManager:GetRPTextFormated("ORDER_BTN_DELAY_OK"),
        ORDER_BTN_OVEROK = g_LRPDescManager:GetRPTextFormated("ORDER_BTN_OVER_OK"),
        ORDER_TITLE_OVER = g_LRPDescManager:GetRPTextFormated("ORDER_TITLE_OVER"),
        ORDER_TITLE_DELAY = g_LRPDescManager:GetRPTextFormated("ORDER_TITLE_DELAY"),
        ORDER_TOTAL_TITLE = g_LRPDescManager:GetRPTextFormated("ORDER_TOTAL_TITLE"),
        ORDER_ING = g_LRPDescManager:GetRPTextFormated("ORDER_ING"),
    }
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_MarketConfig, {
        rpdesc = allRpdesc,
        delayDay = OrderDefine.DelayDay,
    });
end
function LCommonProvider:S2UI_OrderTipsConfig()
    local localRpDesMgr = g_LRPDescManager;
    local allRpdesc = {
        ORDER_DELAY_TIP = localRpDesMgr:GetRPTextFormated("ORDER_DELAY_TIPS"),
        ORDER_OVER_TIP = localRpDesMgr:GetRPTextFormated("ORDER_OVER_TIPS"),
        ORDER_HOVER_TIP = localRpDesMgr:GetRPTextFormated("ORDER_DELAY_HOVER_TIPS"),
        ORDER_BTN_CANCEL = localRpDesMgr:GetRPTextFormated("ORDER_BTN_DELAY_CANCEL"),
        ORDER_BTN_DELAYOK = localRpDesMgr:GetRPTextFormated("ORDER_BTN_DELAY_OK"),
        ORDER_BTN_OVEROK = localRpDesMgr:GetRPTextFormated("ORDER_BTN_OVER_OK"),
        ORDER_TITLE_OVER = localRpDesMgr:GetRPTextFormated("ORDER_TITLE_OVER"),
        ORDER_TITLE_DELAY = localRpDesMgr:GetRPTextFormated("ORDER_TITLE_DELAY"),
        ORDER_TOTAL_TITLE = localRpDesMgr:GetRPTextFormated("ORDER_TOTAL_TITLE"),
        ORDER_DELAY_WARN = localRpDesMgr:GetRPTextFormated("ORDER_DELAYED"),
        CONFIRM_ORDER_TITLE = localRpDesMgr:GetRPTextFormated("MARKET_ORDER_SHORT_TITLE"),
        CONFIRM_ORDER_TIP = localRpDesMgr:GetRPTextFormated("MARKET_ORDER_SHORT_TIPS"),
        CONFIRM_ORDER_OK = localRpDesMgr:GetRPTextFormated("CONFIRM_CONTROL_CONFLICT_YES"),
    }
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OrderTipsConfig, allRpdesc);
end
function LCommonProvider:UI2S_InitGamePlayerUI()
    g_camp:UpdateBoom();
end
function LCommonProvider:UI2S_GetTeachingInfo(data)
    g_LTeachingTipsMgr:UI2S_GetTeachingInfo(data);
end
function LCommonProvider:UI2S_SetTaught(data)
    -- CommonProvider此时还能接收UI事件, 但是教学泡泡模块可能已经卸载了
    if g_LTeachingTipsMgr then
        g_LTeachingTipsMgr:UI2S_SetTaught(data);
    end
end
function LCommonProvider:UI2S_GetTeachingTipsConfig(data)
    g_LTeachingTipsMgr:UI2S_GetTeachingTipsConfig(data);
end
function LCommonProvider:S2UI_OnSendWonderKeys(data)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnSendWonderKeys, data);
end
function LCommonProvider:_syncUIDisaster()
    -- commonProvider加载太早了,需要再读一下更新后的摄像机配置
    self.m_nMinRadius = g_CameraDefine:GetCurDefine().nMinRadius;
    self.m_nMaxRadius = g_CameraDefine:GetCurDefine().nMaxRadius;
    self:S2UI_UpdateMoment();
end
function LCommonProvider:UI2S_CheckCanStartTiltShift()
    if g_FunctionManager:CheckFuncIsUnlock(g_functionType.TILTSHIFT) ~= g_functionState.OPEN then
        g_LTalkManager:TriggerTalk({
            dialogueID = "E_CANNOT_OPEN_WHEN_CITYLEVLE_NOT_ENOUGH",
            type = g_LTalkDefine.TYPE.SYSTEMTIPS,
        });
        return;
    else
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_StartTiltShift);
    end
end
function LCommonProvider:UI2S_CheckCanStartScenery()
    if g_FunctionManager:CheckFuncIsUnlock(g_functionType.SCENERY) ~= g_functionState.OPEN then
        g_LTalkManager:TriggerTalk({
            dialogueID = "E_CANNOT_OPEN_WHEN_CITYLEVLE_NOT_ENOUGH",
            type = g_LTalkDefine.TYPE.SYSTEMTIPS,
        });
    else
        g_LHBUI:Emit(g_LHBUIEvents.S2UI_StartSenery, false);
    end
end
function LCommonProvider:UI2S_StartTiltShiftStatus()
    local nDelay = 2;
    self:StartBlackCurtain(nDelay);
    g_GameWorld:SetIsInTiltShiftStatus(true);
    g_World:SetTickable(false);
    g_BuildingWorldModule:SetAllWoHeadVisible(false);
    local pause = g_Game:IsPaused();
    if not pause then
        g_GameWorld:LogicPause();
        g_Game:LogicTickPause();
    else
        g_GameWorld:SetSpecialKmscMoveStatus(false) -- 特殊kmsc标记 解决滑动位移
    end
    g_GameWorld.bLastPauseStatus = pause;
    -- 先全部暂停
    -- 恢复部分表现逻辑
    g_GameWorld:HideGeologicMap();
    
    g_timer:Register(g_timer.TT_DEFAULT, nDelay, function ()
        g_GameWorld:SetSpecialKmscMoveStatus(true)
        g_RoleManager:LogicResume();
        g_GameWorld.GameWorldAudio:ResumeGameWorldAudio();
        g_GameWorld.VehiclePresentationInst:LogicResume();
        g_BuildingWorldModule:LogicResume();
        g_GameWorld:ResumeSeasonPresentations();
        g_GameWorld:ResumeWeatherPresentations();
        g_EnvironmentMgr:ChangePauseState(false);
        g_CameraController:EnterTiltShiftMode();
    end);
end
function LCommonProvider:UI2S_EndTiltShiftStatus()
    local nDelay = 2;
    g_GameWorld:SetIsInTiltShiftStatus(false);
    self:StartBlackCurtain(nDelay);
    g_World:SetTickable(true);
    g_BuildingWorldModule:SetAllWoHeadVisible(true);
    if g_GameWorld.bLastPauseStatus == true then
        g_GameWorld:LogicPause();
        g_Game:LogicTickPause();
    elseif g_GameWorld.bLastPauseStatus == false then
        g_GameWorld:LogicResume();
        g_Game:LogicTickResume();
    end
    g_GameWorld.bLastPauseStatus = nil;
    g_GameWorld:RestoreGeologicMap();
    g_timer:Register(g_timer.TT_DEFAULT, nDelay, function ()
        g_CameraController:LeaveTiltShiftMode();
    end);
end
function LCommonProvider:UI2S_StartTiltShiftStatusByESC()
    g_GameWorld:SetIsInTiltShiftStatus(true);
    g_World:SetTickable(false);
    -- g_BuildingWorldModule:SetAllWoHeadVisible(false);
    local pause = g_Game:IsPaused();
    if not pause then
        g_GameWorld:LogicPause();
        g_Game:LogicTickPause();
    end
    g_GameWorld.bLastPauseStatus = pause;
    -- 先全部暂停
    -- 恢复部分表现逻辑
    if g_SimWorld then
        g_SimWorld:LogicResume();
    end
    g_GameWorld:HideGeologicMap();
    g_RoleManager:LogicResume();
    g_GameWorld.GameWorldAudio:ResumeGameWorldAudio();
    g_GameWorld.VehiclePresentationInst:LogicResume();
    g_BuildingWorldModule:LogicResume();
    g_GameWorld:ResumeSeasonPresentations();
    g_GameWorld:ResumeWeatherPresentations();
    g_EnvironmentMgr:ChangePauseState(false);
    g_CameraController:EnterTiltShiftMode();
end
function LCommonProvider:UI2S_EndTiltShiftStatusByESC()
    g_GameWorld:SetIsInTiltShiftStatus(false);
    g_World:SetTickable(true);
    -- g_BuildingWorldModule:SetAllWoHeadVisible(true);
    if g_GameWorld.bLastPauseStatus == true then
        g_GameWorld:LogicPause();
        g_Game:LogicTickPause();
        if g_SimWorld then
            g_SimWorld:LogicPause();
        end
    elseif g_GameWorld.bLastPauseStatus == false then
        g_GameWorld:LogicResume();
        g_Game:LogicTickResume();
        if g_SimWorld then
            g_SimWorld:LogicResume();
        end
    end
    g_GameWorld.bLastPauseStatus = nil;
    g_GameWorld:RestoreGeologicMap();
    g_CameraController:LeaveTiltShiftMode();
end
--- 设置游戏逻辑暂停但表现不停（npc暂停）
function LCommonProvider:SetSceneryStatus(bShow)
    if bShow then
        if g_GameWorld.bLastPauseStatus == true then
            g_Game:LogicTickPause();
            g_GameWorld:LogicPause();
            if g_SimWorld then
                g_SimWorld:LogicPause();
            end
        elseif g_GameWorld.bLastPauseStatus == false then
            g_Game:LogicTickResume();
            g_GameWorld:LogicResume();
            if g_SimWorld then
                g_SimWorld:LogicResume();
            end
        end
        
        g_GameWorld.bLastPauseStatus = nil;
        
        g_World:SetTickable(true);
        -- g_BuildingWorldModule:SetAllWoHeadVisible(true);
    else
        g_GameWorld.bLastPauseStatus = g_Game:IsPaused();
        g_World:SetTickable(false);
        -- g_BuildingWorldModule:SetAllWoHeadVisible(false);
        -- 先全部暂停
        -- if not g_Game:IsPaused() then
        g_Game:LogicTickResume();
        g_GameWorld:LogicResume();
        g_Game:LogicTickPause();
        g_GameWorld:LogicPause();
        -- end
        -- 恢复部分表现逻辑
        g_RoleManager:LogicResume();
        g_GameWorld.GameWorldAudio:ResumeGameWorldAudio();
        g_GameWorld.VehiclePresentationInst:LogicResume();
        g_BuildingWorldModule:LogicResume();
        g_GameWorld:ResumeSeasonPresentations();
        g_GameWorld:ResumeWeatherPresentations();
        g_EnvironmentMgr:ChangePauseState(false);
        if g_SimWorld then
            g_SimWorld:LogicResume();
        end
    end
end
function LCommonProvider:SetGameStatusWhenScenery(state)
    if state then
        g_Game:LogicTickResume();
        g_GameWorld:LogicResume();
        -- g_World:SetTickable(true);
    else
        -- g_World:SetTickable(false);
        -- 先全部暂停
        -- if not g_Game:IsPaused() then
        g_Game:LogicTickResume();
        g_GameWorld:LogicResume();
        g_Game:LogicTickPause();
        g_GameWorld:LogicPause();
        -- end
        
        -- 恢复部分表现逻辑
        g_RoleManager:LogicResume();
        g_GameWorld.GameWorldAudio:ResumeGameWorldAudio();
        g_GameWorld.VehiclePresentationInst:LogicResume();
        g_BuildingWorldModule:LogicResume();
        g_GameWorld:ResumeSeasonPresentations();
        g_GameWorld:ResumeWeatherPresentations();
        g_EnvironmentMgr:ChangePauseState(false);
    end
end
function LCommonProvider:UI2S_SetSceneryStatus(bShow)
    self:SetSceneryStatus(bShow);
    if bShow then
        g_BuildingWorldModule:SetAllWoHeadVisible(true);
        g_GameWorld:SetSceneryStatus(false);
        g_GameWorld:SwitchSceneryMode(false);
    else
        g_BuildingWorldModule:SetAllWoHeadVisible(false); 
        g_GameWorld:SetSceneryStatus(true);
        g_GameWorld:SwitchSceneryMode(true);
    end
    -- 判断创建画廊文件夹
    local path = game_world_define.FOLD_PATHS["Gallery"];
    local bExist = FS.Path.Exists(path);
    if path and not bExist then
        FS.MakeDir(path);
    end
end
function LCommonProvider:UI2S_OnSetGameStateWhenScenery(state)
    if state then
        g_GameWorld:ResetWorldStateWhenContinue();
    else
        g_GameWorld:InitWorldStateWhenContinue()
    end
    self:SetGameStatusWhenScenery(state);
end
function LCommonProvider:UI2S_SetEditModeStatus(bShow)
    self:SetSceneryStatus(bShow);
end
function LCommonProvider:UI2S_RecieveReward(nType)
    -- 将节日礼物设置成 已领取
    g_FestivalManager:SetHolidayGiftOpenByType(nType,true);
    g_FestivalManager:SendReward(nil,nType,1)
    -- 更新信件UI 
end
function LCommonProvider:UI2S_OnConfirmFestivalRewardByType(nType)
    g_FestivalManager:RecieveReward(nil,nType,1);
    -- 领取新手奖励事件
    if nType == 5 then
        g_EventDispatcherManager:DispatchEvent(g_EventModel.LEVENT_GAMEPLAY, g_GameplayEventType.RECIEVE_GUIDE_REWARD);
    end
end
function LCommonProvider:S2UI_OnUpdateWindData()
    local nWindLevel = g_WeatherLogicMgr:GetCurrentWind();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateWindData, {windLevel = nWindLevel});
end
function LCommonProvider:UI2S_ChangeWindLevel(level)
    local windCfg = g_WeatherLogicMgr:GetWindRangeCfgByLevel(level);
    if windCfg then
        g_WeatherLogicMgr:_UpdateWind(windCfg.fWindSpeed,{-1,0,0});
    end
end
function LCommonProvider:S2UI_OnUpdateFilterData()
    local nFilterId = g_EnvironmentMgr:GetCurFilterID();
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateFilterData, {curFilterId = nFilterId});
end
function LCommonProvider:UI2S_ChangeFilter(filterID)
    if filterID > 0 then
        g_EnvironmentMgr:SetCurFilterByID(filterID);
        local bSave = g_EnvironmentMgr:GetIsFilterSave();
        if bSave then
            g_GameWorld:UpdateOriginalFilterID();
        end
    end
end
function LCommonProvider:S2UI_OnUpdateCameraFovy(fovy)
    -- local _, fovy = g_CameraController:GetPerspective();
    local focal = g_CameraController:FovyToFocal(fovy);
    local nFocalPer = focal * 100 / 5;
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateCameraFovy, nFocalPer);
end
function LCommonProvider:S2UI_OnUpdateCameraBlurSize(blurSize)
    -- local blurSize = g_DOF:GetGatherBlurSize();
    local nBlurSizePer = blurSize * 100 / 30;
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_OnUpdateCameraBlurSize, nBlurSizePer);
end
function LCommonProvider:UI2S_SetCameraSettingInfo(data)
    if not data then
        return;
    end
    if data.Type == g_CameraDefine.CameraSettingType.Pan then
        g_CameraController:SetPanSpeed(data.value);
    elseif data.Type == g_CameraDefine.CameraSettingType.Zoom then
        g_CameraController:SetZoomSpeed(data.value);
    elseif data.Type == g_CameraDefine.CameraSettingType.Rotate then
        g_CameraController:SetRotateSpeed(data.value);
    elseif data.Type == g_CameraDefine.CameraSettingType.Focal then
        local fovy = g_CameraController:FocalToFovy(data.value);
        g_CameraController:SetFovAngleY(fovy);
    elseif data.Type == g_CameraDefine.CameraSettingType.BlurSize then
        g_DOF:SetGatherBlurSize(data.value);
    end
end
function LCommonProvider:UI2S_SwitchCameraMode()
    g_CameraController:SetFovAngleY(camera_define.tbTiltShiftState.nFov);
    -- g_DOF:Enable(true);
    g_DOF:EnableAutoFocalDistance(true);
    g_DOF:SetGatherBlurSize(camera_define.tbTiltShiftState.nBlur);
    g_DOF:SetClearnessRange(camera_define.tbTiltShiftState.nClearnessRange);
end
function LCommonProvider:UI2S_OnOperateScreenShot()
    local path = game_world_define.FOLD_PATHS["Gallery"];
    local bExist = FS.Path.Exists(path);
    if path and not bExist then
        FS.MakeDir(path);
    end
    g_CoreEngine:DoCapture();
end
function LCommonProvider:UI2S_OnOperateScreenRecord(bStart)
    local path = game_world_define.FOLD_PATHS["Gallery"];
    local bExist = FS.Path.Exists(path);
    if path and not bExist then
        FS.MakeDir(path);
    end
    g_CoreEngine:DoRecord();
end
function LCommonProvider:UI2S_GetGeologicMapLayerInfo()
    local tbSimpleInfos = g_LGeologicMap:GetLayersSimpleInfo()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_SetGeologicMapLayerInfo, tbSimpleInfos);
end
function LCommonProvider:UI2S_SetGeologicMapLayerInfo(tabLayers)
    for i, v in pairs(tabLayers) do
        if v.Visible then
            g_LGeologicMap:SelectedLayer(i)
        else
            g_LGeologicMap:UnselectedLayer(i) 
        end
    end
end
--- UI点击开始新游戏,弹出复制自动存档二次确认弹窗
function LCommonProvider:UI2S_CoverAutoArchivesReminder(data)
    local dataset = {};
    local bNewGame = data.bNewGame or false;
    if bNewGame then
        dataset.content = g_LRPDescManager:GetRPTextFormated("AUTOSAVE_OVERWRITE_CONTENT", {
            DataName = data.archiveName,
        });
    else
        dataset.content = g_LRPDescManager:GetRPTextFormated("AUTOSAVE_OVERWRITE_CONTENT_2", {
            DataName = data.archiveName,
        });
    end
    dataset.title = g_LRPDescManager:GetRPTextFormated("AUTOSAVE_OVERWRITE_TITLE");
    dataset.yes = g_LRPDescManager:GetRPTextFormated("AUTOSAVE_OVERWRITE_BUTTON_02");
    dataset.no = g_LRPDescManager:GetRPTextFormated("AUTOSAVE_OVERWRITE_BUTTON_01");
    dataset.confirmIndex = data.confirmIndex;
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_ShowConfirmCopyArchiveReminder,dataset); -- 二次确认弹窗
end
function LCommonProvider:S2UI_GuideShowStageConditions(index)
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_GuideShowStageConditions,index);
end
function LCommonProvider:S2UI_GuideShowStageDetails()
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_GuideShowStageDetails);
end
--- 更新建筑状态描述
function LCommonProvider:S2UI_UpdateBuildingStateDesc(building)
    local data = {
        buildStateDesc = self:_GetBuildStateDesc(building, false)
    };
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateBuildingStateDesc,data);
end
function LCommonProvider:S2UI_UpdateHoverBuildingStateDesc(building)
    local data = {
        buildStateDesc = self:_GetBuildStateDesc(building, false)
    };
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_UpdateHoverBuildingStateDesc,data);
end
function LCommonProvider:UI2S_OnSandboxOpenedAni()
    g_LStoryManager:OnEndOpenSandbox();
end
function LCommonProvider:GetReignReward(Rewards)
    local res = {};
    if (Rewards) then
        for _,Reward in ipairs(Rewards) do
            local rewardType = Reward.Type;
            local layoutType = Reward.LayoutType;
            local dumpReward = nil;
            if rewardType == "buildingCard" then
                local g,d,p,l = table.unpack(Reward.Source[1]);
                dumpReward = g_LBuildingCardManager:dumpBuildingCard(g, d, p, l);
                dumpReward.rewardType = rewardType;
                dumpReward.layoutType = layoutType;
                table.insert(res,dumpReward);
            elseif rewardType == "adviserCard" then
                local g,d,p,l = table.unpack(Reward.Source[1]);
                local adviserCard = g_LAdviserCardManager:GetAdviserCardByGDPL(g, d, p, l);
                dumpReward = g_LHBUIProvider:GetProvider("LOfficeProvider"):getAdviserCardData(adviserCard);
                dumpReward.rewardType = rewardType;
                dumpReward.layoutType = layoutType;
                table.insert(res,dumpReward);
            elseif rewardType == "talent" then
                dumpReward = {
                    Name = Reward.Name,
                    Desc = Reward.Desc,
                    Icon = Reward.Icon,
                };
                dumpReward.rewardType = rewardType;
                dumpReward.layoutType = layoutType;
                table.insert(res,dumpReward);
            elseif rewardType == "unlock" then
                dumpReward = {
                    Name = Reward.Name,
                    Desc = Reward.Desc,
                    Icon = Reward.Icon,
                };
                dumpReward.rewardType = rewardType;
                dumpReward.layoutType = layoutType;
                table.insert(res,dumpReward);
            elseif rewardType == "risk" then
                dumpReward = {
                    Name = Reward.Name,
                    Desc = Reward.Desc,
                    Icon = Reward.Icon,
                };
                dumpReward.rewardType = rewardType;
                dumpReward.layoutType = layoutType;
                table.insert(res,dumpReward);
            elseif rewardType == "vehicleCard" then
                local g,d,p,l = table.unpack(Reward.Source[1]);
                local card = g_LVehicleCardManager:GetVehicleCardByGDPL(g, d, p, l);
                if not card then
                    LOG_E("Not exist Vehicle card",g,d,p,l);
                    dumpReward = {};
                else
                    local data = card:OnFullSerializing();
                    dumpReward =  data and data.tabMateData;
                    dumpReward.rewardType = rewardType;
                    dumpReward.layoutType = layoutType;
                    table.insert(res,dumpReward);
                end
            elseif rewardType == "wonderCard" then
                local g,d,p,l = table.unpack(Reward.Source[1]);
                dumpReward = g_LBuildingCardManager:dumpBuildingCard(g, d, p, l);
                dumpReward.rewardType = rewardType;
                dumpReward.layoutType = layoutType;
                table.insert(res,dumpReward);
            elseif rewardType == "customFunc" then
                -- local funcInfo = g_blocksLogicCfg:GetBoomLevelFuncCfgByKey(g[1]);
                dumpReward = {
                    Name = Reward.Name,
                    Desc = Reward.Desc,
                    Icon = Reward.Icon,
                };
                dumpReward.rewardType = rewardType;
                dumpReward.layoutType = layoutType;
                table.insert(res,dumpReward);
            end
            if not dumpReward then
                dumpReward = {};
                dumpReward.extra = g_LRPDescManager:GetRPTextFormated("NONE_TITLE_REWARDS");
                rewardType = "none";
                dumpReward.rewardType = rewardType;
                dumpReward.layoutType = layoutType;
                table.insert(res,dumpReward);
            end
            
        end
    else
        local dumpReward = {};
        dumpReward.rewardType = "none";
        dumpReward.extra = g_LRPDescManager:GetRPTextFormated("NONE_TITLE_REWARDS");
        table.insert(res,dumpReward);
    end
    return res;
end
-- 设置是否禁用快捷键
function LCommonProvider:S2UI_SetDisableKeyBoard(bState)
    LOG_I("Set keyboard enable to ", not bState);
    g_LHBUI:Emit(g_LHBUIEvents.S2UI_SetDisableKeyBoard, bState);
end
--- 注册到HBUIProvider
if g_LHBUIProvider then
    g_LHBUIProvider:AddProvider(LCommonProvider);
else
    LOG_E("g_LHBUIProvider is not define.");
end