#pragma once
#include <windows.h> 
#include <stdio.h> 
#include <tchar.h>
#include <strsafe.h>
#include <string.h>

#define PROGRAM_VERSION TEXT("2.9.0")
#define ALLOW_RELAXED			0
#define PIPE_NAME				TEXT("\\\\.\\pipe\\PAM-CONNECT-SERVICE")
#define SERVICE_NAME			TEXT("pamconnect")
#define SERVICE_NAME_DISPLAY	TEXT("PAM Connect Service")
#define PROGRAM_PATH			TEXT("C:\\Program Files\\PAM-Exchange\\PAM-Connect\\pam-service.exe")

extern TCHAR szClientProgram[MAX_PATH];
extern boolean relaxedClientValidation;	


