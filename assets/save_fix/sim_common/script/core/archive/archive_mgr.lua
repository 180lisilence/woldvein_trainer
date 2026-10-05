---
--- Generated manually.
--- Created by liaogaocan.
--- DateTime: 2020-11-9 15:38:14
--- Desc: The logic of saving and loading.
---

---@class LArchive
LOG_I("[PROBE-LOAD] sim_common/script/core/archive/archive_mgr.lua loaded");
local LArchive = ImportScript("script/core/archive/archive.lua").LArchive;
---@class LVersion
local LVersion = ImportScript("script/core/version/version.lua").LVersion;

---@class LArchiveMgr
LArchiveMgr = LArchiveMgr or class("LArchiveMgr");

function LArchiveMgr:ctor()
    self.m_tbArchiveList = {};
    self.m_tbArchiveDic = {};
    --self.m_tbArchiveListWithBackUp = {};

    self.m_szUserFolder = "";
    self.m_szArchiveFolder = "";
    self.TRANSLATE_V_TAG = "TRANSLATE_V";
end

function LArchiveMgr:dtor()
    --
end

function LArchiveMgr:Init()
    self:updateArchiveFolderPath();
    return self:RefreshArchiveList();
end

function LArchiveMgr:UnInit()
    --
end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
function LArchiveMgr:RefreshArchiveListFromMeta(tbRetArchiveDic)
    local tbFileNameList = FS.ListDir(self:GetArchiveFolderPath());
    -- filter for meta file.
    local tbArNameList = {};
    for _, szFileName in ipairs(tbFileNameList) do
        if nil ~= string.match(szFileName, "%.meta$") then
            table.insert(tbArNameList, szFileName);
        end
    end
    local nCurrentMajorVersion = g_SerializationMgr:GetCurrentVersion():GetMajorVersion();
    for _, szArName in ipairs(tbArNameList) do
        local file = FS.Open(self:GetFilePathFromArchiveFolder(szArName), "r");
        if nil ~= file then
            local szSaveStr = file:Read();
            file:Close();
            if type(szSaveStr) == "string" then
                local bOK, tbData = xpcall(function ()
                    return cjson.decode(szSaveStr);
                end, Traceback);
                if true == bOK and type(tbData) == "table" then
                    local ar = LArchive:new();
                    ar:FromData(tbData);
                    local szStorage = ar:GetStorageFileName();
                    local arUUID = ar:GetUUID();
                    local bStorageExist = FS.Path.Exists(self:GetFilePathFromArchiveFolder(szStorage));
                    if bStorageExist then
                        if false == g_SerializationMgr:IsVersionFilterEnable() or ar:GetVersion():GetMajorVersion() == nCurrentMajorVersion then
                            self.m_tbArchiveDic[arUUID] = ar;
                            tbRetArchiveDic[arUUID] = ar;
                        end
                    else
                        LOG_E(("[LArchiveMgr][RefreshArchiveListFromMeta] Meta without storage! uuid=%s, storage=%s"):format(arUUID, szStorage));
                    end
                end
            end
        end
    end
end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
function LArchiveMgr:RefreshArchiveListFromBOH(tbRetArchiveDic)
    local tbFileNameList = FS.ListDir(self:GetArchiveFolderPath());
    -- filter for boh file.
    local tbArNameList = {};
    for _, szFileName in ipairs(tbFileNameList) do
        if nil ~= string.match(szFileName, "%.boh$") then
            local strFileName = string.replace(szFileName, ".boh", "");
            table.insert(tbArNameList, strFileName);
        end
    end
    local nCurrentMajorVersion = g_SerializationMgr:GetCurrentVersion():GetMajorVersion();
    for _, szArName in ipairs(tbArNameList) do
        local strMetaPath = string.format("%s.meta", szArName);
        local bGot, szSaveStr = g_Storage:RequestFileByPathFromBOH(szArName, strMetaPath);
        if bGot and type(szSaveStr) == "string" then
            local bOK, tbData = xpcall(function ()
                return cjson.decode(szSaveStr);
            end, Traceback);
            if true == bOK and type(tbData) == "table" then
                local ar = LArchive:new();
                ar:FromData(tbData);
                local arUUID = ar:GetUUID();
                bGot, szSaveStr = g_Storage:RequestFileByPathFromBOH(szArName, szArName);
                local bStorageExist = bGot and not string.isempty(szSaveStr);
                if bStorageExist then
                    if false == g_SerializationMgr:IsVersionFilterEnable() or ar:GetVersion():GetMajorVersion() == nCurrentMajorVersion then
                        self.m_tbArchiveDic[arUUID] = ar;
                        tbRetArchiveDic[arUUID] = ar;
                    end
                else
                    LOG_E(("[LArchiveMgr][RefreshArchiveListFromBOH] Meta without storage! uuid=%s, storage=%s"):format(arUUID, szArName));
                end
            end
        end
    end
end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
function LArchiveMgr:RefreshArchiveIndex(tbRetArchiveDic)
    local idxFile = nil;
    local szIdxFile = self:GetFilePathFromArchiveFolder("index.json");
    if self:IsUserFolderNameValid() and true == FS.Path.Exists(szIdxFile) then
        idxFile = FS.Open(szIdxFile, "r");
    end
    local tbArIdx = nil;
    if nil ~= idxFile then
        local szJson = idxFile:Read();
        if type(szJson) == "string" then
            tbArIdx = cjson.decode(szJson);
            if type(tbArIdx) == "table" then
                for nIdx, arUUID in ipairs(tbArIdx) do
                    local ar = self.m_tbArchiveDic[arUUID];
                    if nil ~= ar then
                        table.insert(self.m_tbArchiveList, ar);
                        tbRetArchiveDic[arUUID] = nil;
                    end
                end
            end
        end
        idxFile:Close();
    end
end

function LArchiveMgr:RefreshArchiveList()
    self.m_tbArchiveList = {};
    self.m_tbArchiveDic = {};

    local bResult = false;
    local fn = function()
        local tbArchiveDic = {};
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
        self:RefreshArchiveListFromMeta(tbArchiveDic);
        self:RefreshArchiveListFromBOH(tbArchiveDic);
        self:RefreshArchiveIndex(tbArchiveDic);
        
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
        for arUUID, ar in pairs(tbArchiveDic) do
            table.insert(self.m_tbArchiveList, ar);
        end
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
        if self:IsUserFolderNameValid() then
            self:updateArchiveIndexFile();
        end
        self:TranslateAllHashStorageToPack();
        bResult = true;
    end
    xpcall(fn, Traceback);
    return bResult;
end

function LArchiveMgr:updateArchiveIndexFile()
    local tbArIdxNew = {};
    for nIdx, ar in ipairs(self.m_tbArchiveList) do
        table.insert(tbArIdxNew, ar:GetUUID());
    end

    local idxFileNew = FS.Open(self:GetFilePathFromArchiveFolder("index.json"), "w+");
    if nil ~= idxFileNew then
        local szJsonSave = cjson.encode(tbArIdxNew);
        if type(szJsonSave) == "string" then
            idxFileNew:Write(szJsonSave);
        end
        idxFileNew:Close();

        LOG_I("[LArchiveMgr:updateArchiveIndexFile]", szJsonSave);
    end
end

function LArchiveMgr:GetUserFolderName()
    return self.m_szUserFolder;
end

function LArchiveMgr:IsUserFolderNameValid()
    local szUserFolderName = self:GetUserFolderName();
    return "string" == type(szUserFolderName) and "" ~= szUserFolderName;
end

function LArchiveMgr:SetUserFolderName(szFolder)
    self.m_szUserFolder = szFolder;
    self:updateArchiveFolderPath();
    g_Storage:SetStorageFolderPath(self:GetArchiveFolderPath());
end

function LArchiveMgr:updateArchiveFolderPath()
    self.m_szArchiveFolder = ("%s/storage/%s"):format(FS.GetCwd(), self.m_szUserFolder);
    LOG_I(("[LArchiveMgr:updateArchiveFolderPath] self.m_szArchiveFolder = %s"):format(self.m_szArchiveFolder));
end

function LArchiveMgr:GetArchiveFolderPath()
    return self.m_szArchiveFolder;
end

function LArchiveMgr:GetFilePathFromArchiveFolder(szFileName)
    return ("%s/%s"):format(self.m_szArchiveFolder, szFileName);
end

function LArchiveMgr:GetFilePathFromUserdataFolder(szFileName)
    local userdataFolder = self:GetFilePathFromArchiveFolder("userdata");
    return ("%s/%s"):format(userdataFolder, szFileName);
end

function LArchiveMgr:_findArchive(uuid)
    if nil == uuid then
        return nil, nil;
    end
    for idx, value in ipairs(self.m_tbArchiveList) do
        if uuid == value:GetUUID() then
            return value, idx;
        end
    end
end

function LArchiveMgr:GetArchive(uuid)
    return self.m_tbArchiveDic[uuid];
end

function LArchiveMgr:GetArchiveByName(szName)
    for nIdx, ar in ipairs(self.m_tbArchiveList) do
        if nil ~= ar and szName == ar:GetName() then
            return ar, nIdx;
        end
    end
    return nil, nil;
end

function LArchiveMgr:GetArchiveByType(nArchiveType)
    for nIdx, ar in ipairs(self.m_tbArchiveList) do
        if nil ~= ar and nArchiveType == ar:GetArchiveType() then
            return ar, nIdx;
        end
    end
    return nil, nil;
end


function LArchiveMgr:_generateScreenShot(szFileName)
    return true;
end

function LArchiveMgr:SaveDataToMetaFile(uuid, tbArData)
    return self:_saveDataToMetaFile(uuid, tbArData);
end

function LArchiveMgr:_saveDataToMetaFile(uuid, tbArData)
    if nil == uuid or nil == tbArData then
        return false, "invalid uuir or archive data";
    end
    util.printTB(tbArData);

    local bSucc, szContent = xpcall(function ()
        return cjson.encode(tbArData);
    end, Traceback);
    if not bSucc or string.isempty(szContent) then
        local errmsg = string.format("cjson encode failed for uuid %s", uuid);
        LOG_E(errmsg);
        return false, errmsg;
    end
    LOG_I(szContent);

    local strAbsPath = self:GetFilePathFromArchiveFolder(uuid..".meta");
    local strTmpPath = self:GetFilePathFromArchiveFolder(uuid..".meta.~tmp");
    FS.Copy(strAbsPath, strTmpPath);

    local metaFile = FS.Open(strAbsPath, "w+");
    if nil == metaFile then
        LOG_E("LArchiveMgr:_saveDataToMetaFile() Open file failed!");
        FS.Copy(strTmpPath, strAbsPath);
        FS.RemoveFile(strTmpPath);
        local errno, errmsg = FS.GetLastError();
        return false, errmsg;
    end
    if false == metaFile:Write(szContent) then
        LOG_E("LArchiveMgr:_saveDataToMetaFile() Write file failed!");
        FS.Copy(strTmpPath, strAbsPath);
        FS.RemoveFile(strTmpPath);
        metaFile:Close();
        local errno, errmsg = FS.GetLastError();
        return false, errmsg;
    end

    metaFile:Close();
    return true, nil;
end

function LArchiveMgr:_saveMetaFile(uuid)
    if nil == uuid then
        return false;
    end

    local ar = self:GetArchive(uuid);
    if nil == ar then
        return false;
    end

    local tbData = ar:ToData();
    return self:_saveDataToMetaFile(uuid, tbData);
end

function LArchiveMgr:_saveDataToBOHMetaFile(uuid, tbArData)
    if nil == uuid or nil == tbArData then
        return false, "invalid uuir or archive data";
    end
    util.printTB(tbArData);

    local strRelPath = string.format("%s.meta", uuid);
    local bSucc, szContent = xpcall(function ()
        return cjson.encode(tbArData);
    end, Traceback);
    if not bSucc or string.isempty(szContent) then
        local errmsg = string.format("cjson encode failed for uuid %s", uuid);
        LOG_E(errmsg);
        return false, errmsg;
    end
    LOG_I(szContent);
    
    local bSaved = g_Storage:SaveFileByPathToBOH(uuid, strRelPath, szContent);
    local strError = nil;
    if not bSaved then
        bSaved, strError = g_Storage:SaveFileByPathToDisk(strRelPath, szContent);
    end
    if not bSaved then
        LOG_E(strError);
    end
    return bSaved, strError;
end

function LArchiveMgr:GetArchiveList()
    return self.m_tbArchiveList;
end

function LArchiveMgr:GetArchiveCount()
    return #self.m_tbArchiveList;
end

function LArchiveMgr:GetBackUpArchiveList()
    local backUpList = {};
    for nIdx, ar in ipairs(self.m_tbArchiveList) do
        local data = ar:GetArchiveBackUp();
        for _, data in ipairs(data) do
            table.insert(backUpList, data);
        end
    end
    return backUpList;
end

function LArchiveMgr:CreateArchive(szArName, tbLevelInfo, nArchiveType, szUUID, szMapUUID)
    nArchiveType = nArchiveType or setting_define.ArchiveType.NORMAL_SAVE;
    local ar = LArchive:new();
    local szName = szArName or "Untitled";
    local version = LVersion:new();
    version:FromData(g_SerializationMgr:GetCurrentVersion():ToData());
    if not szUUID or string.isempty(szUUID) then
        szUUID = util.GenerateUuid();
    end
    ar:SetVersion(version);
    ar:SetUUID(szUUID);
    ar:SetMapUUID(szMapUUID);
    ar:SetName(szName);
    ar:SetStorageFileName(szUUID);
    ar:SetScreenShotFileName(szUUID..".jpg");
    ar:SetArchiveType(nArchiveType);

    if nArchiveType == setting_define.ArchiveType.SUB_SAVE then
        ar:SetMainArchiveState(false);
    else
        ar:SetMainArchiveState(true);
    end

    table.insert(self.m_tbArchiveList, ar);
    self.m_tbArchiveDic[szUUID] = ar;
    
    local bOK, tbErrors = self:SaveArchive(szUUID, tbLevelInfo, nArchiveType);
    if false == bOK then
        LOG_E("LArchiveMgr:CreateArchive() Storage file save failed!");
        self:RemoveArchive(szUUID);
        return nil, tbErrors;
    end

    self:updateArchiveIndexFile();

    return szUUID, tbErrors;
end

function LArchiveMgr:CreateAndCopySaveArchiveBOH(szArName, szUUID, archiveData, nArchiveType)
    if g_Storage:ExistPackedBOH(archiveData.szUUID) then
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
        local ar = self:GetArchive(archiveData.szUUID);
        local bPackUserdata = ar:GetPlayMode() == g_Game.LGameDefine.PLAY_MOD.SANDBOX;
        local bPackMetadata = true;
        local bReleased = g_Storage:ReleasePackedStorage(archiveData.szUUID, bPackUserdata, bPackMetadata);
        if bReleased then
            FS.RemoveFile(self:GetFilePathFromArchiveFolder(self.TRANSLATE_V_TAG));
        end
        self:CreateAndCopySaveArchive(szArName, szUUID, archiveData, nArchiveType);
        g_Storage:PackHashStorage(szUUID, bPackUserdata, bPackMetadata);
        if bReleased then
            g_Storage:DeletePackedHashContent(archiveData.szUUID);
        end
    else 
        self:CreateAndCopySaveArchive(szArName, szUUID, archiveData, nArchiveType);
    end
end


function LArchiveMgr:CreateAndCopySaveArchive(szArName, szUUID, archiveData, nArchiveType)
    local ar = LArchive:new();
    local szName = szArName or "Untitled";
    local version = LVersion:new();
    version:FromData(g_SerializationMgr:GetCurrentVersion():ToData());
    if not szUUID or string.isempty(szUUID) then
        szUUID = util.GenerateUuid();
    end

    table.insert(self.m_tbArchiveList, ar);
    self.m_tbArchiveDic[szUUID] = ar;

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if false == self:CopySaveArchiveMetaInfo(szUUID, szName, archiveData, nArchiveType) then
        LOG_E("LArchiveMgr:CreateAndCopySaveArchiveMetaInfo() Storage file save failed!");
        self:RemoveArchive(szUUID);
        return nil;
    end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local oldSerializationPath = self:GetFilePathFromArchiveFolder(archiveData.szUUID);
    local bFileExist = FS.Path.Exists(oldSerializationPath);
    if bFileExist then
        local newSerializationPath = self:GetFilePathFromArchiveFolder(szUUID);
        FS.Copy(oldSerializationPath,newSerializationPath);
    else
        LOG_E(string.format("LArchiveMgr:CreateAndCopySaveArchiveMetaInfo oldSerializationPath %s not exist!", oldSerializationPath));
        self:RemoveArchive(szUUID);
        return nil;
    end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local strUserFolderName = g_LXGGameplay:GetUserFolderName();
    local sourceSzUUID = archiveData.szUUID;
    local targetSzUUID = szUUID;
    local oldUserDataPath = string.format(game_world_define.USER_STORE_FOLDER, strUserFolderName, sourceSzUUID);
    local bOldUserDataExist = FS.Path.Exists(oldUserDataPath);
    if bOldUserDataExist then
        FS.Walk(oldUserDataPath, function(current,dirs,files)
            for index, fileName in ipairs(files or {}) do
                local newUserDataPath = "";
                local oldFilePath = current.."/"..fileName;

                local matchStr = string.replace(sourceSzUUID, "-", "%-");
                newUserDataPath = string.replace(current, matchStr, targetSzUUID);

                if not FS.Path.Exists(newUserDataPath) then
                    FS.MakeDir(newUserDataPath);
                end

                local newFilePath = newUserDataPath.."/"..fileName;
                FS.Copy(oldFilePath, newFilePath);
            end
        end);
    end 

    LOG_FOR_PUBLISH_MSG(string.format(
        "[LArchiveMgr][CreateAndCopySaveArchive] Create archive copy %s name %s from archive %s type %d ok.",
        szUUID, szArName, sourceSzUUID, nArchiveType
    ));

-- [PATCH-20260907 v3] fix: CreateAndCopySaveArchive missing TRANSLATE_V -> new save stuck at 3/4
-- Root cause: CreateAndCopySaveArchive copies from template save (which lacks TRANSLATE_V),
-- and does NOT call SaveArchive, so the v2 patch in SaveArchive never runs.
-- Fix: write TRANSLATE_V unconditionally after copy, with pcall protection.
    LOG_FOR_PUBLISH_MSG("[PATCH-20260907 v3] CreateAndCopySaveArchive writing TRANSLATE_V (unconditional)");
    do
        local strPatchVer = "9.2.1";
        local bOk, strErr = pcall(function()
            g_Storage:SaveFileByPathToBOH(szUUID, self.TRANSLATE_V_TAG, strPatchVer);
        end);
        if not bOk then
            LOG_FOR_PUBLISH_MSG("[PATCH-20260907 v3] CreateAndCopySaveArchive SaveFileByPathToBOH failed: " .. tostring(strErr));
        end
    end

    self:updateArchiveIndexFile();

    return szUUID;
end


function LArchiveMgr:RemoveArchive(uuid)
    local ar, idx = self:_findArchive(uuid);
    if nil == ar or nil == idx then
        return false;
    end
    self.m_tbArchiveDic[ar:GetUUID()] = nil;
    table.remove(self.m_tbArchiveList, idx);

    g_Storage:DeletePackedHashContent(uuid);
    g_Storage:DeletePackedBOH(uuid);

    LOG_FOR_PUBLISH_MSG(string.format("[LArchiveMgr][RemoveArchive] Remove %s result: %s", uuid, tostring(true)));
    self:updateArchiveIndexFile();
    return true;
end

function LArchiveMgr:SetArchiveName(uuid, szName)
    local ar = self:GetArchive(uuid);
    if nil == ar then
        return false;
    end
    
    if false == ar:SetName(szName) then
        return false;
    end

    local info = ar.m_tbLevelInfo;
    local tbLevelInfo = {
        playMode = info.playMode,
        year     = info.year,
        month    = info.month,
        day      = info.day,
        season   = info.season,
        inputName = szName,
    } 
    ar:SetLevelInfo(tbLevelInfo);

    self.m_tbArchiveDic[uuid] = ar;
    self:updateArchiveIndexFile();

    return self:_saveMetaFile(uuid);
end

function LArchiveMgr:LoadArchive(uuid)
    local szStorage = nil;
    if nil == uuid then
        return self:LoadEmptyArchive();
    else
        local ar = self:GetArchive(uuid);
        if nil == ar then
            LOG_E("LArchiveMgr:LoadArchive() faild! uuid =", uuid);
            return false;
        end
        szStorage = ar:GetStorageFileName();
    end

    -- nil storage will lead to load a default storage.
    return self:LoadStorage(szStorage);
end

---
--- Save archive
--- @param uuid string
--- @param tbLevelInfo table
--- @param nArchiveType number
--- @return boolean
--- @return string[]
--- 
function LArchiveMgr:SaveArchive(uuid, tbLevelInfo, nArchiveType)
    LOG_I("[PROBE-FUNC] SaveArchive entry");
    nArchiveType = nArchiveType or setting_define.ArchiveType.NORMAL_SAVE;
    local ar = self:GetArchive(uuid);
    if nil == ar then
        LOG_E("LArchiveMgr:SaveArchive() Archive is invalid! uuid =", uuid);
        return false, {"invalid archive uuid when save it."};
    end

    local version = LVersion:new();
    version:FromData(g_SerializationMgr:GetCurrentVersion():ToData());

    ar:SetVersion(version);
    ar:SetLastModifyTime(os.time());
    ar:SetMapPath(g_SceneManager:GetCurScenePath());
    ar:SetSceneId(g_Game:GetCurSceneCfgId());
    ar:SetLevelInfo(tbLevelInfo);
    ar:SetArchiveType(nArchiveType);
    ar:SetName(tbLevelInfo.inputName);

    local bSaved, tbErrors = self:SaveStorage(ar:GetStorageFileName());
    if false == bSaved then
        LOG_E("LArchiveMgr:SaveArchive() Save storage failed! uuid =", uuid);
        return false, tbErrors;
    end

    local bMetaSaved, strErrors = self:_saveDataToBOHMetaFile(uuid, ar:ToData());
    if false == bMetaSaved then
        LOG_E("LArchiveMgr:SaveArchive() Meta file save failed! uuid =", uuid);
        return false, {strErrors};
    end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local bPackUserdata = ar:GetPlayMode() == g_Game.LGameDefine.PLAY_MOD.SANDBOX;
    local bPackMetadata = false;
    local bPacked = g_Storage:PackHashStorage(uuid, bPackUserdata, bPackMetadata);

    -- [PATCH-20260907] fix: create save missing TRANSLATE_V -> stuck at 3/4 (v2)
    -- Root cause: old patch used 'if bPacked then', but new empty save PackHashStorage returns false
    -- Fix: write unconditionally + pcall protection
    LOG_FOR_PUBLISH_MSG("[PATCH-20260907] AM: SaveArchive writing TRANSLATE_V (unconditional)");
    do
        local patchVer = ar:GetVersion();
        local strPatchVer = "9.2.1";
        if patchVer and patchVer.GetVersionString then
            local strVer = patchVer:GetVersionString();
            if strVer and string.len(strVer) > 0 then
                strPatchVer = strVer;
            end
        end
        local bOk, strErr = pcall(function()
            g_Storage:SaveFileByPathToBOH(uuid, self.TRANSLATE_V_TAG, strPatchVer);
        end);
        if not bOk then
            LOG_FOR_PUBLISH_MSG("[PATCH-20260907] SaveFileByPathToBOH failed: " .. tostring(strErr));
        end
    end
    LOG_FOR_PUBLISH_MSG("[LArchiveMgr] PackHashStorage:", bPacked);

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if nArchiveType == setting_define.ArchiveType.NORMAL_SAVE then
        self:CopyArchiveFileToBackup(uuid);
    end

    return true, {};
end

function LArchiveMgr:CopySaveArchiveMetaInfo(szUUID,szName,archiveData, nArchiveType)
    local ar = self:GetArchive(szUUID);
    if nil == ar then
        LOG_E("LArchiveMgr:SaveArchive() Archive is invalid! uuid =", szUUID);
        return false;
    end

    local version = LVersion:new();
    version:FromData(g_SerializationMgr:GetCurrentVersion():ToData());

    ar:FromData(archiveData);
    ar:SetVersion(version);
    ar:SetUUID(szUUID);
    ar:SetName(szName);
    ar:SetStorageFileName(szUUID);
    ar:SetScreenShotFileName(szUUID..".jpg");
    ar:SetLastModifyTime(os.time());
    ar:SetArchiveType(nArchiveType);

    local tbLevelInfo = ar:GetLevelInfo();
    tbLevelInfo.inputName = szName;

    if false == self:_saveDataToMetaFile(szUUID, ar:ToData()) then
        LOG_E("LArchiveMgr:SaveArchive() Meta file save failed! uuid =", szUUID);
        return false;
    end

    return true;
end

function LArchiveMgr:LoadEmptyArchive()
    g_Storage:Clear();
    return true;
end

function LArchiveMgr:LoadStorage(szStorage)
    local ar = self:GetArchive(szStorage);
    local bPackUserdata = ar:GetPlayMode() == g_Game.LGameDefine.PLAY_MOD.SANDBOX;
    local bPackMetadata = false;
    local bRelease = g_Storage:ReleasePackedStorage(szStorage, bPackUserdata, bPackMetadata);
    LOG_I("**********************[LArchiveMgr:LoadStorage] g_Storage:ReleasePackedStorage:", bRelease, szStorage);

    if bRelease then
        FS.RemoveFile(self:GetFilePathFromArchiveFolder(self.TRANSLATE_V_TAG));
    end
    
    local bRetCode = g_Storage:Load(szStorage);
    LOG_I("**********************[LArchiveMgr:LoadStorage] g_Storage:Load ret:", bRetCode, szStorage);
    if not bRetCode then
        return false;
    end

    LOG_I(string.format("[LArchiveMgr:LoadStorage] Unserialize begin ==========>>>>>> %s", szStorage));
    bRetCode = g_SerializationMgr:Unserialize();
    LOG_I(string.format("[LArchiveMgr:LoadStorage] Unserialize end ==========<<<<<< %s", szStorage));

    -- clear all data after load
    g_Storage:Clear();

    if not bRelease then
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
        bPackMetadata = true;
        g_Storage:DeletePackedBOH(szStorage);
        local bPacked = g_Storage:PackHashStorage(szStorage, bPackUserdata, bPackMetadata);
        LOG_FOR_PUBLISH_MSG(string.format("[LArchiveMgr][LoadStorage] Release failed then repack it result is: %s", tostring(bPacked)));
    end
    return bRetCode;
end

--- 
--- Save
--- @param szStorage string
--- @return boolean
--- @return string[]
---
function LArchiveMgr:SaveStorage(szStorage)
    LOG_I(string.format("[LArchiveMgr:SaveStorage] Serialize begin ==========>>>>>> %s", szStorage));
    local tbErrors = g_SerializationMgr:Serialize();
    LOG_I(string.format("[LArchiveMgr:SaveStorage] Serialize end ==========<<<<<< %s", szStorage));

    local bRetCode, strErrorMsg = g_Storage:Save(szStorage);
    LOG_I("**********************[LArchiveMgr:SaveStorage] g_Storage:Save ret:", bRetCode);
    table.insert(tbErrors, strErrorMsg);
    return bRetCode, tbErrors;
end

function LArchiveMgr:ModifyArchiveVersionOnly(uuid)
    if "string" ~= type(uuid) or "" == uuid then
        LOG_E("Invalid ar uuid =", tostring(uuid));
        return false;
    end

    local bRet = false;
    local currentVersion = g_SerializationMgr:GetCurrentVersion();

    repeat
        if true ~= g_Storage:Load(uuid) then
            LOG_E("[LArchiveMgr:ModifyArchiveVersionOnly] Failed to load storage!", uuid);
            break;
        end

        local tbArData = g_Storage:GetTable(storage_define.root_key.Serialization);
        if nil == tbArData or nil == tbArData.tbVersionInfo then
            LOG_E("[LArchiveMgr:ModifyArchiveVersionOnly] Bad storage!", uuid);
            break;
        end

        tbArData.tbVersionInfo = currentVersion:ToData();
        if true ~= g_Storage:Save(uuid) then
            LOG_E("[LArchiveMgr:ModifyArchiveVersionOnly] Failed to save storage!", uuid);
        end
        g_Storage:Clear();

        ---@type LArchive
        local ar = self:GetArchive(uuid);
        if nil == ar then
            LOG_E("[LArchiveMgr:ModifyArchiveVersionOnly] No mata data!", uuid);
            break;
        end
        ar:SetVersion(currentVersion);
        if true ~= self:_saveDataToMetaFile(uuid, ar:ToData()) then
            LOG_E("[LArchiveMgr:ModifyArchiveVersionOnly] Failed to save meta file!", uuid);
        end

        LOG_I("[LArchiveMgr:ModifyArchiveVersionOnly] Modify version succ!", uuid);
        bRet = true;
    until true;

    g_Storage:Clear();
    return bRet;
end

function LArchiveMgr:ModifyAllArchiveVersionOnly()
    LOG_I("[LArchiveMgr:ModifyAllArchiveVersionOnly] >>>>>>>>>>>>>>>>>>>>>>>>>>>>>> begin");

    local tbArList = self:GetArchiveList();
    for _, ar in ipairs(tbArList) do
        self:ModifyArchiveVersionOnly(ar:GetUUID());
    end

    LOG_I("[LArchiveMgr:ModifyAllArchiveVersionOnly] <<<<<<<<<<<<<<<<<<<<<<<<<<<<<< end");
end

function LArchiveMgr:DumpArchiveToJsonFile(uuid)
    local ar = self:GetArchive(uuid);
    if nil == ar then
        LOG_E("LArchiveMgr:DumpArchiveToJsonFile() Archive is invalid! uuid =", uuid);
        return false;
    end

    local szStorage = ar:GetStorageFileName();
    local szStoragePath = g_Storage:GetStorageFilePath(szStorage);
    LOG_I("[LArchiveMgr:DumpArchiveToJsonFile] file: ", szStoragePath);

    local file = FS.Open(szStoragePath, "rb");
    if not file then
        LOG_E("[LArchiveMgr:DumpArchiveToJsonFile] File not found!");
        return false;
    end

    local szSaveStr = file:Read();
    file:Close();
    if type(szSaveStr) ~= "string" then
        LOG_E("[LArchiveMgr:DumpArchiveToJsonFile] Failed to read file!");
        return false;
    end

    local bOK, strBalaBala = util.balabalabala(szSaveStr);
    if false == bOK then
        LOG_E("[LArchiveMgr:DumpArchiveToJsonFile] Failed to balabalabala!");
        return false;
    end

    local szJsonPath = g_Storage:GetStorageFilePath(szStorage..".json");
    local fileJson = FS.Open(szJsonPath, "w");
    if not fileJson then
        LOG_E("[LArchiveMgr:DumpArchiveToJsonFile] Open file failed. ");
        return false;
    end

    local bRet = fileJson:Write(strBalaBala);
    if not bRet then
        LOG_E("[LArchiveMgr:DumpArchiveToJsonFile] Write file failed. ");
    end
    fileJson:Close();

    LOG_I("[LArchiveMgr:DumpArchiveToJsonFile] Json file: ", szJsonPath);

    return bRet;
end

function LArchiveMgr:DumpArchiveFromTextModeToBinaryMode(uuid)
    local ar = self:GetArchive(uuid);
    if nil == ar then
        LOG_E("LArchiveMgr:DumpArchiveFromTextModeToBinaryMode() Archive is invalid! uuid =", uuid);
        return false;
    end

    local szStorage = ar:GetStorageFileName();
    local szStoragePath = g_Storage:GetStorageFilePath(szStorage);
    LOG_I("[LArchiveMgr:DumpArchiveFromTextModeToBinaryMode] file: ", szStoragePath);

    local file = FS.Open(szStoragePath, "r");
    if not file then
        LOG_E("[LArchiveMgr:DumpArchiveFromTextModeToBinaryMode] File not found!");
        return false;
    end

    local szSaveStr = file:Read();
    file:Close();
    if type(szSaveStr) ~= "string" then
        LOG_E("[LArchiveMgr:DumpArchiveFromTextModeToBinaryMode] Failed to read file!");
        return false;
    end

    local fileOutput = FS.Open(szStoragePath, "wb");
    if not fileOutput then
        LOG_E("[LArchiveMgr:DumpArchiveFromTextModeToBinaryMode] Open file failed. ");
        return false;
    end

    local bRet = fileOutput:Write(szSaveStr);
    if not bRet then
        LOG_E("[LArchiveMgr:DumpArchiveFromTextModeToBinaryMode] Write file failed. ");
    end
    fileOutput:Close();

    LOG_I("[LArchiveMgr:DumpArchiveFromTextModeToBinaryMode] Output file: ", szStoragePath);

    return bRet;
end

function LArchiveMgr:LoadArchiveTable(uuid)
    local ar = g_ArchiveMgr:GetArchive(uuid);
    if nil == ar then
        LOG_E("LArchiveMgr:DumpArchiveToJsonFile() Archive is invalid! uuid =", ar:GetUUID());
        return false;
    end

    local szStorage = ar:GetStorageFileName();
    local szStoragePath = g_Storage:GetStorageFilePath(szStorage);
    LOG_I("[LArchiveMgr:DumpArchiveToJsonFile] file: ", szStoragePath);

    local file = FS.Open(szStoragePath, "rb");
    if not file then
        LOG_E("[LArchiveMgr:DumpArchiveToJsonFile] File not found!");
        return false;
    end

    local szSaveStr = file:Read();
    file:Close();
    if type(szSaveStr) ~= "string" then
        LOG_E("[LArchiveMgr:DumpArchiveToJsonFile] Failed to read file!");
        return false;
    end

    local bOK, strBalaBala = util.balabalabala(szSaveStr);
    if false == bOK then
        LOG_E("[LArchiveMgr:DumpArchiveToJsonFile] Failed to balabalabala!");
        return false;
    end
    return JSON.Loads(strBalaBala);
end

function LArchiveMgr:SaveArchiveTable(uuid, tbSerializaition)
    local ar = g_ArchiveMgr:GetArchive(uuid);
    if nil == ar then
        LOG_E("LArchiveMgr:DumpArchiveToJsonFile() Archive is invalid! uuid =", ar:GetUUID());
        return false;
    end

    local szStorage = ar:GetStorageFileName();
    local szStoragePath = g_Storage:GetStorageFilePath(szStorage);
    LOG_I("[LArchiveMgr:DumpArchiveToJsonFile] file: ", szStoragePath);

    local file = FS.Open(szStoragePath, "wb");
    print("[LStorage:Save] file: ", szStoragePath, file);
    if not file then
        LOG_E("[LStorage:Save] Open file failed. ");
        return false; 
    end
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    g_App:AddCustomFileToDumper(szStoragePath);
    g_App:AddCustomFileToDumper(string.format("%s.meta", szStoragePath));
    
    -- try save data to local file
    local strSaveStr = cjson.encode(tbSerializaition);
    local bOK1, strAbaaba = util.abaabaabaaba(strSaveStr);
    if false == bOK1 then
        LOG_E("Failed to abaabaabaaba!");
        file:Close();
        return false;
    end

    if not file:Write(strAbaaba) then
        LOG_E("[LStorage:Save] Write file failed. ");
    end
    file:Close();
end


function LArchiveMgr:DumpArchiveCampBaseResources(uuid)
    local tbStorage = self:LoadArchiveTable(uuid).Serialization;
    local tbCollectorKeyList = tbStorage.tbCollectorKeyList;
    local tbObjInfos = tbStorage.tbObjInfos;
    
    local tbBaseResources = {};
    local tbPostData = {};
    local tbResources = {
        block_define.SOURCE.MONEY,
        block_define.SOURCE.MINERAL,
        block_define.SOURCE.WOOD,
        block_define.SOURCE.CLOTH,
        block_define.SOURCE.FOOD,
        block_define.SOURCE.WATER,
        block_define.SOURCE.SALT,
        block_define.SOURCE.LIQUOR,
        block_define.SOURCE.QUINTESSENCE,
    };
    for idx, tbObj in ipairs(tbObjInfos) do
        local szKey = tbCollectorKeyList[tbObj.CID];
        if szKey == "LBlockSerializationCollector" then
            local blockBaseData = tbObj.tbData.tbBaseData;
            if blockBaseData.nId == block_define.CAMP_ID then
                for i, resourceId in ipairs(tbResources) do
                    if blockBaseData.m_tbSource[resourceId] then
                        tbBaseResources[resourceId] = blockBaseData.m_tbSource[resourceId] or 0;
                        LOG_I(string.format("resource %d is %d",resourceId,blockBaseData.m_tbSource[resourceId]));
                    end
                end
            end
        end
        if szKey == "PostManager" then
            tbPostData = {
                m_records = tbObj.tbData.m_records;
                thy_records = tbObj.tbData.thy_records,
                m_unstorage = tbObj.tbData.m_unstorage,
            }
        end
    end

    return tbBaseResources, tbPostData;
end

function LArchiveMgr:SyncronizeArchiveCampBaseResources(sourceUUID, targetUUID)
    local tbSourceBaseResourecs, tbPostData = self:DumpArchiveCampBaseResources(sourceUUID);

    local tbTargetStorage = self:LoadArchiveTable(targetUUID);
    local tbSerialization = tbTargetStorage.Serialization;
    local tbCollectorKeyList = tbSerialization.tbCollectorKeyList;
    local tbObjInfos = tbSerialization.tbObjInfos;
    local tbResources = {
        block_define.SOURCE.MONEY,
        block_define.SOURCE.MINERAL,
        block_define.SOURCE.WOOD,
        block_define.SOURCE.CLOTH,
        block_define.SOURCE.FOOD,
        block_define.SOURCE.WATER,
        block_define.SOURCE.SALT,
        block_define.SOURCE.LIQUOR,
        block_define.SOURCE.QUINTESSENCE,
    };

    for idx, tbObj in ipairs(tbObjInfos) do
        local szKey = tbCollectorKeyList[tbObj.CID];
        if szKey == "LBlockSerializationCollector" then
            local blockBaseData = tbObj.tbData.tbBaseData;
            if blockBaseData.nId == block_define.CAMP_ID then
                for i, resourceId in ipairs(tbResources) do
                    blockBaseData.m_tbSource[resourceId] = tbSourceBaseResourecs[resourceId] or 0;
                end
                break;
            end
        end
        if szKey == "PostManager" then
            tbObj.tbData.m_records = tbPostData.m_records;
            tbObj.tbData.thy_records = tbPostData.thy_records;
            tbObj.tbData.m_unstorage = tbPostData.m_unstorage;
        end
    end

    -- for _, key in ipairs(tbCollectorKeyList) do
    --     if key == "PostManager" then
    --         local blockBaseData = tbObj
    --     end
    -- end

    self:SaveArchiveTable(targetUUID, tbTargetStorage);
end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
--- @param uuid string
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
function LArchiveMgr:GetArchiveDataRef(uuid)
    local tbArchive = nil;
    if "string" ~= type(uuid) or "" == uuid then
        LOG_E("Invalid ar uuid =", tostring(uuid));
        return tbArchive, nil;
    end
    local bRet = false;
    repeat
        if true ~= g_Storage:Load(uuid) then
            LOG_E("[LArchiveMgr:ModifyArchiveVersionOnly] Failed to load storage!", uuid);
            break;
        end

        local tbArData = g_Storage:GetTable(storage_define.root_key.Serialization);
        if nil == tbArData or nil == tbArData.tbVersionInfo then
            LOG_E("[LArchiveMgr:ModifyArchiveVersionOnly] Bad storage!", uuid);
            break;
        end
        tbArchive = tbArData;
        bRet = true;
    until true;
    local function saveandclean()
        if tbArchive and g_Storage:Save(uuid) then
            LOG_I(string.format("Save %s succeed.", uuid));
        else
            LOG_W(string.format("Save %s failed.", uuid));
        end
        g_Storage:Clear();
    end
    return tbArchive, saveandclean;
end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
function LArchiveMgr:CopyArchiveFileToBackup(uuid)
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if not (g_LXGAgentManager.LXGAgentDefine.XGSDKCheck or g_GameWorld.bGMStorageBackup) then
        return;
    end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local ar = self:GetArchive(uuid);
    if not ar then
        LOG_E("[LArchiveMgr:CopyArchiveFileToBackup] Target archive not exist!!!", uuid);
        return;
    end

    LOG_I("[LArchiveMgr:CopyArchiveFileToBackup] Preparing copy archive info", uuid);
    local bSuccessCopy = self:CopyArchiveFileToBackup_BOH(uuid, ar);
    if bSuccessCopy ~= true then
        self:CopyArchiveFileToBackup_Meta(uuid, ar);
    end
end

function LArchiveMgr:CopyArchiveFileToBackup_BOH(uuid, ar)
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local strBohName = uuid..".boh";
    local strBohData = self:GetFilePathFromArchiveFolder(strBohName);
    local bBohExist = FS.Path.Exists(strBohData);
    if not bBohExist then
        LOG_I("[LArchiveMgr:CopyArchiveFileToBackup_BOH] BOH file not exist!!!", strBohData);
        return;
    end

    local curTime = os.time();
    local curDate = os.date("%Y_%m_%d", curTime);
    local curClock = os.date("%H_%M_%S", curTime);
    local backUpFile = "storageBackup";
    local datePath = string.format("%s/%s", backUpFile, curDate);
    local clockPath = string.format("%s/%s", datePath, curClock);

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if not FS.Path.Exists(backUpFile) then
        FS.MakeDirs(backUpFile);
    end

    if not FS.Path.Exists(datePath) then
        FS.MakeDirs(datePath);
    end

    if not FS.Path.Exists(clockPath) then
        FS.MakeDirs(clockPath);
    end

    local strNewBohFile = FS.Path.Join(clockPath, strBohName);
    FS.Copy(strBohData, strNewBohFile);
    
    local thy = ar:GetPlayMode() == g_Game.LGameDefine.PLAY_MOD.SANDBOX;
    local data = {
        uuid = uuid,
        curTime = curTime,
        curDate = curDate,
        curClock = curClock,
        backUp_Path = clockPath,
        isThy = thy,
    }
    ar:SetArchiveBackUp(data)


    LOG_I("[LArchiveMgr:CopyArchiveFileToBackup_BOH] Copy Normal archive success!!!");

    self:RefreshBackupList();

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if false == self:_saveDataToBOHMetaFile(uuid, ar:ToData()) then
        LOG_E("LArchiveMgr:CopyArchiveFileToBackup BOH file save failed! uuid =", uuid);
        return false;
    end
    return true;
end
function LArchiveMgr:CopyArchiveFileToBackup_Meta(uuid, ar)
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local strMetaName = uuid..".meta";
    local strMetaData = self:GetFilePathFromArchiveFolder(strMetaName);
    local strStorageName = ar:GetStorageFileName();
    local strStorageData = self:GetFilePathFromArchiveFolder(strStorageName);
    local bCopyUserData = ar:GetPlayMode() == g_Game.LGameDefine.PLAY_MOD.SANDBOX;

    local bMetaExist = FS.Path.Exists(strMetaData);
    if not bMetaExist then
        LOG_I("[LArchiveMgr:CopyArchiveFileToBackup] Meta file not exist!!!", strMetaData);
        return;
    end

    local bStorageExist = FS.Path.Exists(strStorageData);
    if not bStorageExist then
        LOG_I("[LArchiveMgr:CopyArchiveFileToBackup] Storage file not exist!!!", strStorageData);
        return;
    end

    if bCopyUserData then
        local strUserFolderName = g_LXGGameplay:GetUserFolderName();
        local userDataPath = string.format(game_world_define.USER_STORE_FOLDER, strUserFolderName, uuid);
        local bUserDataExist = FS.Path.Exists(userDataPath);

        if not bUserDataExist then
            LOG_I("[LArchiveMgr:CopyArchiveFileToBackup] userdata file not exist!!!", userDataPath);
            return;
        end
    end

    local curTime = os.time();
    local curDate = os.date("%Y_%m_%d", curTime);
    local curClock = os.date("%H_%M_%S", curTime);
    local backUpFile = "storageBackup";
    local datePath = string.format("%s/%s", backUpFile, curDate);
    local clockPath = string.format("%s/%s", datePath, curClock);

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if not FS.Path.Exists(backUpFile) then
        FS.MakeDirs(backUpFile);
    end

    if not FS.Path.Exists(datePath) then
        FS.MakeDirs(datePath);
    end

    if not FS.Path.Exists(clockPath) then
        FS.MakeDirs(clockPath);
    end

    local strNewMetaFile = FS.Path.Join(clockPath, strMetaName);
    FS.Copy(strMetaData, strNewMetaFile);

    local strNewStorageFile = FS.Path.Join(clockPath, strStorageName);
    FS.Copy(strStorageData, strNewStorageFile);

    if bCopyUserData then
        local strUserFolderName = g_LXGGameplay:GetUserFolderName();
        local userDataPath = string.format(game_world_define.USER_STORE_FOLDER, strUserFolderName, uuid);
        local newUserDataPath = string.format("%s/userdata", clockPath);

        if not FS.Path.Exists(newUserDataPath) then
            FS.MakeDirs(newUserDataPath);
        end
        newUserDataPath = string.format("%s/%s", newUserDataPath, uuid);
        if not FS.Path.Exists(newUserDataPath) then
            FS.MakeDirs(newUserDataPath);
        end

        FS.Walk(userDataPath, function(current,dirs,files)
            for index, fileName in ipairs(files or {}) do   
                local oldFilePath = current.."/"..fileName;
                local newPath = newUserDataPath .. string.sub(current,#userDataPath+1,#current);
                newPath = KFS.normalize(newPath);
                if not FS.Path.Exists(newPath) then
                    FS.MakeDirs(newPath);
                end
                local newFilePath = newPath .."/"..fileName;
                FS.Copy(oldFilePath, newFilePath);
            end
        end);
    end
    
    local thy = ar:GetPlayMode() == g_Game.LGameDefine.PLAY_MOD.SANDBOX;
    local data = {
        uuid = uuid,
        curTime = curTime,
        curDate = curDate,
        curClock = curClock,
        backUp_Path = clockPath,
        isThy = thy,
    }
    ar:SetArchiveBackUp(data)


    LOG_I("[LArchiveMgr:CopyArchiveFileToBackup] Copy Normal archive success!!!");

    self:RefreshBackupList();

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if false == self:_saveDataToMetaFile(uuid, ar:ToData()) then
        LOG_E("LArchiveMgr:CopyArchiveFileToBackup Meta file save failed! uuid =", uuid);
        return false;
    end
end

function LArchiveMgr:RefreshBackupList()
    local storagePath = "storageBackup";
    local tbFolderList = FS.ListDir(storagePath);
    table.sort(tbFolderList, function(a,b) 
        local tbDateA = string.split(a, "_");
        local tbDateB = string.split(b, "_");

        if tbDateA[1] ~= tbDateB[1] then
            local yearA = tonumber(tbDateA[1]);
            local yearB = tonumber(tbDateB[1]);
            if not yearA then
                return true;
            end
            if not yearB then
                return false;
            end
            return yearA < yearB;
        elseif tbDateA[2] ~= tbDateB[2] then
            local monthA = tonumber(tbDateA[2]);
            local monthB = tonumber(tbDateB[2]);
            if not monthA then
                return true;
            end
            if not monthB then
                return false;
            end
            return monthA < monthB;
        elseif tbDateA[3] ~= tbDateB[3] then
            local dayA = tonumber(tbDateA[3]);
            local dayB = tonumber(tbDateB[3]);
            if not dayA then
                return true;
            end
            if not dayB then
                return false;
            end
            return dayA < dayB;
        end
    end);
    LOG_I(string.format("Current backup folder number: %d", #tbFolderList));

    if tbFolderList and #tbFolderList > g_Game.LGameDefine.BACKUP_FOLDER_NUM then
        local deleteIndex = #tbFolderList - g_Game.LGameDefine.BACKUP_FOLDER_NUM;
        for index, folderName in ipairs(tbFolderList) do
            if index <= deleteIndex then
                LOG_W("[LArchiveMgr:RefreshBackupList] Delete backup archive", folderName);
                --FS.RemoveAll(FS.Path.Join(storagePath, folderName));
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
                local deleteList = {};
                local timePath = ("%s/%s"):format(storagePath, folderName);
                local timeList = FS.ListDir(timePath);
                for _, time in ipairs(timeList) do
                    local arPath = ("%s/%s"):format(timePath, time);
                    local arList = FS.ListDir(arPath);
                    for index, uuid in ipairs(arList) do
                        local deleteData = {
                            delete_uuid = uuid,
                            delete_date = folderName
                        }
                        table.insert(deleteList, deleteData);
                    end
                end
                FS.RemoveAll(FS.Path.Join(storagePath, folderName));
                for index, data in ipairs(deleteList) do
                    local arUUID = data.delete_uuid;
                    local ar = self:GetArchive(arUUID);
                    if ar then
                        ar:RemoveArchiveBackUp(arUUID, data.delete_date);
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
                        if false == self:_saveDataToMetaFile(arUUID, ar:ToData()) then
                            LOG_E("LArchiveMgr:RefreshBackupList() Meta file save failed! uuid =", arUUID);
                        end
                    end
                end
            else
                break;
            end
        end
    end
end


-- local data = {
--     uuid = uuid,
--     curTime = curTime,
--     curDate = curDate,
--     curClock = curClock,
--     backUp_Path = clockPath,
--     isThy = thy,
-- }
function LArchiveMgr:CoverBackUpToStorage(data)
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if not ar then
        LOG_E("[LArchiveMgr:CoverBackUpToStorage] Target archive not exist!!!", data.uuid);
        return;
    end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local bSuccessCover = self:CoverBackUpToStorage_BOH(data, ar);
    if bSuccessCover ~= true then
        self:CoverBackUpToStorage_Meta(data, ar);
    end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    g_LHBUIProvider:EmitTo("LCommonProvider", g_LHBUIEvents.UI2S_GetArchives);
end

function LArchiveMgr:CoverBackUpToStorage_Meta(data, ar)
    local strStorageName = ar:GetStorageFileName();
    local strMetaName = string.format("%s.meta", data.uuid);
    local strBohName = string.format("%s.boh", data.uuid);
    local bSuccess = false;
    local strErrMsg = nil;

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local strNewMetaFile = FS.Path.Join(data.backUp_Path, strMetaName);
    local strNewStorageFile = FS.Path.Join(data.backUp_Path, strStorageName);
    local strNewUserDataPath = string.format("%s/userdata/%s", data.backUp_Path, data.uuid);

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if not FS.Path.LocalExists(strNewMetaFile) then
        strErrMsg = string.format("[LArchiveMgr:CoverBackUpToStorage_Meta] Backup Meta File not exist, %s", strNewMetaFile)
        LOG_E(strErrMsg);
        return bSuccess, strErrMsg;
    end
    if not FS.Path.LocalExists(strNewStorageFile) then
        strErrMsg = string.format("[LArchiveMgr:CoverBackUpToStorage_Meta] Backup Storage File not exist, %s", strNewStorageFile)
        LOG_E(strErrMsg);
        return bSuccess, strErrMsg;
    end
    if data.isThy and not FS.Path.LocalExists(strNewUserDataPath) then
        strErrMsg = string.format("[LArchiveMgr:CoverBackUpToStorage_Meta] Backup Storage userdata not exist, %s", strNewUserDataPath)
        LOG_E(strErrMsg);
        return bSuccess, strErrMsg;
    end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    local strMetaData = self:GetFilePathFromArchiveFolder(strMetaName);
    local strBohData = self:GetFilePathFromArchiveFolder(strBohName);
    local strStorageData = self:GetFilePathFromArchiveFolder(strStorageName);
    local strUserData = self:GetFilePathFromUserdataFolder(strStorageName);
    local backUpData = ar:GetArchiveBackUp();
 
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    bSuccess = FS.SafeCopy(strNewMetaFile, strMetaData);
    if not bSuccess then
        strErrMsg = string.format("[LArchiveMgr:CoverBackUpToStorage_Meta] Copy backup meta failed, %s", strNewMetaFile);
        LOG_E(strErrMsg);
        return bSuccess, strErrMsg;
    end
    bSuccess = FS.SafeCopy(strNewStorageFile, strStorageData);
    if not bSuccess then
        strErrMsg = string.format("[LArchiveMgr:CoverBackUpToStorage_Meta] Copy backup storage failed, %s", strNewStorageFile);
        LOG_E(strErrMsg);
        return bSuccess, strErrMsg;
    end
    if data.isThy and not FS.Path.LocalExists(strNewUserDataPath) then
        strErrMsg = string.format("[LArchiveMgr:CoverBackUpToStorage_Meta] Copy backup userdata failed, %s", strNewUserDataPath);
        LOG_E(strErrMsg);
        bSuccess = false;
        return bSuccess, strErrMsg;
    end
    if not data.isThy then
        FS.RemoveAll(strUserData);
    else
        local strTmpUserDataPath = string.format("%s~udtmp", strUserData);
        FS.Move(strUserData, strTmpUserDataPath);
        FS.Walk(strNewUserDataPath, function(current, dirs, files)
            for index, fileName in ipairs(files) do   
                local oldFilePath = current.."/"..fileName;
                local newPath = strUserData .. string.sub(current,#strNewUserDataPath+1,#current);
                newPath = KFS.normalize(newPath);
                if not FS.Path.Exists(newPath) then
                    FS.MakeDirs(newPath);
                end
                local newFilePath = newPath .."/"..fileName;
                FS.Copy(oldFilePath, newFilePath);
            end
        end);
        FS.RemoveAll(strTmpUserDataPath);
    end
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    FS.RemoveFile(strBohData);
    bSuccess = true;
    LOG_FOR_PUBLISH_MSG("[LArchiveMgr:CoverBackUpToStorage_Meta] CoverBackUpToStorage copy bk data to storage succeed, wait refresh next.");
    
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    self:RefreshArchiveList();
    local new_ar = self:GetArchive(data.uuid);
    if new_ar then
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
        for _, backupDataItem in ipairs(backUpData) do
            new_ar:SetArchiveBackUp(backupDataItem);
        end    
        bSuccess, strErrMsg = self:_saveDataToBOHMetaFile(data.uuid, new_ar:ToData());
    end

    if not bSuccess then
        LOG_E(string.format("[LArchiveMgr:CoverBackUpToStorage_Meta] failed with message: %s", strErrMsg));
    else
        LOG_FOR_PUBLISH_MSG("[LArchiveMgr:CoverBackUpToStorage_Meta] all done.");
    end
    return bSuccess, strErrMsg;
end

function LArchiveMgr:CoverBackUpToStorage_BOH(data, ar)
    local bSuccess = false;
    local strErrMsg = nil;
    local strBohName = string.format("%s.boh", data.uuid);
    local strNewBohFile = FS.Path.Join(data.backUp_Path, strBohName);
    local strBohData = self:GetFilePathFromArchiveFolder(strBohName);
    local strUserData = self:GetFilePathFromUserdataFolder(data.uuid);

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    if not FS.Path.LocalExists(strNewBohFile) then
        strErrMsg = string.format("[LArchiveMgr:CoverBackUpToStorage_BOH] Backup BOH File not exist, %s", strNewBohFile)
        LOG_E(strErrMsg);
        return bSuccess, strErrMsg;
    end

-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    bSuccess = FS.SafeCopy(strNewBohFile, strBohData);
    if not bSuccess then
        strErrMsg = string.format("[LArchiveMgr:CoverBackUpToStorage_BOH] Copy BOH failed, %s", strNewBohFile);
        LOG_E(strErrMsg);
        return bSuccess, strErrMsg;
    end
    if FS.Path.LocalExists(strUserData) then
        FS.RemoveAll(strUserData);
    end
    LOG_FOR_PUBLISH_MSG("[LArchiveMgr:CoverBackUpToStorage_BOH] CoverBackUpToStorage copy bk data to storage succeed, wait refresh next.");
    
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
    self:RefreshArchiveList();
    local new_ar = self:GetArchive(data.uuid);
    local backUpData = ar:GetArchiveBackUp();
    if new_ar then
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
        for _, backupDataItem in ipairs(backUpData) do
            new_ar:SetArchiveBackUp(backupDataItem);
        end    
        bSuccess, strErrMsg = self:_saveDataToBOHMetaFile(data.uuid, new_ar:ToData());
    end

    if not bSuccess then
        LOG_E(string.format("[LArchiveMgr:CoverBackUpToStorage_BOH] failed with message: %s", strErrMsg));
    else
        LOG_FOR_PUBLISH_MSG("[LArchiveMgr:CoverBackUpToStorage_BOH] all done.");
    end
    return bSuccess, strErrMsg;
end

function LArchiveMgr:TranslateAllHashStorageToPack()
    local nBeginTime = os.clock();
    for nIdx, ar in ipairs(self.m_tbArchiveList) do
        local arUUID = ar:GetUUID();
        local strFolder = self:GetArchiveFolderPath();
        local bExistBOH = g_Storage:ExistPackedBOH(arUUID);
        if bExistBOH then
            local bReleased, strContent = g_Storage:RequestFileByPathFromBOH(arUUID, self.TRANSLATE_V_TAG);
            bExistBOH = bReleased and not string.isempty(strContent);
        end
        if not bExistBOH then
-- [PATCH cleanup] original comment lost in gbk->utf8 conversion; logic unchanged
            local strCurUserdataDir = string.format("%s/userdata/%s", strFolder, arUUID);
            local strBlendMapBakeDir = FS.Path.Join(strCurUserdataDir, "landscape", "blendmap_bc");
            local strHeightMapBakeDir = FS.Path.Join(strCurUserdataDir, "landscape", "heightmap_bc");
            local strProceduralBakeDir = FS.Path.Join(strCurUserdataDir, "landscape", "procedural");
            local nRemoveBeginTime = os.clock();
            FS.RemoveAll(strBlendMapBakeDir);
            FS.RemoveAll(strHeightMapBakeDir);
            FS.RemoveAll(strProceduralBakeDir);
            LOG_I(string.format("[TranslateAllHashStorageToPack] RemoveAll for idx %d cost %d", nIdx, os.clock() - nRemoveBeginTime));

            local nPackBeginTime = os.clock();
            local bPackUserdata = ar:GetPlayMode() == g_Game.LGameDefine.PLAY_MOD.SANDBOX;
            local bPackMetadata = true;
            local bPacked = g_Storage:PackHashStorage(arUUID, bPackUserdata, bPackMetadata);
            LOG_I(string.format("[TranslateAllHashStorageToPack] PackHashStorage for idx %d cost %d", nIdx, os.clock() - nPackBeginTime));
            LOG_FOR_PUBLISH_MSG(string.format(
                "[TranslateAllHashStorageToPack] Translate archive %s to packed %s", tostring(arUUID), tostring(bPacked)
            ));
            if bPacked then
                local version = ar:GetVersion();
                local strVersion = version and version:GetVersionString() or "UNKNOWN_VERSION";
                g_Storage:SaveFileByPathToBOH(arUUID, self.TRANSLATE_V_TAG, strVersion);
            end
        end
    end
    LOG_I(string.format("[TranslateAllHashStorageToPack] Cost %d", os.clock() - nBeginTime));
end

---@type LArchiveMgr
_G.g_ArchiveMgr = LArchiveMgr:new();

function onReload()
    if nil ~= _G.g_ArchiveMgr then
        _G.g_ArchiveMgr:UnInit();
    end
end