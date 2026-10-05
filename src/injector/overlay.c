/*
 * woldvein Trainer v0.4.6 - 游戏内 Overlay DLL
 *
 * 功能：
 *   - Hook IDXGISwapChain::Present，在游戏渲染帧上叠加 ImGui 界面
 *   - 支持 DX11（平野孤鸿使用 Unity Il2Cpp + DX11）
 *   - 热键 INSERT 切换 Overlay 显示/隐藏
 *   - 通过命名管道与 Python 端通信，接收修改器状态
 *
 * 编译：
 *   cl /LD /O2 /W3 /Fe:dist\woldvein_overlay.dll src\injector\overlay.c
 *       /link /SUBSYSTEM:WINDOWS user32.lib kernel32.lib d3d11.lib dxgi.lib
 *
 * 依赖：
 *   - ImGui（需要额外引入 imgui 源码）
 *   - 本文件提供 Hook 框架，ImGui 集成需补充 imgui_impl_dx11.cpp / imgui_impl_win32.cpp
 *
 * 注意：这是框架代码，完整 ImGui 渲染需要引入 ImGui 源码并实现渲染回调。
 */
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <stdio.h>
#include <stdbool.h>

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "user32.lib")

// === 全局变量 ===
static HMODULE g_hModule = NULL;
static bool g_overlayVisible = false;
static bool g_initialized = false;

// DX11 相关
static IDXGISwapChain* g_pSwapChain = NULL;
static ID3D11Device* g_pd3dDevice = NULL;
static ID3D11DeviceContext* g_pd3dContext = NULL;

// 原始 Present 函数指针
typedef HRESULT(STDMETHODCALLTYPE* Present_t)(IDXGISwapChain*, UINT, UINT);
static Present_t oPresent = NULL;

// 窗口过程
static WNDPROC oWndProc = NULL;
static HWND g_hwnd = NULL;

// === 命名管道通信（与 Python 端）===
#define PIPE_NAME L"\\\\.\\pipe\\woldvein_overlay"
static HANDLE g_hPipe = INVALID_HANDLE_VALUE;
static char g_statusBuffer[2048] = {0};

// === 前向声明 ===
HRESULT STDMETHODCALLTYPE hkPresent(IDXGISwapChain* pSwapChain, UINT SyncInterval, UINT Flags);
LRESULT CALLBACK hkWndProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam);
void InitImGui(IDXGISwapChain* pSwapChain);
void ShutdownImGui();
void RenderOverlay();
DWORD WINAPI PipeThread(LPVOID lpParam);

// === DllMain ===
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    switch (ul_reason_for_call) {
    case DLL_PROCESS_ATTACH:
        g_hModule = hModule;
        DisableThreadLibraryCalls(hModule);
        // 启动管道通信线程
        CreateThread(NULL, 0, PipeThread, NULL, 0, NULL);
        break;
    case DLL_PROCESS_DETACH:
        ShutdownImGui();
        if (g_hPipe != INVALID_HANDLE_VALUE) CloseHandle(g_hPipe);
        break;
    }
    return TRUE;
}

// === 命名管道线程：接收 Python 端状态 ===
DWORD WINAPI PipeThread(LPVOID lpParam) {
    while (true) {
        g_hPipe = CreateFileW(
            PIPE_NAME, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL
        );
        if (g_hPipe == INVALID_HANDLE_VALUE) {
            Sleep(1000);
            continue;
        }

        char buffer[2048];
        DWORD bytesRead;
        while (ReadFile(g_hPipe, buffer, sizeof(buffer) - 1, &bytesRead, NULL)) {
            if (bytesRead > 0) {
                buffer[bytesRead] = '\0';
                strncpy(g_statusBuffer, buffer, sizeof(g_statusBuffer) - 1);
            }
        }
        CloseHandle(g_hPipe);
        g_hPipe = INVALID_HANDLE_VALUE;
        Sleep(500);
    }
    return 0;
}

// === 窗口过程 Hook：捕获热键 ===
LRESULT CALLBACK hkWndProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    if (uMsg == WM_KEYDOWN && wParam == VK_INSERT) {
        g_overlayVisible = !g_overlayVisible;
        return 0;  // 吞掉 INSERT 键，防止游戏响应
    }
    return CallWindowProc(oWndProc, hWnd, uMsg, wParam, lParam);
}

// === Present Hook：渲染 Overlay ===
HRESULT STDMETHODCALLTYPE hkPresent(IDXGISwapChain* pSwapChain, UINT SyncInterval, UINT Flags) {
    if (!g_initialized) {
        InitImGui(pSwapChain);
        g_initialized = true;
    }

    if (g_overlayVisible) {
        RenderOverlay();
    }

    return oPresent(pSwapChain, SyncInterval, Flags);
}

// === 初始化 ImGui（需要引入 ImGui 源码）===
void InitImGui(IDXGISwapChain* pSwapChain) {
    // 获取设备和上下文
    if (FAILED(pSwapChain->GetDevice(__uuidof(ID3D11Device), (void**)&g_pd3dDevice))) {
        return;
    }
    g_pd3dDevice->GetImmediateContext(&g_pd3dContext);

    // 获取窗口句柄
    DXGI_SWAP_CHAIN_DESC desc;
    pSwapChain->GetDesc(&desc);
    g_hwnd = desc.OutputWindow;

    // Hook 窗口过程
    oWndProc = (WNDPROC)SetWindowLongPtr(g_hwnd, GWLP_WNDPROC, (LONG_PTR)hkWndProc);

    // TODO: 在这里初始化 ImGui
    // IMGUI_CHECKVERSION();
    // ImGui::CreateContext();
    // ImGui_ImplWin32_Init(g_hwnd);
    // ImGui_ImplDX11_Init(g_pd3dDevice, g_pd3dContext);

    g_pSwapChain = pSwapChain;
}

// === 关闭 ImGui ===
void ShutdownImGui() {
    if (g_hwnd && oWndProc) {
        SetWindowLongPtr(g_hwnd, GWLP_WNDPROC, (LONG_PTR)oWndProc);
    }
    // TODO: ImGui_ImplDX11_Shutdown();
    // TODO: ImGui_ImplWin32_Shutdown();
    // TODO: ImGui::DestroyContext();
    if (g_pd3dContext) g_pd3dContext->Release();
    if (g_pd3dDevice) g_pd3dDevice->Release();
}

// === 渲染 Overlay 内容 ===
void RenderOverlay() {
    // TODO: 在这里实现 ImGui 渲染
    // ImGui_ImplDX11_NewFrame();
    // ImGui_ImplWin32_NewFrame();
    // ImGui::NewFrame();
    //
    // ImGui::Begin("woldvein Trainer");
    // ImGui::Text("状态: %s", g_statusBuffer);
    // ImGui::Text("按 INSERT 隐藏/显示");
    // ImGui::End();
    //
    // ImGui::Render();
    // ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
}

// === 导出函数：安装 Hook ===
// 注意：完整的 VTable Hook 需要在运行时获取 SwapChain 虚表地址
// 这里提供框架，实际 Hook 安装需要在游戏初始化后通过 CreateDevice  dummy 获取
__declspec(dllexport) bool InstallOverlayHook() {
    // TODO: 实现完整的 SwapChain VTable Hook
    // 1. 创建临时 D3D11 设备和 SwapChain
    // 2. 从虚表获取 Present 地址
    // 3. 写入跳转指令到 hkPresent
    // 4. 保存原始函数地址到 oPresent
    return false;  // 框架占位，实际实现需补充
}

__declspec(dllexport) void SetOverlayVisible(bool visible) {
    g_overlayVisible = visible;
}

__declspec(dllexport) bool IsOverlayVisible() {
    return g_overlayVisible;
}
