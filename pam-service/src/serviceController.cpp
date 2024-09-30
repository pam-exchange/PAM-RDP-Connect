#include <windows.h> 
#include <stdio.h> 
#include <tchar.h>
#include <strsafe.h>
#include <string.h>
#include <iostream>
#include <fstream>

#include <log4cplus/logger.h>
#include <log4cplus/loggingmacros.h>
#include <log4cplus/configurator.h>
#include <log4cplus/initializer.h>

#include <getopt.h>

#include "servicecontroller.h"
#include "serviceManagement.h"
#include "request.h"
#include "hosts.h"
#include "registry.h"

using namespace std;

#define LOGMSG_SIZE 255
namespace {
	TCHAR szLogMsg[LOGMSG_SIZE+1];
}

TCHAR szClientProgram[MAX_PATH];	// available for other source files
//boolean relaxedClientValidation = false;

#define BUFSIZE 4096
DWORD WINAPI InstanceThread(LPVOID); 

#if ALLOW_RELAXED
#pragma message ("Relaxed client validation - permitted")
boolean relaxedClientValidation = true;
#else
#pragma message ("Relaxed client validation - disabled")
boolean relaxedClientValidation = false;
#endif

//-----------------------------------------------------------------------------
int PipeMain()
{ 
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("PipeMain"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	BOOL fConnected;
	DWORD dwThreadId; 
	HANDLE hPipe, hThread; 
	LPTSTR lpszPipename = (LPTSTR)PIPE_NAME; 
 
	// The main loop creates an instance of the named pipe and 
	// then waits for a client to connect to it. When the client 
	// connects, a thread is created to handle communications 
	// with that client, and the loop is repeated. 

	PSECURITY_DESCRIPTOR psd = NULL;
	BYTE  sd[SECURITY_DESCRIPTOR_MIN_LENGTH];
	psd = (PSECURITY_DESCRIPTOR)sd;
	InitializeSecurityDescriptor(psd, SECURITY_DESCRIPTOR_REVISION);
	SetSecurityDescriptorDacl(psd, TRUE, (PACL)NULL, FALSE);
	SECURITY_ATTRIBUTES sa = {sizeof(sa), psd, FALSE};

	for (;;) 
	{ 
		snprintf(szLogMsg, LOGMSG_SIZE, "Creating named pipe '%s'", lpszPipename);
		LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

		hPipe = CreateNamedPipe(
					lpszPipename,             	// pipe name 
					PIPE_ACCESS_DUPLEX,       	// read/write access 
					PIPE_TYPE_MESSAGE |       	// message type pipe 
					PIPE_READMODE_MESSAGE |   	// message-read mode 
					PIPE_WAIT|                	// blocking mode 
					PIPE_REJECT_REMOTE_CLIENTS,	// only localhost clients
					PIPE_UNLIMITED_INSTANCES, 	// max. instances  
					BUFSIZE,                  	// output buffer size 
					BUFSIZE,                  	// input buffer size 
					NMPWAIT_USE_DEFAULT_WAIT, 	// client time-out 
					&sa);

		if (hPipe == INVALID_HANDLE_VALUE) 
		{
			snprintf(szLogMsg, LOGMSG_SIZE, "CreatePipe failed, name='%s', lastError= %d", lpszPipename, GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			return 0;
		}
 
		// Wait for the client to connect; if it succeeds, 
		// the function returns a nonzero value. If the function
		// returns zero, GetLastError returns ERROR_PIPE_CONNECTED. 
 
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("Waiting for connection to pipe..."));
		fConnected = ConnectNamedPipe(hPipe, NULL) ? TRUE : (GetLastError() == ERROR_PIPE_CONNECTED);
 
		if (fConnected) 
		{ 
			LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("Client connected, start new thread"));

			// Create a thread for this client. 
			hThread = CreateThread( 
							NULL,              // no security attribute 
							0,                 // default stack size 
							InstanceThread,    // thread proc
							(LPVOID) hPipe,    // thread parameter 
							0,                 // not suspended 
							&dwThreadId);      // returns thread ID 

			if (hThread == NULL) {
				snprintf(szLogMsg, LOGMSG_SIZE, "CreateThread failed, lastError= %d", GetLastError());
				LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
				return 0;
			}

			snprintf(szLogMsg, LOGMSG_SIZE, "New thread created, id= %d", dwThreadId);
			LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT(szLogMsg));

			CloseHandle(hThread);
		} 
		else {
			snprintf(szLogMsg, LOGMSG_SIZE, "ConnectNamedPipe failed, lastError= %d", GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));

			// The client could not connect, so close the pipe. 
			CloseHandle(hPipe);
		}
	} 
	return 1; 
} 
 
//-----------------------------------------------------------------------------
DWORD WINAPI InstanceThread(LPVOID lpvParam)
{ 
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("InstanceThread"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	TCHAR chRequest[BUFSIZE];
	TCHAR chReply[BUFSIZE]; 
	DWORD cbBytesRead, cbReplyBytes, cbWritten; 
	BOOL fSuccess; 
	HANDLE hPipe; 
 
	// The thread's parameter is a handle to a pipe instance. 
 	hPipe = (HANDLE) lpvParam; 
 
	while (1) 
	{ 
		// Read client requests from the pipe. 
		fSuccess = ReadFile( 
						hPipe,        // handle to pipe 
						chRequest,    // buffer to receive data 
						BUFSIZE*sizeof(TCHAR), // size of buffer 
						&cbBytesRead, // number of bytes read 
						NULL);        // not overlapped I/O 

		if (!fSuccess || cbBytesRead == 0) {
			if (fSuccess !=ERROR_SUCCESS && fSuccess!= ERROR_BROKEN_PIPE) {
				snprintf(szLogMsg, LOGMSG_SIZE, "ReadFile failed, lastError= %d", GetLastError());
				LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			}
			break;
		}

		snprintf(szLogMsg, LOGMSG_SIZE, "cbBytesRead= %d, chRequest= '%s'", cbBytesRead, chRequest);
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

		ProcessRequest(hPipe, chRequest, chReply, &cbReplyBytes); 
 
		snprintf(szLogMsg, LOGMSG_SIZE, "cbReplyBytes= %d, chReply= '%s'", cbReplyBytes, chReply);
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

		// Write the reply to the pipe. 
		fSuccess = WriteFile( 
						hPipe,        // handle to pipe 
						chReply,      // buffer to write from 
						cbReplyBytes, // number of bytes to write 
						&cbWritten,   // number of bytes written 
						NULL);        // not overlapped I/O 

		if (! fSuccess || cbReplyBytes != cbWritten) {
			snprintf(szLogMsg, LOGMSG_SIZE, "WriteFile failed, cbReplyBytes= %d, cbWritten= %d, lastError= %d", cbReplyBytes, cbWritten, GetLastError());
			LOG4CPLUS_ERROR(logger, LOG4CPLUS_TEXT(szLogMsg));
			break;
		}
	} 
 
	// Flush the pipe to allow the client to read the pipe's contents 
	// before disconnecting. Then disconnect the pipe, and close the 
	// handle to this pipe instance. 
 
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Cleanup"));
	FlushFileBuffers(hPipe);
	DisconnectNamedPipe(hPipe); 
	CloseHandle(hPipe); 

	return 1;
}

#pragma comment(lib, "advapi32.lib")

// #define SERVICE_NAME                  TEXT("PIPE_NAME")
#define SERVICE_CONTROL_CUSTOM_STOP   240

SERVICE_STATUS_HANDLE hSt   = NULL;
SERVICE_STATUS        svcst = 
{
	SERVICE_WIN32_OWN_PROCESS,
	SERVICE_START_PENDING,
	SERVICE_ACCEPT_PAUSE_CONTINUE | SERVICE_ACCEPT_STOP
};

//-----------------------------------------------------------------------------
void WINAPI Handler(DWORD ctrlCode)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("Handler"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	DWORD& status = svcst.dwCurrentState; // default

	switch( ctrlCode )
	{
	case SERVICE_CONTROL_STOP:
		HostsExit();
		RegistryTrustedServerExit();
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("SetServiceStatus - SERVICE_STOPPED"));
		status = SERVICE_STOPPED;
		break;
	case SERVICE_CONTROL_PAUSE:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("SetServiceStatus - SERVICE_PAUSED"));
		status = SERVICE_PAUSED;
		break;
	case SERVICE_CONTROL_CONTINUE:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("SetServiceStatus - SERVICE_RUNNING"));
		status = SERVICE_RUNNING;
		break;
	case SERVICE_CONTROL_CUSTOM_STOP:
		HostsExit();
		RegistryTrustedServerExit();
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("SetServiceStatus - SERVICE_STOPPED"));
		status = SERVICE_STOPPED;
		break;
	}

	SetServiceStatus(hSt, (LPSERVICE_STATUS)&svcst);
}

//-----------------------------------------------------------------------------
void WINAPI ServiceMain(DWORD argc, LPTSTR* argv)
{
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("ServiceMain"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	hSt = RegisterServiceCtrlHandler(SERVICE_NAME, Handler);
	if (hSt)
	{
		svcst.dwCurrentState = SERVICE_RUNNING;
		SetServiceStatus(hSt, &svcst);
		HostsInit();
		RegistryTrustedServerInit();
		PipeMain();
	}
}

void WINAPI license() {
	SetConsoleOutputCP(CP_UTF8);
	cout << u8"DANSK / DANISH VERSION" << endl;
	cout << u8"-------------------------------" << endl;
	cout << u8"TERMS AND CONDITIONS" << endl;
	cout << u8"Hvis der er uoverensstemmelser mellem den danske og engelske tekst for" << endl;
	cout << u8"Terms & Conditions, så har den danske tekst forrang." << endl;
	cout << endl;
	cout << u8"RETTIGHEDER" << endl;
	cout << u8"PAM-Exchange og associerede selskaber, inklusiv fuldt eller delvist" << endl;
	cout << u8"ejede datterselskaber, er Leverandøren af programmet ”PAM - Connect”." << endl;
	cout << u8"Leverandøren har ophavsret til programmellet og dokumentation i" << endl;
	cout << u8"overensstemmelse med ophavsretslovens bestemmelser herom." << endl;
	cout << endl;
	cout << u8"Kunden erhverver en tidsubegrænset og uoverdragelig brugsret til" << endl;
	cout << u8"programmellet og dokumentation, herunder til tilpassede eller ændrede" << endl;
	cout << u8"udgaver heraf, såfremt Leverandøren efter aftale mellem Parterne har" << endl;
	cout << u8"leveret dette." << endl;
	cout << endl;
	cout << u8"Brugsretten omfatter rettigheder til at foretage den for brugen af" << endl;
	cout << u8"programmellet nødvendige kopiering og ændring, herunder" << endl;
	cout << u8"sikkerhedskopiering og fejlrettelse med henblik på at opnå" << endl;
	cout << u8"interoperabilitet, i overens - stemmelse med ophavsretslovens" << endl;
	cout << u8"bestemmelser herom." << endl;
	cout << endl;
	cout << u8"Kunden er uberettiget til at kopiere programmel og dokumentation i" << endl;
	cout << u8"videre omfang end nødvendigt for at sikre dets drift.Kunden kan" << endl;
	cout << u8"overlade driften af systemet til tredjemand." << endl;
	cout << endl;
	cout << u8"ANSVAR FOR PROGRAMMEL" << endl;
	cout << u8"Programmellet stilles til rådighed på et \"as - is\" grundlag og" << endl;
	cout << u8"Leverandøren er således ikke ansvarlig for eventuelle fejl og mangler" << endl;
	cout << u8"samt programmellets funktion og virkemåde, herunder om det opfylder" << endl;
	cout << u8"Kundens forretningsbehov." << endl;
	cout << endl;
	cout << u8"VEDLIGEHOLDELSE OG VIDEREUDVIKLING AF PROGRAMMEL" << endl;
	cout << u8"Leverandøren er ikke forpligtet til at vedligeholde og videreudvikle" << endl;
	cout << u8"programmet. Hvis kunden opdager fejl eller har forslag om udvidelser" << endl;
	cout << u8"eller ønsker til programmets funktionalitet, kan de fremsendes til" << endl;
	cout << u8"Leverandøren. Leverandøren er ikke forpligtet til at rette fejl og at" << endl;
	cout << u8"forslag og ønsker kan og / eller vil blive inkluderet i en opdateret" << endl;
	cout << u8"version af programmet." << endl;
	cout << endl;
	cout << u8"Copyright 2024, PAM-Exchange" << endl;
	cout << endl;
	cout << endl;
	cout << u8"ENGLISH / ENGELSK VERSION" << endl;
	cout << u8"------------------------------ -" << endl;
	cout << u8"TERMS AND CONDITIONS" << endl;
	cout << u8"In the event of discrepancies in the Danish and English text for Terms" << endl;
	cout << u8"and Conditions, the Danish Terms and Conditions will have priority." << endl;
	cout << endl;
	cout << u8"RIGHTS OF USAGE" << endl;
	cout << u8"PAM-Exchange and any of its subsidiaries and affiliates are the" << endl;
	cout << u8"supplier (“Supplier”) of the program ”PAM Connect” and any" << endl;
	cout << u8"documentation (“Program”). The program is copyrighted and" << endl;
	cout << u8"any documentation according to Danish copyright laws." << endl;
	cout << endl;
	cout << u8"The customer acquires an unlimited time and non - transferrable usage to" << endl;
	cout << u8"the program and documentation, including any adoptions and changes" << endl;
	cout << u8"provided by the Supplier, according to an agreement between the Supplier" << endl;
	cout << u8"and the customer." << endl;
	cout << endl;
	cout << u8"The rights to usage include the permissions to copy the program and" << endl;
	cout << u8"documentation for deployment within the Customer organisation, and to" << endl;
	cout << u8"make necessary changes for installations and operation.This includes" << endl;
	cout << u8"backups and changes necessary for interoperability according to Danish" << endl;
	cout << u8"copyright laws." << endl;
	cout << endl;
	cout << u8"The customer is not permitted to copy the program and documentation" << endl;
	cout << u8"beyond the necessity for operation in the customer environment and" << endl;
	cout << u8"organisation.The customer may grant the operation of the program to a" << endl;
	cout << u8"third party." << endl;
	cout << endl;
	cout << u8"RESPONSIBILITY FOR PROGRAM" << endl;
	cout << u8"The program is supplied on an “as - is” basis and the Supplier is not" << endl;
	cout << u8"responsible for any errors and short comings in the functionality of the" << endl;
	cout << u8"Program, including the fulfilment of Customers requirements to the" << endl;
	cout << u8"program." << endl;
	cout << endl;
	cout << u8"SUPPORT AND MAINTENANCE" << endl;
	cout << u8"The Supplier is not required to maintain and extend the functionality of" << endl;
	cout << u8"the Program. Should the Customer detect errors to the expected" << endl;
	cout << u8"functionality of the Program or has the Customer suggestions for" << endl;
	cout << u8"extensions to the functionality of the Program, such can be reported to" << endl;
	cout << u8"the Supplier. The Supplier is not required and cannot guarantee nor make" << endl;
	cout << u8"any promises to make any such changes to the Program in a future version" << endl;
	cout << u8"or release of the Program." << endl;
	cout << endl;
	cout << u8"Copyright 2024, PAM-Exchange" << endl;
}


//-----------------------------------------------------------------------------
int _tmain(int argc, TCHAR* argv[])
{
	log4cplus::Initializer initializer;

	// Get program path for service executable
	TCHAR szProgramPath[MAX_PATH];
	szProgramPath[sizeof(szProgramPath) - 1] = 0;
	GetModuleFileNameA(NULL, szProgramPath, sizeof(szProgramPath));
	char *pch = strrchr(szProgramPath, '\\');
	if (pch) { *pch = 0; }
	else { szProgramPath[0] = 0; }

	// build logging.properties filename as szProgramPath\logging.properties
	TCHAR szLoggingProperties[MAX_PATH];
	szLoggingProperties[sizeof(szLoggingProperties) - 1] = 0;
	strcpy_s(szLoggingProperties, sizeof(szLoggingProperties), szProgramPath);
	strcat_s(szLoggingProperties, sizeof(szLoggingProperties), "\\logging.properties");

	log4cplus::PropertyConfigurator::doConfigure(szLoggingProperties);
	log4cplus::Logger logger = log4cplus::Logger::getInstance(LOG4CPLUS_TEXT("main"));
	LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Start"));

	// build logging.properties filename as szProgramPath\logging.properties
	szClientProgram[sizeof(szClientProgram) - 1] = 0;
	strcpy_s(szClientProgram, sizeof(szClientProgram), szProgramPath);
	strcat_s(szClientProgram, sizeof(szClientProgram), "\\pam-rdp.exe");

	snprintf(szLogMsg, LOGMSG_SIZE, "Client program= %s", szClientProgram);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));

	SERVICE_TABLE_ENTRY table[] =
	{
		{ (LPTSTR)SERVICE_NAME, ServiceMain },
		{ NULL, NULL }
	};

#define CMD_INSTALL	1
#define CMD_UNINSTALL 2
#define CMD_START 3
#define CMD_STOP 4
#define CMD_RESTART 5
#define CMD_VERSION 6
#define CMD_LICENSE 7

	int cmd= 0;
	while (1)
	{
		// https://www.gnu.org/software/libc/manual/html_node/Getopt-Long-Options.html
		static struct option long_options[] =
		{
			{"install",   no_argument, 0, 'i'},
			{"uninstall", no_argument, 0, 'u'},
			{"start",     no_argument, 0, 's'},
			{"stop",      no_argument, 0, 't'},
			{"restart",   no_argument, 0, 'r'},
			{"help",      no_argument, 0, 'h'},
			{"version",   no_argument, 0, 'v'},
			{"license",   no_argument, 0, 'l'},
#if ALLOW_RELAXED
			{"relax",     no_argument, 0, 'x'},
#endif
			{0, 0, 0, 0}
		};
		/* getopt_long stores the option index here. */
		int option_index = 0;

		int c = getopt_long(argc, argv, "iustrhvlx", long_options, &option_index);

		/* Detect the end of the options. */
		if (c == -1)
			break;

		switch (c)
		{
		case 'i':
			if (cmd) goto usage;
			cmd = CMD_INSTALL;
			break;

		case 'u':
			if (cmd) goto usage;
			cmd = CMD_UNINSTALL;
			break;

		case 's':
			if (cmd) goto usage;
			cmd = CMD_START;
			break;

		case 't':
			if (cmd) goto usage;
			cmd = CMD_STOP;
			break;

		case 'r':
			if (cmd) goto usage;
			cmd = CMD_RESTART;
			break;

		case 'v':
			if (cmd) goto usage;
			cmd = CMD_VERSION;
			break;

		case 'l':
			if (cmd) goto usage;
			cmd = CMD_LICENSE;
			break;

/*
#if ALLOW_RELAXED
		case 'x':
			snprintf(szLogMsg, LOGMSG_SIZE, "relax option");
			LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
			relaxedClientValidation = TRUE;
			break;
#endif
*/

		case 'h':
		case '?':
		default:
			if (cmd) goto usage;
		}
	}

	/* Print any remaining command line arguments (not options). */
	if (optind < argc)
	{
		if (     _stricmp(argv[optind], "install") == 0   || _stricmp(argv[optind], "/install") == 0)   {if (cmd) goto usage; cmd = CMD_INSTALL;}
		else if (_stricmp(argv[optind], "uninstall") == 0 || _stricmp(argv[optind], "/uninstall") == 0) {if (cmd) goto usage; cmd = CMD_UNINSTALL;}
		else if (_stricmp(argv[optind], "start") == 0     || _stricmp(argv[optind], "/start") == 0)     {if (cmd) goto usage; cmd = CMD_START;}
		else if (_stricmp(argv[optind], "stop") == 0      || _stricmp(argv[optind], "/stop") == 0)      {if (cmd) goto usage; cmd = CMD_STOP;}
		else if (_stricmp(argv[optind], "restart") == 0   || _stricmp(argv[optind], "/restart") == 0)   {if (cmd) goto usage; cmd = CMD_RESTART;}
		else if (_stricmp(argv[optind], "version") == 0 || _stricmp(argv[optind], "/version") == 0)		{ if (cmd) goto usage; cmd = CMD_VERSION; }
		else if (_stricmp(argv[optind], "license") == 0 || _stricmp(argv[optind], "/license") == 0)		{ if (cmd) goto usage; cmd = CMD_LICENSE; }
		else {goto usage;}
	}

#if ALLOW_RELAXED
	snprintf(szLogMsg, LOGMSG_SIZE, "relaxedClientValidation= %d", relaxedClientValidation);
	LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT(szLogMsg));
#endif

	switch(cmd)
	{
	case CMD_INSTALL:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("command: install"));
		ServiceInstall();
		ServiceStart();
		return 0;

	case CMD_UNINSTALL:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("command: uninstall"));
		ServiceStop();
		ServiceUninstall();
		return 0;
	
	case CMD_START:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("command: start"));
		ServiceStart();
		return 0;

	case CMD_STOP:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("command: stop"));
		ServiceStop();
		return 0;

	case CMD_RESTART:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("command: restart"));
		ServiceStop();
		ServiceStart();
		return 0;

	case CMD_VERSION:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("command: version"));
		cout << endl << "PAM-RDP-Service version " PROGRAM_VERSION << endl << endl;
		return TRUE;

	case CMD_LICENSE:
		LOG4CPLUS_DEBUG(logger, LOG4CPLUS_TEXT("command: license"));
		cout << endl << "PAM-RDP-Service version " PROGRAM_VERSION << endl << endl;
		license();
		return TRUE;

	default:
		LOG4CPLUS_TRACE(logger, LOG4CPLUS_TEXT("Calling StartServiceCtrlDispatcher"));
		if (!StartServiceCtrlDispatcher(table)) {
			snprintf(szLogMsg, LOGMSG_SIZE, "StartServiceCtrlDispatcher failed, lastError= %d", GetLastError());
			LOG4CPLUS_FATAL(logger, LOG4CPLUS_TEXT(szLogMsg));
			return 1;
		}
		HostsInit();
		return 0;
	}

usage:
	cout << "PAM-Service [-iustrvh] [-x]" << '\n';
	cout << '\n';
	cout << "  -i --install    Install service" << '\n';
	cout << "  -u --uninstall  Uninstall service" << '\n';
	cout << "  -s --start      Start service" << '\n';
	cout << "  -t --stop       Stop service" << '\n';
	cout << "  -r --restart    Restart service" << '\n';
	cout << "  -v --version    Show version" << '\n';
	cout << "  -l --license    Show Terms & Conditions" << '\n';
	cout << "  -h --help       This message" << '\n';
//	cout << "  -x --relaxed    Relaxed client check" << '\n';
	return 1;
}
