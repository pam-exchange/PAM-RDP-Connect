#pragma once

#include <windows.h>

HKEY __stdcall RegistryOpenKey(HKEY hRootKey, LPCTSTR lpszKey);
void __stdcall RegistrySetValue(HKEY hKey, LPCTSTR lpValue, DWORD data);
void __stdcall RegistryDeleteValue(HKEY hKey, LPCTSTR lpValue);
void __stdcall RegistryCloseKey(HKEY hKey);

void __stdcall RegistryTrustedServerInit();
void __stdcall RegistryTrustedServerExit();
void __stdcall RegistryTrustedServerAdd(LPCTSTR hostname);
void __stdcall RegistryTrustedServerRemove(LPCTSTR hostname);
