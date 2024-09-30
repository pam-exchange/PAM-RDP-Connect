#include <windows.h>
#include <stdio.h> 
#include <tchar.h>
#include <strsafe.h>
#include <string.h>
#include <regex>
#include <sys/stat.h>
#include <iostream>
#include <fstream>
#include <psapi.h>
#include <winreg.h>

#include <log4cplus/logger.h>
#include <log4cplus/loggingmacros.h>

#include "serviceController.h"
#include "request.h"
#include "hosts.h"
#include "registry.h"

using namespace std;

#define LOGMSG_SIZE 255
namespace {
	TCHAR szLogMsg[LOGMSG_SIZE + 1];
}

#define BUFSIZE 4096

#if ALLOW_RELAXED
#pragma message ("Relaxed client validation - permitted")
#else
#pragma message ("Relaxed client validation - disabled")
#endif

//-----------------------------------------------------------------------------
VOID __stdcall ProcessRequest(HANDLE hPipe, LPTSTR chRequest, LPTSTR chReply, LPDWORD pchBytes)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("ProcessRequest"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	std::string haystack = chRequest;
	BOOL bSuccess = TRUE;
	std::smatch m;
	TCHAR szRspMsg[LOGMSG_SIZE];
	snprintf(szRspMsg, sizeof(szRspMsg), TEXT("OK"));

	/* Authenticate client program sending the pipe message
	   The client program (pam-rdp.exe) is located in same directory as service executable
	*/

	// get caller PID
	ULONG callerPID;
	GetNamedPipeClientProcessId(hPipe, &callerPID);
	snprintf(szLogMsg, LOGMSG_SIZE, "Caller PID= %.4x", callerPID);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

	HANDLE hProcess = OpenProcess(PROCESS_ALL_ACCESS, FALSE, callerPID);
	TCHAR lpCallerFilename[MAX_PATH] = TEXT("");

	GetModuleFileNameExA(hProcess, NULL, lpCallerFilename, sizeof(lpCallerFilename) - 1);
	snprintf(szLogMsg, LOGMSG_SIZE, "Caller filename= '%s'", lpCallerFilename);
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

	// Convert 8.3 short name of caller program to long name 
	if (strchr(lpCallerFilename,'~')) {
		LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Caller filename is short name"));
		TCHAR tmp[MAX_PATH] = TEXT("");
		if (GetLongPathName(lpCallerFilename, tmp, MAX_PATH) > 0) {
			strncpy_s(lpCallerFilename, tmp, MAX_PATH);
			snprintf(szLogMsg, LOGMSG_SIZE, "Caller filename (long)= '%s'", lpCallerFilename);
			LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));
		}
	}

	if (ALLOW_RELAXED && relaxedClientValidation) {
		snprintf(szLogMsg, LOGMSG_SIZE, "Relaxed Client Validation - caller= '%s', expected= '%s'", lpCallerFilename, szClientProgram);
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
	}
	else {
		if (_strnicmp(szClientProgram, lpCallerFilename, sizeof(szClientProgram)) == 0) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Client program is authenticated");
			LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
		}
		else {
			bSuccess = false;
			snprintf(szLogMsg, LOGMSG_SIZE, "Client program is not authenticated - caller= '%s', expected= '%s'", lpCallerFilename, szClientProgram);
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			snprintf(szRspMsg, sizeof(szRspMsg), TEXT("ERROR - Client program is not autnenticated"));
			goto finished;
		}
	}

	snprintf(szLogMsg, LOGMSG_SIZE, "chRequest= '%s'", chRequest);
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

	// ---- add ----
	if (std::regex_match(haystack, m, regex("^add\\s+(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\s+([a-zA-Z0-9_\\-\\.]+)"))) {
		snprintf(szLogMsg, LOGMSG_SIZE, "add command - ip= '%s', name= '%s'", m.str(1).c_str(), m.str(2).c_str());
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

		// entry is 'ip hostname'
		string entry = m.str(1) + " " + m.str(2);

		HostsAddEntry( entry );
		HostsSave();

		snprintf(szLogMsg, LOGMSG_SIZE, "Added '%s'", entry.c_str());
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT(szLogMsg));

		// Add new server to trusted server registry
		RegistryTrustedServerAdd(m.str(2).c_str());

		goto finished;
	}

	// ---- remove ----
	if (std::regex_match(haystack, m, regex("^remove\\s+(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\s+([a-zA-Z0-9_\\-\\.]+)"))) {
		snprintf(szLogMsg, LOGMSG_SIZE, "remove command - ip= '%s', name= '%s'", m.str(1).c_str(), m.str(2).c_str());
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

		// entry is 'ip hostname'
		string entry = m.str(1) + " " + m.str(2);

		HostsRemoveEntry( entry );
		HostsSave();

		snprintf(szLogMsg, LOGMSG_SIZE, "Removed entry '%s'", entry.c_str());
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT(szLogMsg));

		// Remove new server from trusted server registry
		RegistryTrustedServerRemove(m.str(2).c_str());

		goto finished;
	}

	{
		// unsupported command
		bSuccess = false;
		snprintf(szLogMsg, LOGMSG_SIZE, "Unsupported command, chRequest= '%s'", chRequest);
		LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
		snprintf(szRspMsg, sizeof(szRspMsg), TEXT("ERROR - Unknown command"));
		goto finished;
	}
	
finished:
	// return result message
	StringCchCopyNA(chReply, BUFSIZE, szRspMsg, sizeof(szRspMsg));
	*pchBytes = (lstrlen(chReply) + 1) * sizeof(TCHAR);
}

