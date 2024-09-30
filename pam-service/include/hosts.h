#pragma once
#include <windows.h>
#include <string.h>

VOID __stdcall HostsInit();
VOID __stdcall HostsExit();

DWORD __stdcall HostsAddEntry(std::string);
DWORD __stdcall HostsRemoveEntry(std::string);
DWORD __stdcall HostsBackup();
DWORD __stdcall HostsLoad();
DWORD __stdcall HostsSave();
DWORD __stdcall HostsRestore();
