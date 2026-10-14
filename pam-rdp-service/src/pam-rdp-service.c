/*
 * MIT License
 *
 * Copyright (c) 2024-2025 PAM-Exchange
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif

#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <psapi.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <time.h>
#include <sys/stat.h>

#define SERVICE_NAME           "PAM-RDP-CONNECT-SERVICE"
#define SERVICE_DISPLAY_NAME    "PAM-RDP-Connect Service"
#define SERVICE_DESCRIPTION     "Service to add or remove entries from hosts file via named pipe."
#define PIPE_NAME              "\\\\.\\pipe\\PAM-RDP-SERVICE"
#define DEFAULT_ALLOWED_CLIENT "C:\\Program Files\\PAM-Exchange\\PAM-RDP-Connect\\pam-rdp.exe"
#define DEFAULT_LOG_FILE       "c:\\Windows\\Temp\\pam-rdp-service.log"
#define HOSTS_FILE_PATH        "C:\\Windows\\System32\\drivers\\etc\\hosts"
#define BACKUP_HOSTS_FILE_PATH "C:\\Windows\\System32\\drivers\\etc\\hosts.bak"
#define REG_KEY_PATH           "Software\\Microsoft\\Terminal Server Client\\LocalDevices"

#define LOG_MAX_SIZE           (5 * 1024 * 1024) // 5 MB
#define LOG_BACKUP_COUNT       5
#define BUFFER_SIZE            65536

enum LogLevel {
    LOG_LEVEL_NOTSET   = 0,
    LOG_LEVEL_DEBUG    = 10,
    LOG_LEVEL_INFO     = 20,
    LOG_LEVEL_WARNING  = 30,
    LOG_LEVEL_ERROR    = 40,
    LOG_LEVEL_CRITICAL = 50
};

static SERVICE_STATUS        g_SvcStatus;
static SERVICE_STATUS_HANDLE g_SvcStatusHandle;
static HANDLE                g_hWaitStop = NULL;
static HANDLE                g_hCommandMutex = NULL;

static char g_configFilename[MAX_PATH] = {0};
static char g_allowedClient[MAX_PATH]  = {0};
static char g_logFile[MAX_PATH]        = {0};
static char g_logLevel[16]             = {0};

static enum LogLevel g_configuredLogLevel = LOG_LEVEL_DEBUG;

/* Function prototypes */
static void load_config(void);
static void backup_hosts_file(void);
static void restore_hosts_file(void);
static int  detect_hosts_encoding(const char *path);
static void add_to_hosts(const char *ip, const char *hostname);
static void remove_from_hosts(const char *ip, const char *hostname);
static void add_to_registry(const char *hostname);
static void remove_from_registry(const char *hostname);
static BOOL is_valid_client(void);
static void process_command(const char *cmd, char *out_response, size_t response_max);
static PSECURITY_ATTRIBUTES CreatePipeSecurityObject(SECURITY_DESCRIPTOR *pSD, PACL *ppDacl);
static void FreePipeSecurityObject(PSECURITY_ATTRIBUTES pSA, PACL pDacl);

static enum LogLevel parse_log_level(const char *level_str) {
    if (_stricmp(level_str, "NOTSET") == 0)   return LOG_LEVEL_NOTSET;
    if (_stricmp(level_str, "DEBUG") == 0)    return LOG_LEVEL_DEBUG;
    if (_stricmp(level_str, "INFO") == 0)     return LOG_LEVEL_INFO;
    if (_stricmp(level_str, "WARNING") == 0)  return LOG_LEVEL_WARNING;
    if (_stricmp(level_str, "ERROR") == 0)    return LOG_LEVEL_ERROR;
    if (_stricmp(level_str, "CRITICAL") == 0) return LOG_LEVEL_CRITICAL;
    return LOG_LEVEL_DEBUG;
}

static const char *level_to_string(enum LogLevel level) {
    switch (level) {
        case LOG_LEVEL_NOTSET:   return "NOTSET";
        case LOG_LEVEL_DEBUG:    return "DEBUG";
        case LOG_LEVEL_INFO:     return "INFO";
        case LOG_LEVEL_WARNING:  return "WARNING";
        case LOG_LEVEL_ERROR:    return "ERROR";
        case LOG_LEVEL_CRITICAL: return "CRITICAL";
        default:                 return "DEBUG";
    }
}

static void rotate_log_files(const char *logfile) {
    struct _stat st;
    if (_stat(logfile, &st) != 0) return;
    if (st.st_size < LOG_MAX_SIZE) return;

    char oldName[MAX_PATH], newName[MAX_PATH];

    snprintf(oldName, sizeof(oldName), "%s.5", logfile);
    remove(oldName);

    for (int i = 4; i >= 1; i--) {
        snprintf(oldName, sizeof(oldName), "%s.%d", logfile, i);
        snprintf(newName, sizeof(newName), "%s.%d", logfile, i + 1);
        rename(oldName, newName);
    }

    snprintf(newName, sizeof(newName), "%s.1", logfile);
    rename(logfile, newName);
}

static void log_msg(enum LogLevel level, const char *func_name, int line_num, const char *fmt, ...) {
    if (level < g_configuredLogLevel) return;

    if (g_logFile[0] == '\0') {
        snprintf(g_logFile, sizeof(g_logFile), "%s", DEFAULT_LOG_FILE);
    }

    rotate_log_files(g_logFile);

    FILE *f = fopen(g_logFile, "a");
    if (!f) return;

    SYSTEMTIME st;
    GetLocalTime(&st);
    char timeStr[64];
    snprintf(timeStr, sizeof(timeStr), "%04d-%02d-%02d %02d:%02d:%02d,%03d",
             st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);

    DWORD pid = GetCurrentProcessId();

    char msgBuf[2048];
    va_list args;
    va_start(args, fmt);
    vsnprintf(msgBuf, sizeof(msgBuf), fmt, args);
    va_end(args);

    fprintf(f, "[%s - %lu - %s] %s (%s - %d)\n",
            timeStr, (unsigned long)pid, level_to_string(level), msgBuf, func_name, line_num);
    fflush(f);
    fclose(f);
}

#define LOG_DEBUG(fmt, ...) log_msg(LOG_LEVEL_DEBUG, __FUNCTION__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_INFO(fmt, ...)  log_msg(LOG_LEVEL_INFO, __FUNCTION__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_WARN(fmt, ...)  log_msg(LOG_LEVEL_WARNING, __FUNCTION__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...) log_msg(LOG_LEVEL_ERROR, __FUNCTION__, __LINE__, fmt, ##__VA_ARGS__)

static void load_config(void) {
    char exePath[MAX_PATH];
    if (GetModuleFileNameA(NULL, exePath, MAX_PATH) > 0) {
        char *lastSlash = strrchr(exePath, '\\');
        if (lastSlash) {
            *lastSlash = '\0';
            snprintf(g_configFilename, sizeof(g_configFilename), "%s\\pam-rdp-service.properties", exePath);
        } else {
            snprintf(g_configFilename, sizeof(g_configFilename), "pam-rdp-service.properties");
        }
    } else {
        snprintf(g_configFilename, sizeof(g_configFilename), "pam-rdp-service.properties");
    }

    GetPrivateProfileStringA("Service", "allowed_client", DEFAULT_ALLOWED_CLIENT,
                            g_allowedClient, sizeof(g_allowedClient), g_configFilename);

    GetPrivateProfileStringA("Logging", "logfile", DEFAULT_LOG_FILE,
                            g_logFile, sizeof(g_logFile), g_configFilename);

    GetPrivateProfileStringA("Logging", "loglevel", "DEBUG",
                            g_logLevel, sizeof(g_logLevel), g_configFilename);

    g_configuredLogLevel = parse_log_level(g_logLevel);

    LOG_DEBUG("Configuration: configFilename= %s", g_configFilename);
    LOG_DEBUG("Configuration: allowed_client= %s", g_allowedClient);
}

static void backup_hosts_file(void) {
    DWORD dwAttrib = GetFileAttributesA(HOSTS_FILE_PATH);
    if (dwAttrib != INVALID_FILE_ATTRIBUTES && !(dwAttrib & FILE_ATTRIBUTE_DIRECTORY)) {
        if (CopyFileA(HOSTS_FILE_PATH, BACKUP_HOSTS_FILE_PATH, FALSE)) {
            LOG_INFO("Copy file %s --> %s", HOSTS_FILE_PATH, BACKUP_HOSTS_FILE_PATH);
        } else {
            LOG_ERROR("Failed to copy %s to %s, error=%lu", HOSTS_FILE_PATH, BACKUP_HOSTS_FILE_PATH, GetLastError());
        }
    } else {
        LOG_DEBUG("No hosts file found");
    }
}

static void restore_hosts_file(void) {
    DWORD dwAttrib = GetFileAttributesA(BACKUP_HOSTS_FILE_PATH);
    if (dwAttrib != INVALID_FILE_ATTRIBUTES && !(dwAttrib & FILE_ATTRIBUTE_DIRECTORY)) {
        if (CopyFileA(BACKUP_HOSTS_FILE_PATH, HOSTS_FILE_PATH, FALSE)) {
            LOG_INFO("Copy file %s --> %s", BACKUP_HOSTS_FILE_PATH, HOSTS_FILE_PATH);
        } else {
            LOG_ERROR("Failed to copy %s to %s, error=%lu", BACKUP_HOSTS_FILE_PATH, HOSTS_FILE_PATH, GetLastError());
        }
    } else {
        LOG_DEBUG("No hosts backup found");
    }
}

static int detect_hosts_encoding(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;

    unsigned char buf[4] = {0};
    size_t n = fread(buf, 1, 4, f);
    fclose(f);

    if (n >= 2 && buf[0] == 0xFF && buf[1] == 0xFE) {
        return 1; // UTF-16 LE
    } else if (n >= 2 && buf[0] == 0xFE && buf[1] == 0xFF) {
        return 2; // UTF-16 BE
    } else if (n >= 3 && buf[0] == 0xEF && buf[1] == 0xBB && buf[2] == 0xBF) {
        return 3; // UTF-8 BOM
    }
    return 0; // ASCII / UTF-8 without BOM
}

static void add_to_hosts(const char *ip, const char *hostname) {
    int enc = detect_hosts_encoding(HOSTS_FILE_PATH);
    FILE *f = fopen(HOSTS_FILE_PATH, "ab");
    if (!f) {
        LOG_ERROR("Failed to open hosts file for appending: %s", HOSTS_FILE_PATH);
        return;
    }

    char lineUtf8[512];
    snprintf(lineUtf8, sizeof(lineUtf8), "%s\t%s\r\n", ip, hostname);

    if (enc == 1) { // UTF-16 LE
        wchar_t wBuf[512];
        int wLen = MultiByteToWideChar(CP_UTF8, 0, lineUtf8, -1, wBuf, 512);
        if (wLen > 1) {
            fwrite(wBuf, sizeof(wchar_t), wLen - 1, f);
        }
    } else { // ASCII / UTF-8
        fwrite(lineUtf8, 1, strlen(lineUtf8), f);
    }

    fclose(f);
    LOG_INFO("Added entry to hosts file: %s %s", ip, hostname);
}

static void remove_from_hosts(const char *ip, const char *hostname) {
    int enc = detect_hosts_encoding(HOSTS_FILE_PATH);

    FILE *f = fopen(HOSTS_FILE_PATH, "rb");
    if (!f) {
        LOG_ERROR("Failed to open hosts file for reading: %s", HOSTS_FILE_PATH);
        return;
    }

    fseek(f, 0, SEEK_END);
    long fileSize = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fileSize <= 0) {
        fclose(f);
        return;
    }

    unsigned char *fileBuf = (unsigned char*)malloc(fileSize + 4);
    if (!fileBuf) {
        fclose(f);
        return;
    }

    fread(fileBuf, 1, fileSize, f);
    fclose(f);
    fileBuf[fileSize] = 0;
    fileBuf[fileSize + 1] = 0;

    char *utf8Text = NULL;

    if (enc == 1) { // UTF-16 LE
        unsigned char *pData = fileBuf;
        long dataLen = fileSize;
        if (fileSize >= 2 && pData[0] == 0xFF && pData[1] == 0xFE) {
            pData += 2;
            dataLen -= 2;
        }
        int wChars = dataLen / 2;
        int reqBytes = WideCharToMultiByte(CP_UTF8, 0, (wchar_t*)pData, wChars, NULL, 0, NULL, NULL);
        utf8Text = (char*)malloc(reqBytes + 1);
        if (utf8Text) {
            WideCharToMultiByte(CP_UTF8, 0, (wchar_t*)pData, wChars, utf8Text, reqBytes, NULL, NULL);
            utf8Text[reqBytes] = '\0';
        }
        free(fileBuf);
    } else {
        unsigned char *pData = fileBuf;
        long dataLen = fileSize;
        if (fileSize >= 3 && pData[0] == 0xEF && pData[1] == 0xBB && pData[2] == 0xBF) {
            pData += 3;
            dataLen -= 3;
        }
        utf8Text = (char*)malloc(dataLen + 1);
        if (utf8Text) {
            memcpy(utf8Text, pData, dataLen);
            utf8Text[dataLen] = '\0';
        }
        free(fileBuf);
    }

    if (!utf8Text) {
        LOG_ERROR("Memory allocation failure processing hosts file");
        return;
    }

    char *newContent = (char*)malloc(strlen(utf8Text) + 1);
    if (!newContent) {
        free(utf8Text);
        return;
    }
    newContent[0] = '\0';
    size_t newLen = 0;

    char *line = utf8Text;
    while (*line) {
        char *nextLine = strchr(line, '\n');
        size_t lineLen;
        if (nextLine) {
            lineLen = nextLine - line + 1;
        } else {
            lineLen = strlen(line);
        }

        char tempLine[1024];
        size_t copyLen = lineLen < sizeof(tempLine) - 1 ? lineLen : sizeof(tempLine) - 1;
        memcpy(tempLine, line, copyLen);
        tempLine[copyLen] = '\0';

        char *pTrim = tempLine;
        while (*pTrim == ' ' || *pTrim == '\t') pTrim++;

        BOOL isMatch = FALSE;
        if (_strnicmp(pTrim, ip, strlen(ip)) == 0) {
            if (strstr(tempLine, hostname) != NULL) {
                isMatch = TRUE;
            }
        }

        if (!isMatch) {
            memcpy(newContent + newLen, line, lineLen);
            newLen += lineLen;
            newContent[newLen] = '\0';
        }

        if (nextLine) {
            line = nextLine + 1;
        } else {
            break;
        }
    }

    free(utf8Text);

    f = fopen(HOSTS_FILE_PATH, "wb");
    if (!f) {
        LOG_ERROR("Failed to open hosts file for writing: %s", HOSTS_FILE_PATH);
        free(newContent);
        return;
    }

    if (enc == 1) { // UTF-16 LE
        unsigned char bom[2] = {0xFF, 0xFE};
        fwrite(bom, 1, 2, f);

        int reqWChars = MultiByteToWideChar(CP_UTF8, 0, newContent, -1, NULL, 0);
        if (reqWChars > 0) {
            wchar_t *wBuf = (wchar_t*)malloc(reqWChars * sizeof(wchar_t));
            if (wBuf) {
                MultiByteToWideChar(CP_UTF8, 0, newContent, -1, wBuf, reqWChars);
                if (reqWChars > 1) {
                    fwrite(wBuf, sizeof(wchar_t), reqWChars - 1, f);
                }
                free(wBuf);
            }
        }
    } else {
        if (enc == 3) { // UTF-8 BOM
            unsigned char bom[3] = {0xEF, 0xBB, 0xBF};
            fwrite(bom, 1, 3, f);
        }
        fwrite(newContent, 1, newLen, f);
    }

    fclose(f);
    free(newContent);
    LOG_INFO("Removed entry from hosts file: %s %s", ip, hostname);
}

static void add_to_registry(const char *hostname) {
    HKEY hKey;
    LONG res = RegCreateKeyExA(HKEY_LOCAL_MACHINE, REG_KEY_PATH, 0, NULL, 0, KEY_SET_VALUE, NULL, &hKey, NULL);
    if (res == ERROR_SUCCESS) {
        DWORD dwValue = 1;
        RegSetValueExA(hKey, hostname, 0, REG_DWORD, (BYTE*)&dwValue, sizeof(dwValue));
        RegCloseKey(hKey);
        LOG_INFO("Added '%s' to registry.", hostname);
    } else {
        LOG_ERROR("Failed to create/open registry key %s, error=%ld", REG_KEY_PATH, res);
    }
}

static void remove_from_registry(const char *hostname) {
    HKEY hKey;
    LONG res = RegOpenKeyExA(HKEY_LOCAL_MACHINE, REG_KEY_PATH, 0, KEY_SET_VALUE, &hKey);
    if (res == ERROR_SUCCESS) {
        RegDeleteValueA(hKey, hostname);
        RegCloseKey(hKey);
        LOG_INFO("Removed '%s' from registry.", hostname);
    } else {
        LOG_ERROR("Failed to open registry key %s for deletion, error=%ld", REG_KEY_PATH, res);
    }
}

static BOOL is_valid_client(void) {
    HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnap == INVALID_HANDLE_VALUE) {
        LOG_DEBUG("Calling client - Not OK (snapshot failed)");
        return FALSE;
    }

    PROCESSENTRY32 pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32);

    if (!Process32First(hSnap, &pe32)) {
        CloseHandle(hSnap);
        LOG_DEBUG("Calling client - Not OK (Process32First failed)");
        return FALSE;
    }

    BOOL isValid = FALSE;
    typedef BOOL (WINAPI *QueryFullProcessImageNameA_t)(HANDLE, DWORD, LPSTR, PDWORD);
    static QueryFullProcessImageNameA_t pQueryFullProcessImageNameA = NULL;
    static BOOL pQueryChecked = FALSE;

    if (!pQueryChecked) {
        HMODULE hKernel32 = GetModuleHandleA("kernel32.dll");
        if (hKernel32) {
            pQueryFullProcessImageNameA = (QueryFullProcessImageNameA_t)(void*)GetProcAddress(hKernel32, "QueryFullProcessImageNameA");
        }
        pQueryChecked = TRUE;
    }

    do {
        HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pe32.th32ProcessID);
        if (!hProcess) {
            hProcess = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pe32.th32ProcessID);
        }
        if (hProcess) {
            char exePath[MAX_PATH] = {0};
            DWORD dwSize = MAX_PATH;
            BOOL gotPath = FALSE;

            if (pQueryFullProcessImageNameA) {
                if (pQueryFullProcessImageNameA(hProcess, 0, exePath, &dwSize)) {
                    gotPath = TRUE;
                }
            }
            if (!gotPath) {
                if (GetModuleFileNameExA(hProcess, NULL, exePath, MAX_PATH) > 0) {
                    gotPath = TRUE;
                }
            }

            CloseHandle(hProcess);

            if (gotPath) {
                if (_stricmp(exePath, g_allowedClient) == 0) {
                    isValid = TRUE;
                    break;
                }
            }
        }
    } while (Process32Next(hSnap, &pe32));

    CloseHandle(hSnap);

    if (isValid) {
        LOG_DEBUG("Calling client - OK");
    } else {
        LOG_DEBUG("Calling client - Not OK");
    }
    return isValid;
}

static void process_command(const char *cmd, char *out_response, size_t response_max) {
    if (!is_valid_client()) {
        snprintf(out_response, response_max, "ERROR: Unauthorized client");
        return;
    }

    char cmdCopy[1024];
    snprintf(cmdCopy, sizeof(cmdCopy), "%s", cmd);

    char *p = cmdCopy + strlen(cmdCopy) - 1;
    while (p >= cmdCopy && isspace((unsigned char)*p)) {
        *p = '\0';
        p--;
    }
    char *start = cmdCopy;
    while (*start && isspace((unsigned char)*start)) {
        start++;
    }

    if (strlen(start) == 0) {
        LOG_ERROR("Invalid command received. command= %s", cmd);
        snprintf(out_response, response_max, "ERROR: Invalid command format");
        return;
    }

    char *tokens[10];
    int tokenCount = 0;
    char *tok = strtok(start, " \t\r\n");
    while (tok && tokenCount < 10) {
        tokens[tokenCount++] = tok;
        tok = strtok(NULL, " \t\r\n");
    }

    if (tokenCount != 3) {
        LOG_ERROR("Invalid command received. command= %s", cmd);
        snprintf(out_response, response_max, "ERROR: Invalid command format");
        return;
    }

    char action[64], ip[256], hostname[256];
    snprintf(action, sizeof(action), "%s", tokens[0]);
    snprintf(ip, sizeof(ip), "%s", tokens[1]);
    snprintf(hostname, sizeof(hostname), "%s", tokens[2]);

    for (int i = 0; action[i]; i++) {
        action[i] = (char)tolower((unsigned char)action[i]);
    }

    if (strcmp(action, "add") == 0) {
        LOG_DEBUG("adding ip=%s hostname=%s", ip, hostname);
        add_to_registry(hostname);
        add_to_hosts(ip, hostname);
        snprintf(out_response, response_max, "OK: %s %s added", ip, hostname);
    } else if (strcmp(action, "remove") == 0) {
        LOG_DEBUG("removing ip=%s hostname=%s", ip, hostname);
        remove_from_registry(hostname);
        remove_from_hosts(ip, hostname);
        snprintf(out_response, response_max, "OK: %s %s removed", ip, hostname);
    } else {
        LOG_ERROR("Unknown command: %s", cmd);
        snprintf(out_response, response_max, "ERROR: Unknown command");
    }
}

static PSECURITY_ATTRIBUTES CreatePipeSecurityObject(SECURITY_DESCRIPTOR *pSD, PACL *ppDacl) {
    PSID pSidEveryone = NULL;
    PSID pSidCreatorOwner = NULL;
    SID_IDENTIFIER_AUTHORITY SIDAuthWorld = SECURITY_WORLD_SID_AUTHORITY;
    SID_IDENTIFIER_AUTHORITY SIDAuthCreator = SECURITY_CREATOR_SID_AUTHORITY;

    if (!AllocateAndInitializeSid(&SIDAuthWorld, 1, SECURITY_WORLD_RID, 0, 0, 0, 0, 0, 0, 0, &pSidEveryone)) {
        return NULL;
    }
    if (!AllocateAndInitializeSid(&SIDAuthCreator, 1, SECURITY_CREATOR_OWNER_RID, 0, 0, 0, 0, 0, 0, 0, &pSidCreatorOwner)) {
        FreeSid(pSidEveryone);
        return NULL;
    }

    DWORD cbAcl = sizeof(ACL) +
                  sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD) + GetLengthSid(pSidEveryone) +
                  sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD) + GetLengthSid(pSidCreatorOwner);

    *ppDacl = (PACL)LocalAlloc(LPTR, cbAcl);
    if (!*ppDacl) {
        FreeSid(pSidEveryone);
        FreeSid(pSidCreatorOwner);
        return NULL;
    }

    InitializeAcl(*ppDacl, cbAcl, ACL_REVISION);
    AddAccessAllowedAce(*ppDacl, ACL_REVISION, FILE_GENERIC_READ | FILE_GENERIC_WRITE, pSidEveryone);
    AddAccessAllowedAce(*ppDacl, ACL_REVISION, FILE_ALL_ACCESS, pSidCreatorOwner);

    InitializeSecurityDescriptor(pSD, SECURITY_DESCRIPTOR_REVISION);
    SetSecurityDescriptorDacl(pSD, TRUE, *ppDacl, FALSE);

    PSECURITY_ATTRIBUTES pSA = (PSECURITY_ATTRIBUTES)LocalAlloc(LPTR, sizeof(SECURITY_ATTRIBUTES));
    if (pSA) {
        pSA->nLength = sizeof(SECURITY_ATTRIBUTES);
        pSA->lpSecurityDescriptor = pSD;
        pSA->bInheritHandle = FALSE;
    }

    FreeSid(pSidEveryone);
    FreeSid(pSidCreatorOwner);
    return pSA;
}

static void FreePipeSecurityObject(PSECURITY_ATTRIBUTES pSA, PACL pDacl) {
    if (pDacl) LocalFree(pDacl);
    if (pSA) LocalFree(pSA);
}

static void ServiceRun(void) {
    LOG_INFO("Starting service...");
    backup_hosts_file();

    LOG_DEBUG("create security attribute");
    SECURITY_DESCRIPTOR sd;
    PACL pDacl = NULL;
    PSECURITY_ATTRIBUTES pSA = CreatePipeSecurityObject(&sd, &pDacl);

    g_hCommandMutex = CreateMutex(NULL, FALSE, NULL);

    OVERLAPPED overlapped;
    ZeroMemory(&overlapped, sizeof(OVERLAPPED));
    overlapped.hEvent = CreateEvent(NULL, TRUE, FALSE, NULL);

    HANDLE waitHandles[2];
    waitHandles[0] = g_hWaitStop;
    waitHandles[1] = overlapped.hEvent;

    while (TRUE) {
        LOG_DEBUG("create named pipe");
        HANDLE hPipe = CreateNamedPipeA(
            PIPE_NAME,
            PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
            PIPE_UNLIMITED_INSTANCES,
            BUFFER_SIZE, BUFFER_SIZE, 0,
            pSA
        );

        if (hPipe == INVALID_HANDLE_VALUE) {
            LOG_ERROR("Failed to create named pipe, error=%lu", GetLastError());
            break;
        }

        BOOL fConnected = ConnectNamedPipe(hPipe, &overlapped);
        DWORD dwErr = GetLastError();

        if (!fConnected) {
            if (dwErr == ERROR_PIPE_CONNECTED) {
                LOG_DEBUG("Client is fast, hr= %lu", dwErr);
                SetEvent(overlapped.hEvent);
            } else if (dwErr != ERROR_IO_PENDING) {
                LOG_DEBUG("Error connecting pipe, error=%lu", dwErr);
                CloseHandle(hPipe);
                break;
            }
        }

        LOG_DEBUG("Wait for multiple events");
        DWORD dwWait = WaitForMultipleObjects(2, waitHandles, FALSE, INFINITE);

        if (dwWait == WAIT_OBJECT_0) {
            LOG_DEBUG("Stop event received");
            CloseHandle(hPipe);
            break;
        } else if (dwWait == WAIT_OBJECT_0 + 1) {
            LOG_DEBUG("Pipe event received");
            ResetEvent(overlapped.hEvent);

            char inBuffer[65536] = {0};
            DWORD cbRead = 0;

            OVERLAPPED readOverlapped;
            ZeroMemory(&readOverlapped, sizeof(OVERLAPPED));
            readOverlapped.hEvent = CreateEvent(NULL, TRUE, FALSE, NULL);

            BOOL fRead = ReadFile(hPipe, inBuffer, sizeof(inBuffer) - 1, &cbRead, &readOverlapped);
            if (!fRead && GetLastError() == ERROR_IO_PENDING) {
                fRead = GetOverlappedResult(hPipe, &readOverlapped, &cbRead, TRUE);
            }
            CloseHandle(readOverlapped.hEvent);

            LOG_DEBUG("ReadFile, result= %d, bytesRead= %lu", fRead, cbRead);

            if (fRead && cbRead > 0) {
                inBuffer[cbRead] = '\0';
                LOG_DEBUG("Command received: %s", inBuffer);

                LOG_DEBUG("Acquire Semaphore");
                WaitForSingleObject(g_hCommandMutex, INFINITE);
                LOG_DEBUG("Semaphore acquired");

                char response[2048] = {0};
                process_command(inBuffer, response, sizeof(response));
                LOG_DEBUG("Response from process_command: %s", response);

                DWORD cbWritten = 0;
                OVERLAPPED writeOverlapped;
                ZeroMemory(&writeOverlapped, sizeof(OVERLAPPED));
                writeOverlapped.hEvent = CreateEvent(NULL, TRUE, FALSE, NULL);

                BOOL fWrite = WriteFile(hPipe, response, (DWORD)strlen(response), &cbWritten, &writeOverlapped);
                if (!fWrite && GetLastError() == ERROR_IO_PENDING) {
                    GetOverlappedResult(hPipe, &writeOverlapped, &cbWritten, TRUE);
                }
                CloseHandle(writeOverlapped.hEvent);

                ReleaseMutex(g_hCommandMutex);
                LOG_DEBUG("Seemaphore released");
            } else {
                LOG_DEBUG("client closed connection");
            }

            LOG_DEBUG("DisconnectNamedPipe");
            DisconnectNamedPipe(hPipe);
            CloseHandle(hPipe);
        } else {
            LOG_ERROR("WaitForMultipleObjects returned unexpected value: %lu", dwWait);
            CloseHandle(hPipe);
            break;
        }
    }

    if (overlapped.hEvent) CloseHandle(overlapped.hEvent);
    if (g_hCommandMutex) CloseHandle(g_hCommandMutex);
    FreePipeSecurityObject(pSA, pDacl);
}

static VOID WINAPI ReportSvcStatus(DWORD dwCurrentState, DWORD dwWin32ExitCode, DWORD dwWaitHint) {
    static DWORD dwCheckPoint = 1;

    g_SvcStatus.dwServiceType = SERVICE_WIN32_OWN_PROCESS;
    g_SvcStatus.dwCurrentState = dwCurrentState;
    g_SvcStatus.dwWin32ExitCode = dwWin32ExitCode;
    g_SvcStatus.dwWaitHint = dwWaitHint;

    if (dwCurrentState == SERVICE_START_PENDING)
        g_SvcStatus.dwControlsAccepted = 0;
    else
        g_SvcStatus.dwControlsAccepted = SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN;

    if ((dwCurrentState == SERVICE_RUNNING) || (dwCurrentState == SERVICE_STOPPED))
        g_SvcStatus.dwCheckPoint = 0;
    else
        g_SvcStatus.dwCheckPoint = dwCheckPoint++;

    SetServiceStatus(g_SvcStatusHandle, &g_SvcStatus);
}

static VOID WINAPI SvcCtrlHandler(DWORD dwCtrl) {
    switch (dwCtrl) {
        case SERVICE_CONTROL_STOP:
        case SERVICE_CONTROL_SHUTDOWN:
            LOG_INFO("Stopping service...");
            ReportSvcStatus(SERVICE_STOP_PENDING, NO_ERROR, 5000);
            restore_hosts_file();
            if (g_hWaitStop) SetEvent(g_hWaitStop);
            LOG_DEBUG("Service stop event signaled");
            return;
        default:
            break;
    }
}

static VOID WINAPI ServiceMain(DWORD dwArgc, LPTSTR *lpszArgv) {
    (void)dwArgc;
    (void)lpszArgv;

    g_SvcStatusHandle = RegisterServiceCtrlHandlerA(SERVICE_NAME, SvcCtrlHandler);
    if (!g_SvcStatusHandle) {
        return;
    }

    ReportSvcStatus(SERVICE_START_PENDING, NO_ERROR, 3000);

    g_hWaitStop = CreateEvent(NULL, TRUE, FALSE, NULL);
    if (!g_hWaitStop) {
        ReportSvcStatus(SERVICE_STOPPED, GetLastError(), 0);
        return;
    }

    load_config();
    ReportSvcStatus(SERVICE_RUNNING, NO_ERROR, 0);

    ServiceRun();

    LOG_DEBUG("Service stopped");
    ReportSvcStatus(SERVICE_STOPPED, NO_ERROR, 0);
}

static void InstallServiceCmd(void) {
    SC_HANDLE hSCM = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
    if (!hSCM) {
        printf("Failed to open Service Control Manager. Error: %lu\n", GetLastError());
        return;
    }

    char szPath[MAX_PATH];
    if (!GetModuleFileNameA(NULL, szPath, MAX_PATH)) {
        printf("Failed to get module file name. Error: %lu\n", GetLastError());
        CloseServiceHandle(hSCM);
        return;
    }

    SC_HANDLE hService = CreateServiceA(
        hSCM,
        SERVICE_NAME,
        SERVICE_DISPLAY_NAME,
        SERVICE_ALL_ACCESS,
        SERVICE_WIN32_OWN_PROCESS,
        SERVICE_AUTO_START,
        SERVICE_ERROR_NORMAL,
        szPath,
        NULL, NULL, NULL, NULL, NULL
    );

    if (!hService) {
        DWORD dwErr = GetLastError();
        if (dwErr == ERROR_SERVICE_EXISTS) {
            printf("Service already exists.\n");
        } else {
            printf("Failed to create service. Error: %lu\n", dwErr);
        }
        CloseServiceHandle(hSCM);
        return;
    }

    SERVICE_DESCRIPTIONA sd;
    sd.lpDescription = SERVICE_DESCRIPTION;
    ChangeServiceConfig2A(hService, SERVICE_CONFIG_DESCRIPTION, &sd);

    printf("Service '%s' installed successfully.\n", SERVICE_NAME);
    CloseServiceHandle(hService);
    CloseServiceHandle(hSCM);
}

static void RemoveServiceCmd(void) {
    SC_HANDLE hSCM = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
    if (!hSCM) {
        printf("Failed to open Service Control Manager. Error: %lu\n", GetLastError());
        return;
    }

    SC_HANDLE hService = OpenServiceA(hSCM, SERVICE_NAME, DELETE);
    if (!hService) {
        printf("Failed to open service. Error: %lu\n", GetLastError());
        CloseServiceHandle(hSCM);
        return;
    }

    if (DeleteService(hService)) {
        printf("Service '%s' removed successfully.\n", SERVICE_NAME);
    } else {
        printf("Failed to remove service. Error: %lu\n", GetLastError());
    }

    CloseServiceHandle(hService);
    CloseServiceHandle(hSCM);
}

static void StartServiceCmd(void) {
    SC_HANDLE hSCM = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
    if (!hSCM) {
        printf("Failed to open Service Control Manager. Error: %lu\n", GetLastError());
        return;
    }

    SC_HANDLE hService = OpenServiceA(hSCM, SERVICE_NAME, SERVICE_START);
    if (!hService) {
        printf("Failed to open service. Error: %lu\n", GetLastError());
        CloseServiceHandle(hSCM);
        return;
    }

    if (StartServiceA(hService, 0, NULL)) {
        printf("Service '%s' started successfully.\n", SERVICE_NAME);
    } else {
        DWORD dwErr = GetLastError();
        if (dwErr == ERROR_SERVICE_ALREADY_RUNNING) {
            printf("Service '%s' is already running.\n", SERVICE_NAME);
        } else {
            printf("Failed to start service. Error: %lu\n", dwErr);
        }
    }

    CloseServiceHandle(hService);
    CloseServiceHandle(hSCM);
}

static void StopServiceCmd(void) {
    SC_HANDLE hSCM = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
    if (!hSCM) {
        printf("Failed to open Service Control Manager. Error: %lu\n", GetLastError());
        return;
    }

    SC_HANDLE hService = OpenServiceA(hSCM, SERVICE_NAME, SERVICE_STOP);
    if (!hService) {
        printf("Failed to open service. Error: %lu\n", GetLastError());
        CloseServiceHandle(hSCM);
        return;
    }

    SERVICE_STATUS status;
    if (ControlService(hService, SERVICE_CONTROL_STOP, &status)) {
        printf("Service '%s' stop signal sent successfully.\n", SERVICE_NAME);
    } else {
        printf("Failed to stop service. Error: %lu\n", GetLastError());
    }

    CloseServiceHandle(hService);
    CloseServiceHandle(hSCM);
}

int main(int argc, char *argv[]) {
    if (argc > 1) {
        if (_stricmp(argv[1], "install") == 0 || _stricmp(argv[1], "-install") == 0 || _stricmp(argv[1], "--install") == 0) {
            InstallServiceCmd();
            return 0;
        } else if (_stricmp(argv[1], "remove") == 0 || _stricmp(argv[1], "uninstall") == 0 ||
                   _stricmp(argv[1], "-remove") == 0 || _stricmp(argv[1], "--uninstall") == 0) {
            RemoveServiceCmd();
            return 0;
        } else if (_stricmp(argv[1], "start") == 0 || _stricmp(argv[1], "-start") == 0 || _stricmp(argv[1], "--start") == 0) {
            StartServiceCmd();
            return 0;
        } else if (_stricmp(argv[1], "stop") == 0 || _stricmp(argv[1], "-stop") == 0 || _stricmp(argv[1], "--stop") == 0) {
            StopServiceCmd();
            return 0;
        }
    }

    SERVICE_TABLE_ENTRYA ServiceTable[] = {
        { SERVICE_NAME, (LPSERVICE_MAIN_FUNCTIONA)ServiceMain },
        { NULL, NULL }
    };

    if (!StartServiceCtrlDispatcherA(ServiceTable)) {
        DWORD dwErr = GetLastError();
        if (dwErr == ERROR_FAILED_SERVICE_CONTROLLER_CONNECT) {
            printf("PAM-RDP-Connect Service\n");
            printf("Usage: %s [install | remove | start | stop]\n", argv[0]);
        }
    }

    return 0;
}
