#include <windows.h> 
#include <stdio.h> 
#include <iostream>
#include <fstream>

#include <log4cplus/logger.h>
#include <log4cplus/loggingmacros.h>

#include "serviceController.h"
#include "hosts.h"

using namespace std;

BOOL __stdcall StopDependentServices(SC_HANDLE schSCManager, SC_HANDLE schService);
BOOL __stdcall SetServiceDescription(SC_HANDLE schService, LPTSTR description);

#define LOGMSG_SIZE 255
namespace {
	TCHAR szLogMsg[LOGMSG_SIZE + 1];
	LPTSTR lpszServiceDescription = (LPTSTR)TEXT("Helper service for PAM Connect program PAM-RDP");
}

//-----------------------------------------------------------------------------
VOID __stdcall ServiceInstall()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("ServiceInstall"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	SC_HANDLE schSCManager;
	SC_HANDLE schService;
	TCHAR szPath[MAX_PATH];

	if (!GetModuleFileName(NULL, szPath, MAX_PATH)) {
		snprintf(szLogMsg,LOGMSG_SIZE, "Cannot find service '%s', lastError= %d", szPath,GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		return;
	}

	// Get a handle to the SCM database. 

	schSCManager = OpenSCManager(
		NULL,                    // local computer
		NULL,                    // ServicesActive database 
		SC_MANAGER_ALL_ACCESS);  // full access rights 

	if (NULL == schSCManager) {
		snprintf(szLogMsg, LOGMSG_SIZE, "OpenSCManager failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		return;
	}

	// Create the service

	schService = CreateService(
		schSCManager,				// SCM database 
		SERVICE_NAME,				// name of service 
		SERVICE_NAME_DISPLAY,		// service name to display 
		SERVICE_ALL_ACCESS,			// desired access 
		SERVICE_WIN32_OWN_PROCESS,	// service type 
		SERVICE_AUTO_START,			// start type 
		SERVICE_ERROR_NORMAL,		// error control type 
		szPath,						// path to service's binary 
		NULL,						// no load ordering group 
		NULL,						// no tag identifier 
		NULL,						// no dependencies 
		NULL,						// LocalSystem account 
		NULL);						// no password 

	if (GetLastError() == ERROR_SUCCESS) {
		if (schService == NULL)
		{
			snprintf(szLogMsg, LOGMSG_SIZE, "CreateService failed, lastError= %d", GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			CloseServiceHandle(schSCManager);
			return;
		}
		else
			LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT("Service installed successfully"));

		SetServiceDescription(schService, lpszServiceDescription);

		CloseServiceHandle(schService);
		CloseServiceHandle(schSCManager);
		return;
	}

	if (GetLastError() == ERROR_SERVICE_EXISTS) {
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT("Service already installed"));
	}
	else {
		snprintf(szLogMsg, LOGMSG_SIZE, "CreateService failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
	}
}

//-----------------------------------------------------------------------------
VOID __stdcall ServiceUninstall()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("ServiceUninstall"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	SC_HANDLE schSCManager;
	SC_HANDLE schService;

	// Get a handle to the SCM database. 
	schSCManager = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);

	if (NULL == schSCManager) {
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT("OpenSCManager failed, lastError= " + to_string(GetLastError())));
		return;
	}

	schService = OpenService(schSCManager, SERVICE_NAME, DELETE); 
	if (schService == NULL)
	{
		if (GetLastError() == ERROR_SERVICE_DOES_NOT_EXIST) {
			LOG4CPLUS_WARN(logger, LOG4CPLUS_TEXT("Service not found"));
		}
		else {
			snprintf(szLogMsg, LOGMSG_SIZE, "OpenService failed, lastError= %d", GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		}
		
		CloseServiceHandle(schSCManager);
		return;
	}

	if (!DeleteService(schService))
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "DeleteService failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
	}
	else
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT("Service deleted successfully"));

	CloseServiceHandle(schService);
	CloseServiceHandle(schSCManager);
	return;
}

//-----------------------------------------------------------------------------
VOID __stdcall ServiceStart()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("ServiceStart"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(SERVICE_NAME " version: " PROGRAM_VERSION));

	SC_HANDLE schSCManager;
	SC_HANDLE schService;

	// Get a handle to the SCM database. 
	schSCManager = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
	if (NULL == schSCManager) {
		snprintf(szLogMsg, LOGMSG_SIZE, "OpenSCManager failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		return;
	}

	schService = OpenService(schSCManager, SERVICE_NAME, SERVICE_START);
	if (schService == NULL)
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "OpenService failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		CloseServiceHandle(schSCManager);
		return;
	}

	if (!StartService(schService, 0, NULL))
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "StartService failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
	}
	else {
		//HostsInit();
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT("Service started successfully"));
	}

	CloseServiceHandle(schService);
	CloseServiceHandle(schSCManager);

	return;
}

//-----------------------------------------------------------------------------
VOID __stdcall ServiceStop()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("ServiceStop"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	SC_HANDLE schSCManager;
	SC_HANDLE schService;
	SERVICE_STATUS_PROCESS ssp;
	DWORD dwStartTime = GetTickCount();
	DWORD dwBytesNeeded;
	DWORD dwTimeout = 30000; // 30-second time-out
	DWORD dwWaitTime;

	// Stop hosts access
	HostsExit();

	// Get a handle to the SCM database. 
	schSCManager = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
	if (NULL == schSCManager)
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "OpenSCManager failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		return;
	}

	// Get a handle to the service.

	schService = OpenService(schSCManager, SERVICE_NAME, SERVICE_STOP | SERVICE_QUERY_STATUS | SERVICE_ENUMERATE_DEPENDENTS);
	if (schService == NULL)
	{
		if (GetLastError() == ERROR_SERVICE_DOES_NOT_EXIST) {
			LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("Service is not found"));
		}
		else {
			snprintf(szLogMsg, LOGMSG_SIZE, "OpenService failed, lastError= %d", GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		}
		CloseServiceHandle(schSCManager);
		return;
	}

	// Make sure the service is not already stopped.

	if (!QueryServiceStatusEx(schService, SC_STATUS_PROCESS_INFO, (LPBYTE)&ssp, sizeof(SERVICE_STATUS_PROCESS), &dwBytesNeeded))
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "QueryServiceStatusEx failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		goto stop_cleanup;
	}

	if (ssp.dwCurrentState == SERVICE_STOPPED)
	{
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT("Service already stopped")); 
		goto stop_cleanup;
	}

	// If a stop is pending, wait for it.

	while (ssp.dwCurrentState == SERVICE_STOP_PENDING)
	{
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("Service stop pending..."));

		// Do not wait longer than the wait hint. A good interval is 
		// one-tenth of the wait hint but not less than 1 second  
		// and not more than 10 seconds. 

		dwWaitTime = ssp.dwWaitHint / 10;

		if (dwWaitTime < 1000)
			dwWaitTime = 1000;
		else if (dwWaitTime > 10000)
			dwWaitTime = 10000;

		Sleep(dwWaitTime);

		if (!QueryServiceStatusEx(schService,SC_STATUS_PROCESS_INFO,(LPBYTE)&ssp,sizeof(SERVICE_STATUS_PROCESS),&dwBytesNeeded))
		{
			snprintf(szLogMsg, LOGMSG_SIZE, "QueryServiceStatusEx failed, lastError= %d", GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			goto stop_cleanup;
		}

		if (ssp.dwCurrentState == SERVICE_STOPPED)
		{
			LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT("Service stopped successfully"));
			goto stop_cleanup;
		}

		if (GetTickCount() - dwStartTime > dwTimeout)
		{
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT("Service stop timed out"));
			goto stop_cleanup;
		}
	}

	// If the service is running, dependencies must be stopped first.

	StopDependentServices(schSCManager, schService);

	// Send a stop code to the service.

	if (!ControlService(schService,SERVICE_CONTROL_STOP,(LPSERVICE_STATUS)&ssp))
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "ControlService failed, lastError= %d", GetLastError());
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		goto stop_cleanup;
	}

	// Wait for the service to stop.

	while (ssp.dwCurrentState != SERVICE_STOPPED)
	{
		Sleep(ssp.dwWaitHint);
		if (!QueryServiceStatusEx(schService,SC_STATUS_PROCESS_INFO,(LPBYTE)&ssp,sizeof(SERVICE_STATUS_PROCESS),&dwBytesNeeded))
		{
			snprintf(szLogMsg, LOGMSG_SIZE, "QueryServiceStatusEx failed, lastError= %d", GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			goto stop_cleanup;
		}

		if (ssp.dwCurrentState == SERVICE_STOPPED)
			break;

		if (GetTickCount() - dwStartTime > dwTimeout)
		{
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT("Wait timed out"));
			goto stop_cleanup;
		}
	}

	LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT("Service stopped successfully"));
	
stop_cleanup:
	CloseServiceHandle(schService);
	CloseServiceHandle(schSCManager);
}


//-----------------------------------------------------------------------------
BOOL __stdcall StopDependentServices(SC_HANDLE schSCManager, SC_HANDLE schService)
{
	//log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("StopDependentServices"));
	//LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	DWORD i;
	DWORD dwBytesNeeded;
	DWORD dwCount;

	LPENUM_SERVICE_STATUS   lpDependencies = NULL;
	ENUM_SERVICE_STATUS     ess;
	SC_HANDLE               hDepService;
	SERVICE_STATUS_PROCESS  ssp;

	DWORD dwStartTime = GetTickCount();
	DWORD dwTimeout = 30000; // 30-second time-out

	// Pass a zero-length buffer to get the required buffer size.
	if (EnumDependentServices(schService, SERVICE_ACTIVE, lpDependencies, 0, &dwBytesNeeded, &dwCount)) {
		// If the Enum call succeeds, then there are no dependent
		// services, so do nothing.
		//LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("Npo dependent services"));
		return TRUE;
	}
	else {
		if (GetLastError() != ERROR_MORE_DATA) {
			snprintf(szLogMsg, LOGMSG_SIZE, "EnumDependentServices failed, lastError= %d", GetLastError());
			//LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return FALSE; // Unexpected error
		}

		// Allocate a buffer for the dependencies.
		lpDependencies = (LPENUM_SERVICE_STATUS)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, dwBytesNeeded);

		if (!lpDependencies) 
			return FALSE;

		__try {
			// Enumerate the dependencies.
			if (!EnumDependentServices(schService, SERVICE_ACTIVE,lpDependencies, dwBytesNeeded, &dwBytesNeeded,&dwCount)) {
				//LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("No dependencies"));
				return FALSE;
			}

			for (i = 0; i < dwCount; i++)
			{
				ess = *(lpDependencies + i);
				// Open the service.
				hDepService = OpenService(schSCManager,ess.lpServiceName,SERVICE_STOP | SERVICE_QUERY_STATUS);

				if (!hDepService) {
					//LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("No dependent service"));
					return FALSE;
				}

				__try {
					// Send a stop code.
					if (!ControlService(hDepService,SERVICE_CONTROL_STOP,(LPSERVICE_STATUS)&ssp)) {
						//LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("Stop code sent to ControlService"));
						return FALSE;
					}

					// Wait for the service to stop.
					while (ssp.dwCurrentState != SERVICE_STOPPED)
					{
						Sleep(ssp.dwWaitHint);
						if (!QueryServiceStatusEx(hDepService,SC_STATUS_PROCESS_INFO,(LPBYTE)&ssp,sizeof(SERVICE_STATUS_PROCESS),&dwBytesNeeded)) {
							snprintf(szLogMsg, LOGMSG_SIZE, "QueryServiceStatusEx failed, lastError= %d", GetLastError());
							//LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
							return FALSE;
						}

						if (ssp.dwCurrentState == SERVICE_STOPPED)
							break;

						if (GetTickCount() - dwStartTime > dwTimeout) {
							//LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("Wait timed out"));
							return FALSE;
						}
					}
				}
				__finally
				{
					// Always release the service handle.
					CloseServiceHandle(hDepService);
				}
			}
		}
		__finally
		{
			// Always free the enumeration buffer.
			HeapFree(GetProcessHeap(), 0, lpDependencies);
		}
	}
	return TRUE;
}

//-----------------------------------------------------------------------------
BOOL __stdcall SetServiceDescription(SC_HANDLE schService, LPTSTR description)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("SetServiceDescription"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("start"));

	SERVICE_DESCRIPTION sd;

	sd.lpDescription = description;
	if (!ChangeServiceConfig2(schService, SERVICE_CONFIG_DESCRIPTION, &sd)) {
		snprintf(szLogMsg, LOGMSG_SIZE, "ChangeServiceConfig2 failed, lastError= %d", GetLastError());
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
	}

	return TRUE;
}

