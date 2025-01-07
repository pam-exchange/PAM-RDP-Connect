import servicemanager
import win32serviceutil
import win32service
import win32event
import win32pipe
import win32file
import win32api
import win32security
import win32timezone
import winreg
import pywintypes
import winerror
import os
import logging
from threading import Semaphore
import configparser
import shutil
import time
import psutil

# # Use "import *" to keep this looking as much as a "normal" service
# as possible.  Real code shouldn't do this.
from ntsecuritycon import *  # nopycln: import

class PAMRDPService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PAM-RDP-CONNECT-SERVICE"
    _svc_display_name_ = "PAM-RDP-Connect Service"
    _svc_description_ = "Service to add or remove entries from hosts file via named pipe."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # Create an event which we will use to wait on.
        # The "service stop" request will set this event.
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        # We need to use overlapped IO for this, so we dont block when
        # waiting for a client to connect.  This is the only effective way
        # to handle either a client connection, or a service stop request.
        self.overlapped = pywintypes.OVERLAPPED()
        # And create an event to be used in the OVERLAPPED object.
        self.overlapped.hEvent = win32event.CreateEvent(None,0,0,None)

        self.pipe_name = r'\\.\pipe\PAM-RDP-SERVICE'
        self.semaphore = Semaphore(1)

        self.config = configparser.ConfigParser()
        self.configFilename= os.path.join(os.path.split(sys.executable)[0], 'pam-rdp-service.properties')
        self.config.read(self.configFilename)
        
        self.setup_logging()
        self.allowed_client = self.config.get('Service', 'allowed_client', fallback=r'C:\Program Files\PAM-Exchange\PAM-RDP-Connect\pam-rdp.exe')
        
        self.hosts_file_path = r"C:\Windows\System32\drivers\etc\hosts"
        self.backup_hosts_file_path = self.hosts_file_path + ".bak"

        # Log configuration
        self.logger.debug(f"Configuration: configFilename= {self.configFilename}")
        self.logger.debug(f"Configuration: allowed_client= {self.allowed_client}")

    def setup_logging(self):
        try:
            log_file = self.config.get('Logging', 'logfile', fallback=r'c:\Windows\Temp\pam-rdp-service.log')
            log_level = self.config.get('Logging', 'loglevel', fallback='DEBUG').upper()
            if not log_level in ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                log_level= 'DEBUG'
            log_format = self.config.get('Logging', 'logformat', fallback='[%(asctime)s - %(levelname)s] %(message)s (%(process)s/%(funcName)s - %(lineno)s)')
        except Exception as e:
            log_file = r'c:\Windows\Temp\pam-rdp-service.log'
            log_level = 'DEBUG'
            log_format = '[%(asctime)s - %(levelname)s] %(message)s (%(process)s/%(funcName)s - %(lineno)s)'
            
        logging.basicConfig(filename=log_file, level=getattr(logging, log_level), format=log_format)
        self.logger = logging.getLogger(self._svc_name_)

    def SvcStop(self):
        self.logger.info("Stopping service...")
        # Before we do anything, tell the SCM we are starting the stop process.
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

        self.restore_hosts_file()

        # And set my event.
        win32event.SetEvent(self.hWaitStop)
        self.logger.debug(f"Service stopped")

    def SvcDoRun(self):
        self.logger.info(f"Starting service...")
        self.backup_hosts_file()

        # Create security attribute for named pipe
        self.logger.debug(f"create security attribute")
        sa= self.CreatePipeSecurityObject()

        # Create named pipe
        #
        # The pipe will reject conections from remote clients
        #
        self.logger.debug(f"create named pipe")
        handle= win32pipe.CreateNamedPipe(
            self.pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX | win32file.FILE_FLAG_OVERLAPPED,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT | win32pipe.PIPE_REJECT_REMOTE_CLIENTS,
            win32pipe.PIPE_UNLIMITED_INSTANCES,
            65536, 65536, 0, 
            sa
        )

        while True:
            try:
                hr= win32pipe.ConnectNamedPipe(handle, self.overlapped)
            except Exception as e:
                self.logger.debug(f"Error connecting pipe")
                handle.Close()
                break
                
            if hr==winerror.ERROR_PIPE_CONNECTED:
                # Client is fast, and already connected - signal event
                self.logger.debug(f"Client is fast, hr= {hr}")
                win32event.SetEvent(self.overlapped.hEvent)
                
            # Wait for either a connection, or a service stop request
            timeout= win32event.INFINITE
            waitHandles= self.hWaitStop, self.overlapped.hEvent
            
            #
            # Wait for an event on the pipe. Events can be (service) STOP or some PipeEvent.
            self.logger.debug(f"Wait for multiple events")
            rc= win32event.WaitForMultipleObjects(waitHandles, 0, timeout)
            
            if rc==win32event.WAIT_OBJECT_0:
                self.logger.debug(f"Stop event received")
                break
            else:
                self.logger.debug(f"Pipe event received")
                try:
                    result, data = win32file.ReadFile(handle, 64 * 1024)
                    self.logger.debug(f"ReadFile, result= {result}")
                    if data:
                        command = data.decode('ascii').strip()
                        self.logger.debug(f"Command received: {command}")
                        
                        # Process commands one at a time by using a semaphore                        
                        self.logger.debug(f"Acquire Semaphore")
                        self.semaphore.acquire()
                        self.logger.debug(f"Semaphore acquired")
                        
                        response = self.process_command(command)
                        self.logger.debug(f"Response from process_command: {response}")
                        win32file.WriteFile(handle, response.encode('ascii'))
                                                
                        self.semaphore.release()
                        self.logger.debug(f"Seemaphore released")
                        
                    self.logger.debug(f"DisconnectNamedPipe")
                    win32pipe.DisconnectNamedPipe(handle)
                except win32file.error:
                    # Client disconnected without sending data
                    # or before reading the response
                    # Thats OK - just get the next connection
                    self.logger.debug(f"client closed connection")

    def CreatePipeSecurityObject(self):
        # Create a security object giving World read/write access,
        # but only "Owner" modify access.
        sa = pywintypes.SECURITY_ATTRIBUTES()
        sidEveryone = pywintypes.SID()
        sidEveryone.Initialize(SECURITY_WORLD_SID_AUTHORITY, 1)
        sidEveryone.SetSubAuthority(0, SECURITY_WORLD_RID)
        sidCreator = pywintypes.SID()
        sidCreator.Initialize(SECURITY_CREATOR_SID_AUTHORITY, 1)
        sidCreator.SetSubAuthority(0, SECURITY_CREATOR_OWNER_RID)

        acl = pywintypes.ACL()
        acl.AddAccessAllowedAce(FILE_GENERIC_READ | FILE_GENERIC_WRITE, sidEveryone)
        acl.AddAccessAllowedAce(FILE_ALL_ACCESS, sidCreator)

        sa.SetSecurityDescriptorDacl(1, acl, 0)
        return sa

    def process_command(self, command):
        if not self.is_valid_client():
            return "ERROR: Unauthorized client"
        
        try:
            parts = command.lower().split()
            if len(parts) != 3:
                self.logger.error(f"Invalid command received. command= {command}")
                return "ERROR: Invalid command format"

            action, ip, hostname = parts
            if action == "add":
                self.logger.debug(f"adding ip={ip} hostname={hostname}")
                self.add_to_registry(hostname)
                self.add_to_hosts(ip, hostname)
                return f"OK: {ip} {hostname} added"
            elif action == "remove":
                self.logger.debug(f"removing ip={ip} hostname={hostname}")
                self.remove_from_registry(hostname)
                self.remove_from_hosts(ip, hostname)
                return f"OK: {ip} {hostname} removed"
            else:
                self.logger.error(f"Unknown command: {command}")
                return "ERROR: Unknown command"
        except Exception as e:
            self.logger.error(f"Error processing command: {str(e)}")
            return f"ERROR: {str(e)}"

    def add_to_hosts(self, ip, hostname):
        encoding = self.detect_encoding(self.hosts_file_path)
        with open(self.hosts_file_path, 'a', encoding=encoding) as hosts_file:
            hosts_file.write(f"{ip}\t{hostname}\n")
        self.logger.info(f"Added entry to hosts file: {ip} {hostname}")

    def remove_from_hosts(self, ip, hostname):
        encoding = self.detect_encoding(self.hosts_file_path)
        with open(self.hosts_file_path, 'r', encoding=encoding) as hosts_file:
            lines = hosts_file.readlines()
        with open(self.hosts_file_path, 'w', encoding=encoding) as hosts_file:
            for line in lines:
                if not (line.startswith(ip) and hostname in line):
                    hosts_file.write(line)
        self.logger.info(f"Removed entry from hosts file: {ip} {hostname}")

    def is_valid_client(self):
        for proc in psutil.process_iter(['pid', 'exe']):
            try:
                #self.logger.debug(f"process - {proc.info['exe']}")
                if proc.info['exe'] and proc.info['exe'].lower() == self.allowed_client.lower():
                    self.logger.debug(f"Calling client - OK")
                    return True
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
        self.logger.debug(f"Calling client - Not OK")
        return False

    def backup_hosts_file(self):
        if os.path.exists(self.hosts_file_path):
            shutil.copy(self.hosts_file_path, self.backup_hosts_file_path)
            self.logger.info(f"Copy file {self.hosts_file_path} --> {self.backup_hosts_file_path}")
        else:
            self.logger.debug("No hosts file found")

    def restore_hosts_file(self):
        if os.path.exists(self.backup_hosts_file_path):
            shutil.copy(self.backup_hosts_file_path, self.hosts_file_path)
            self.logger.info(f"Copy file {self.backup_hosts_file_path} --> {self.hosts_file_path}")
        else:
            self.logger.debug("No hosts backup found")

    def detect_encoding(self, file_path):
        with open(file_path, 'rb') as f:
            raw_data = f.read(4)
        if raw_data.startswith(b'\xff\xfe'):
            return 'utf-16'
        elif raw_data.startswith(b'\xfe\xff'):
            return 'utf-16'
        elif raw_data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        else:
            return 'ascii'

    def add_to_registry(self, hostname):
        key = r"Software\Microsoft\Terminal Server Client\LocalDevices"
        reg_key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key)
        winreg.SetValueEx(reg_key, hostname, 0, winreg.REG_SZ, "1")
        winreg.CloseKey(reg_key)
        self.logger.info(f"Added '{hostname}' to registry.")

    def remove_from_registry(self, hostname):
        key = r"Software\Microsoft\Terminal Server Client\LocalDevices"
        reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(reg_key, hostname)
        winreg.CloseKey(reg_key)
        self.logger.info(f"Removed '{hostname}' from registry.")

if __name__ == '__main__':
    #win32serviceutil.HandleCommandLine(PAMRDPService)
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PAMRDPService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PAMRDPService)
    
    