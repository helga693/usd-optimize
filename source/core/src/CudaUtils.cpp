// SPDX-FileCopyrightText: Copyright (c) 2020-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//

#include "usd_optimize/core/CudaUtils.h"

#include <cstring>
#include <mutex>

// clang-format off
// The order of includes is important for Windows.
#ifdef _WIN32
#    define WIN32_LEAN_AND_MEAN
#    include <windows.h>
#    include <setupapi.h>
#    pragma comment(lib, "setupapi.lib")
#else
#    include <dlfcn.h>
#endif
// clang-format on


namespace usd_optimize
{

#if defined(_WIN32)
static bool hasNvidiaDisplayAdapter()
{
    static const GUID GUID_DEVCLASS_DISPLAY = { 0x4d36e968,
                                                0xe325,
                                                0x11ce,
                                                { 0xbf, 0xc1, 0x08, 0x00, 0x2b, 0xe1, 0x03, 0x18 } };

    HDEVINFO deviceInfoSet = SetupDiGetClassDevsA(&GUID_DEVCLASS_DISPLAY, NULL, NULL, DIGCF_PRESENT);
    if (deviceInfoSet == INVALID_HANDLE_VALUE)
    {
        return false;
    }

    SP_DEVINFO_DATA deviceInfoData;
    deviceInfoData.cbSize = sizeof(SP_DEVINFO_DATA);

    bool foundNvidia = false;
    for (DWORD i = 0; SetupDiEnumDeviceInfo(deviceInfoSet, i, &deviceInfoData); i++)
    {
        char buffer[256]{};
        if (SetupDiGetDeviceRegistryPropertyA(deviceInfoSet,
                                              &deviceInfoData,
                                              SPDRP_HARDWAREID,
                                              NULL,
                                              (PBYTE)buffer,
                                              sizeof(buffer),
                                              NULL) &&
            (strstr(buffer, "VEN_10DE") != NULL || strstr(buffer, "ven_10de") != NULL))
        {
            foundNvidia = true;
            break;
        }
    }

    SetupDiDestroyDeviceInfoList(deviceInfoSet);
    return foundNvidia;
}
#endif

bool isCudaAvailable()
{
    static std::once_flag initFlag;
    static bool available = false;

    std::call_once(
        initFlag,
        []()
        {
            // Driver API function pointer types
            typedef int (*PFN_cuInit)(unsigned int);
            typedef int (*PFN_cuDeviceGetCount)(int*);

            PFN_cuInit pfn_cuInit = nullptr;
            PFN_cuDeviceGetCount pfn_cuDeviceGetCount = nullptr;

#if defined(_WIN32)
            if (!hasNvidiaDisplayAdapter())
            {
                USD_OPTIMIZE_LOG_WARN("No NVIDIA GPU found. GPU acceleration disabled.");
                return;
            }

            HMODULE hCudaDriver = LoadLibraryA("nvcuda.dll");
            if (hCudaDriver == NULL)
            {
                USD_OPTIMIZE_LOG_WARN("Could not load nvcuda.dll. GPU acceleration disabled.");
                return;
            }

            pfn_cuInit = (PFN_cuInit)GetProcAddress(hCudaDriver, "cuInit");
            pfn_cuDeviceGetCount = (PFN_cuDeviceGetCount)GetProcAddress(hCudaDriver, "cuDeviceGetCount");

            if (!pfn_cuInit || !pfn_cuDeviceGetCount)
            {
                USD_OPTIMIZE_LOG_WARN("Could not get CUDA driver functions. GPU acceleration disabled.");
                FreeLibrary(hCudaDriver);
                return;
            }

            int err = pfn_cuInit(0);
            if (err != 0)
            {
                USD_OPTIMIZE_LOG_WARN("Could not initialize CUDA driver (error %d). GPU acceleration disabled.", err);
                FreeLibrary(hCudaDriver);
                return;
            }

            int deviceCount = 0;
            err = pfn_cuDeviceGetCount(&deviceCount);
            available = (err == 0 && deviceCount > 0);
            if (err != 0)
            {
                USD_OPTIMIZE_LOG_WARN("Could not query CUDA device count (error %d). GPU acceleration disabled.", err);
            }
            else if (deviceCount <= 0)
            {
                USD_OPTIMIZE_LOG_WARN("No CUDA-capable GPU found. GPU acceleration disabled.");
            }
            FreeLibrary(hCudaDriver);

#elif defined(__linux__)
            void* hCudaDriver = dlopen("libcuda.so", RTLD_NOW);
            if (hCudaDriver == NULL)
            {
                // WSL and possibly other systems might require the .1 suffix.
                hCudaDriver = dlopen("libcuda.so.1", RTLD_NOW);
                if (hCudaDriver == NULL)
                {
                    USD_OPTIMIZE_LOG_WARN("Could not load CUDA driver. GPU acceleration disabled.");
                    return;
                }
            }

            pfn_cuInit = (PFN_cuInit)dlsym(hCudaDriver, "cuInit");
            pfn_cuDeviceGetCount = (PFN_cuDeviceGetCount)dlsym(hCudaDriver, "cuDeviceGetCount");

            if (!pfn_cuInit || !pfn_cuDeviceGetCount)
            {
                USD_OPTIMIZE_LOG_WARN("Could not get CUDA driver functions. GPU acceleration disabled.");
                dlclose(hCudaDriver);
                return;
            }

            int err = pfn_cuInit(0);
            if (err != 0)
            {
                USD_OPTIMIZE_LOG_WARN("Could not initialize CUDA driver (error %d). GPU acceleration disabled.", err);
                dlclose(hCudaDriver);
                return;
            }

            int deviceCount = 0;
            err = pfn_cuDeviceGetCount(&deviceCount);
            available = (err == 0 && deviceCount > 0);
            if (err != 0)
            {
                USD_OPTIMIZE_LOG_WARN("Could not query CUDA device count (error %d). GPU acceleration disabled.", err);
            }
            else if (deviceCount <= 0)
            {
                USD_OPTIMIZE_LOG_WARN("No CUDA-capable GPU found. GPU acceleration disabled.");
            }
            dlclose(hCudaDriver);
#endif
        });

    return available;
}

} // namespace usd_optimize
