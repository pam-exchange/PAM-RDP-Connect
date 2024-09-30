#include <windows.h>

#include <log4cplus/logger.h>
#include <log4cplus/loggingmacros.h>

using namespace std;

#define LOGMSG_SIZE 255
namespace {
	TCHAR szLogMsg[LOGMSG_SIZE + 1];
	LPTSTR lpszKeyBase = (LPTSTR)TEXT("Software\\Microsoft\\Terminal Server Client\\LocalDevices");
	HKEY hKeyTrustedServer = 0;
}


//-----------------------------------------------------------------------------
HKEY __stdcall RegistryOpenKey(HKEY hRootKey, LPCTSTR lpszKey)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("RegistryOpenKey"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	HKEY hKey;
	
	snprintf(szLogMsg, LOGMSG_SIZE, "Open/create registry key '%s'", lpszKey);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

	LONG nError = RegOpenKeyEx(hRootKey, lpszKey, NULL, KEY_ALL_ACCESS, &hKey);

	if (nError == ERROR_FILE_NOT_FOUND)
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "Registry key '%s' is not found , create it", lpszKey);
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

		nError = RegCreateKeyEx(hRootKey, lpszKey, NULL, NULL, REG_OPTION_NON_VOLATILE, KEY_ALL_ACCESS, NULL, &hKey, NULL);
	}

	if (nError) {
		snprintf(szLogMsg, LOGMSG_SIZE, "Error open/create registry key '%s', error= %d", lpszKey,nError);
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
	}

	return hKey;
}

//-----------------------------------------------------------------------------
void __stdcall RegistrySetValue(HKEY hKey, LPCTSTR lpValue, DWORD data)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("RegistrySetValue"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	snprintf(szLogMsg, LOGMSG_SIZE, "Setting entry '%s' with value '%.8x (%d)'", lpValue, data, data);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

	LONG nError = RegSetValueEx(hKey, lpValue, NULL, REG_DWORD, (LPBYTE)&data, sizeof(DWORD));

	if (nError) {
		snprintf(szLogMsg, LOGMSG_SIZE, "Error setting value to entry '%s', error= %d", lpValue, nError);
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
	}
}

//-----------------------------------------------------------------------------
void __stdcall RegistryDeleteValue(HKEY hKey, LPCTSTR lpValue)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("RegistrySetValue"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	snprintf(szLogMsg, LOGMSG_SIZE, "Removing entry '%s'", lpValue);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

	LONG nError = RegDeleteValue(hKey, lpValue);

	if (nError) {
		snprintf(szLogMsg, LOGMSG_SIZE, "Error removing entry '%s', error= %d", lpValue, nError);
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
	}
}

//-----------------------------------------------------------------------------
void __stdcall RegistryCloseKey(HKEY hKey)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("RegistryCloseKey"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	RegCloseKey(hKey);
}


//-----------------------------------------------------------------------------
void __stdcall RegistryTrustedServerInit()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("RegistryTrustedServerInit"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (!hKeyTrustedServer) {
		snprintf(szLogMsg, LOGMSG_SIZE, "Open registry key 'HKLM\\%s'", lpszKeyBase);
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

		hKeyTrustedServer = RegistryOpenKey(HKEY_LOCAL_MACHINE, lpszKeyBase);

		if (!hKeyTrustedServer) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Error opening registry key 'HKLM\\%s'", lpszKeyBase);
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		}
	}
}

//-----------------------------------------------------------------------------
void __stdcall RegistryTrustedServerExit()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("RegistryTrustedServerExit"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (hKeyTrustedServer) {
		snprintf(szLogMsg, LOGMSG_SIZE, "Close registry key 'HKLM\\%s'", lpszKeyBase);
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
		RegistryCloseKey(hKeyTrustedServer);
	}
}

//-----------------------------------------------------------------------------
void __stdcall RegistryTrustedServerAdd(LPCTSTR hostname)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("RegistryTrustedServerAdd"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (!hKeyTrustedServer) {
		RegistryTrustedServerInit();

		if (!hKeyTrustedServer) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Regiy key 'HKLM\\%s' is not opened", lpszKeyBase);
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return;
		}
	}

	snprintf(szLogMsg, LOGMSG_SIZE, "Add trusted server '%s' to 'HKLM\\%s'", hostname,lpszKeyBase);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
	RegistrySetValue(hKeyTrustedServer, hostname, 0x6F);
}

//-----------------------------------------------------------------------------
void __stdcall RegistryTrustedServerRemove(LPCTSTR hostname)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("RegistryTrustedServerRemove"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (!hKeyTrustedServer) {
		RegistryTrustedServerInit();

		if (!hKeyTrustedServer) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Regiy key 'HKLM\\%s' is not opened", lpszKeyBase);
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return;
		}
	}

	snprintf(szLogMsg, LOGMSG_SIZE, "Remove trusted server '%s' from 'HKLM\\%s'", hostname, lpszKeyBase);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
	RegistryDeleteValue(hKeyTrustedServer, hostname);
}
