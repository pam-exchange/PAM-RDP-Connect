#include <windows.h>
#include <stdio.h> 
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <regex>
#include <mutex>

#include <log4cplus/logger.h>
#include <log4cplus/loggingmacros.h>
#include "hosts.h"

using namespace std;

#define LOGMSG_SIZE 255
namespace {
	TCHAR szLogMsg[LOGMSG_SIZE + 1];
	LPTSTR lpszHosts = (LPTSTR)TEXT("c:\\windows\\system32\\drivers\\etc\\hosts");
	LPTSTR lpszHostsShadow = (LPTSTR)TEXT("c:\\windows\\system32\\drivers\\etc\\hosts.shadow");
	LPTSTR lpszHostsBackup = (LPTSTR)TEXT("c:\\windows\\system32\\drivers\\etc\\hosts.backup");

	std::mutex mtx;
	vector<string> hostsOriginal;
	vector<string> hostsUpdates;
	boolean initialized = FALSE;
}

#define BUFSIZE 4096
DWORD __stdcall FileExists(LPTSTR);

//-----------------------------------------------------------------------------
VOID __stdcall HostsInit() 
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("HostsInit"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	HostsBackup();
	HostsLoad();
	initialized = TRUE;
}

//-----------------------------------------------------------------------------
VOID __stdcall HostsExit() 
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("HostsExit"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	HostsRestore();
}

//-----------------------------------------------------------------------------
DWORD __stdcall HostsLoad()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("HostsLoad"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	snprintf(szLogMsg, LOGMSG_SIZE, "Reading file '%s'", lpszHosts);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

	mtx.lock();		// enter critical section
	ifstream in(lpszHosts); //input file stream
	string line; //variable to hold line while being read

	while (getline(in, line)) {
		if (line.size() > 0 && line[0] != '#') {
			snprintf(szLogMsg, LOGMSG_SIZE, "Read entry= '%s'", line.c_str());
			LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));
			hostsOriginal.push_back(line);
		}
	}
	in.close();
	mtx.unlock();	// exit critical section

	snprintf(szLogMsg, LOGMSG_SIZE, "hostsOriginal size= %zu", hostsOriginal.size());
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
	for (int i = 0; i < hostsOriginal.size(); i++)
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "hostsOriginal entry= '%s'", hostsOriginal[i].c_str());
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
	}
	return 0;
}

//-----------------------------------------------------------------------------
DWORD __stdcall HostsSave()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("HostsSave"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (!initialized) 
		HostsInit(); 

	snprintf(szLogMsg, LOGMSG_SIZE, "Writing file '%s'", lpszHosts);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

	mtx.lock();		// enter critical section
	ofstream out(lpszHosts);

	// Original
	snprintf(szLogMsg, LOGMSG_SIZE, "hostsOriginal size= %zu", hostsOriginal.size());
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));
	for (int i = 0; i < hostsOriginal.size(); i++)
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "hostsOriginal entry= '%s'", hostsOriginal[i].c_str());
		LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

		out << hostsOriginal[i] << '\n';
	}

	// Updates
	snprintf(szLogMsg, LOGMSG_SIZE, "hostsUpdates size= %zu", hostsUpdates.size());
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));
	out << "#\n# PAM-Service\n#\n" << '\n';
	for (int i = 0; i < hostsUpdates.size(); i++)
	{
		snprintf(szLogMsg, LOGMSG_SIZE, "hostsUpdates entry= '%s'", hostsUpdates[i].c_str());
		LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

		out << hostsUpdates[i] << '\n';
	}

	out.close();
	mtx.unlock();	// exit critical section

	return 0;
}


//-----------------------------------------------------------------------------
DWORD __stdcall HostsAddEntry(string entry)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("HostsAddEntry"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (!initialized)
		HostsInit();

	std::smatch matcher;

	snprintf(szLogMsg, LOGMSG_SIZE, "entry= '%s'", entry.c_str());
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

	if (std::regex_match(entry, matcher, regex("^\\s*\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\s+([a-zA-Z0-9_\\-\\.]+)"))) {
		// entry is formatted as "ip-address hostname"

		string search = "^\\s*\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\s+(" + matcher.str(1) + ")";
		snprintf(szLogMsg, LOGMSG_SIZE, "search= '%s'", search.c_str());
		LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

		mtx.lock();		// enter critical section

		boolean modified = FALSE;
		for (int i = 0; i < hostsUpdates.size(); i++)
		{
			LOG4CPLUS_TRACE(logger, hostsUpdates[i]);
			if (std::regex_match(hostsUpdates[i], matcher, regex(search))) {
				snprintf(szLogMsg, LOGMSG_SIZE, "update entry= '%s'", entry.c_str());
				LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
				hostsUpdates[i] = entry;
				modified = TRUE;
				break;
			}
		}

		if (!modified) {
			snprintf(szLogMsg, LOGMSG_SIZE, "adding entry= '%s'", entry.c_str());
			LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
			hostsUpdates.push_back(entry);
		}
		
		mtx.unlock();	// leave critical section
	}
	return 0;
}

//-----------------------------------------------------------------------------
DWORD __stdcall HostsRemoveEntry(string entry)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("HostsRemoveEntry"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (!initialized)
		HostsInit();

	std::smatch matcher;

	snprintf(szLogMsg, LOGMSG_SIZE, "entry= '%s'", entry.c_str());
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

	if (std::regex_match(entry, matcher, regex("^\\s*(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})\\s+([a-zA-Z0-9_\\-\\.]+)"))) {
		// entry is formatted as "ip-address hostname"

		string search = "^\\s*("+matcher.str(1)+")\\s+(" + matcher.str(2) + ")";
		snprintf(szLogMsg, LOGMSG_SIZE, "search= '%s'", search.c_str());
		LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

		mtx.lock();		// enter critical section

		for (int i = 0; i < hostsUpdates.size(); i++)
		{
			LOG4CPLUS_TRACE(logger, hostsUpdates[i]);
			if (std::regex_match(hostsUpdates[i], matcher, regex(search))) {
				snprintf(szLogMsg, LOGMSG_SIZE, "remove entry= '%s'", entry.c_str());
				LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
				hostsUpdates.erase(hostsUpdates.begin()+i);
				break;
			}
		}

		mtx.unlock();	// exit critical section
	}
	return 0;
}

//-----------------------------------------------------------------------------
DWORD __stdcall HostsBackup()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("HostsBackup"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (FileExists(lpszHostsShadow)) {
		snprintf(szLogMsg, LOGMSG_SIZE, "Shadow found, copy '%s' to '%s'", lpszHostsShadow, lpszHosts);
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT(szLogMsg));

		// copy hosts.shadow to hosts
		if (!CopyFile(lpszHostsShadow, lpszHosts, FALSE)) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Failed to copy '%s' to '%s', lastError= %d", lpszHostsShadow, lpszHosts, GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return -1;
		}
	}
	else if (FileExists(lpszHostsBackup)) {
		// backup file already exist, copy backup to hosts
		snprintf(szLogMsg, LOGMSG_SIZE, "Backup found, copy '%s' to '%s'", lpszHostsBackup, lpszHosts);
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT(szLogMsg));

		if (!CopyFile(lpszHostsBackup, lpszHosts, FALSE)) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Failed to copy '%s' to '%s', lastError= %d", lpszHostsBackup, lpszHosts, GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return -2;
		}
	}
	else {
		// no shadow and no backup, create a backup
		snprintf(szLogMsg, LOGMSG_SIZE, "Copy '%s' to '%s'", lpszHosts, lpszHostsBackup);
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT(szLogMsg));

		if (!CopyFile(lpszHosts, lpszHostsBackup, FALSE)) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Failed to copy '%s' to '%s', lastError= %d", lpszHosts, lpszHostsBackup, GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return -3;
		}
	}
	return 0;
}

//-----------------------------------------------------------------------------
DWORD __stdcall HostsRestore()
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("HostsRestore"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	if (FileExists(lpszHostsShadow)) {
		// copy hosts.shadow to hosts
		snprintf(szLogMsg, LOGMSG_SIZE, "Shadow found, copy '%s' to '%s'", lpszHostsShadow, lpszHosts);
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT(szLogMsg));

		if (!CopyFile(lpszHostsShadow, lpszHosts, FALSE)) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Failed to copy '%s' to '%s', lastError= %d", lpszHostsShadow, lpszHosts, GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return -1;
		}
	}
	else if (FileExists(lpszHostsBackup)) {
		// backup file already exist, copy backup to hosts
		snprintf(szLogMsg, LOGMSG_SIZE, "Backup found, copy '%s' to '%s'", lpszHostsBackup, lpszHosts);
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT(szLogMsg));

		if (!CopyFile(lpszHostsBackup, lpszHosts, FALSE)) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Failed to copy '%s' to '%s', lastError= %d", lpszHostsBackup, lpszHosts, GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return -2;
		}
	}

	// always (try to) delete backup file
	if (FileExists(lpszHostsBackup)) {
		snprintf(szLogMsg, LOGMSG_SIZE, "Backup found, deleting '%s'", lpszHostsBackup);
		LOG4CPLUS_INFO(logger, LOG4CPLUS_TEXT(szLogMsg));
		if (!DeleteFile(lpszHostsBackup)) {
			snprintf(szLogMsg, LOGMSG_SIZE, "Failed to delete '%s', lastError= %d", lpszHostsBackup, GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			// Do not flag an error to caller, leave szRspMsg as is
		}
	}

	return 0;
}

#ifndef	S_ISREG
#define	S_ISREG(mode)	(((mode) & S_IFREG) == S_IFREG)
#endif

//-----------------------------------------------------------------------------
DWORD __stdcall FileExists(LPTSTR path)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("FileExists"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	struct stat fileStat;

	if (stat(path, &fileStat)) {
		snprintf(szLogMsg, LOGMSG_SIZE, "File '%s' is not found", path);
		LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));
		return 0;
	}

	snprintf(szLogMsg, LOGMSG_SIZE, "File '%s' status= '%d'", path, fileStat.st_mode);
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

	return S_ISREG(fileStat.st_mode);
}
