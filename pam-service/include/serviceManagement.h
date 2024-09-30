#pragma once

#include <windows.h> 

VOID ServiceInstall();
VOID ServiceUninstall();
VOID ServiceStart();
VOID ServiceStop();

extern HANDLE ghMutex;
