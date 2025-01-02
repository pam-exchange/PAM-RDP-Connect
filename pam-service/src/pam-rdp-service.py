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

class PAMRDPService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PAM-RDP-SERVICE"
    _svc_display_name_ = "PAM RDP Service"
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
        self.config.read(os.path.join(os.path.dirname(__file__), 'pam-rdp-service.properties'))
        #self.config.read('c:/tmp/pam-rdp-service.properties')
        
        self.setup_logging()
        self.allowed_client = self.config.get('Service', 'allowed_client')
        
        self.hosts_file_path = r"C:\Windows\System32\drivers\etc\hosts"
        self.backup_hosts_file_path = self.hosts_file_path + ".bak"

    def setup_logging(self):
        try:
            #log_file = self.config.get('Logging', 'logfile', fallback=r'c:\Windows\Temp\pam-rdp-service.log')
            log_file = self.config.get('Logging', 'logfile', fallback=r'c:\tmp\pam-rdp-service.log')
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
        self.logger.info("Starting service...")
        self.backup_hosts_file()

        self.logger.debug(f"create named pipe")
        # When running as a service, we must use special security for the pipe
        sa = pywintypes.SECURITY_ATTRIBUTES()
        # Say we do have a DACL, and it is empty
        # (ie, allow full access!)
        sa.SetSecurityDescriptorDacl ( 1, None, 0 )
        
        handle= win32pipe.CreateNamedPipe(
            self.pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX | win32file.FILE_FLAG_OVERLAPPED,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            win32pipe.PIPE_UNLIMITED_INSTANCES,
            65536, 65536, 0, 
            sa
        )
        self.logger.debug(f"pipe handle= {handle}")
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
            
            self.logger.debug(f"Wait for multiple events")
            rc= win32event.WaitForMultipleObjects(waitHandles, 0, timeout)
            
            if rc==win32event.WAIT_OBJECT_0:
                # stop event
                self.logger.debug(f"Stop event received")
                break
            else:
                # Pipe event - read the data, process command and response
                self.logger.debug(f"Pipe event received")
                try:
                    result, data = win32file.ReadFile(handle, 64 * 1024)
                    self.logger.debug(f"ReadFile, result= {result}")
                    if data:
                        command = data.decode('ascii').strip()
                        self.logger.debug(f"command received: {command}")
                        self.semaphore.acquire()
                        response = self.process_command(command)
                        win32file.WriteFile(handle, response.encode('ascii'))
                        self.semaphore.release()
                    self.logger.debug(f"DisconnectNamedPipe")
                    win32pipe.DisconnectNamedPipe(handle)
                except win32file.error:
                    # Client disconnected without sending data
                    # or before reading the response
                    # Thats OK - just get the next connection
                    self.logger.debug(f"client closed connection")


    def process_command(self, command):
        #client_filename = os.path.basename(command.split()[-1])
        #if not self.is_valid_client(client_filename):
        #    return "ERROR: Unauthorized client"
        
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
        self.logger.info(f"removed entry from hosts file: {ip} {hostname}")

    def is_valid_client(self, client_filename):
        self.logger.debug(f"client_filename= {client_filename}")
        return 1==1

    def backup_hosts_file(self):
        if os.path.exists(self.hosts_file_path):
            shutil.copy(self.hosts_file_path, self.backup_hosts_file_path)
            self.logger.info(f"copy file {self.hosts_file_path} --> {self.backup_hosts_file_path}")
        else:
            self.logger.debug("no hosts file found")

    def restore_hosts_file(self):
        if os.path.exists(self.backup_hosts_file_path):
            shutil.copy(self.backup_hosts_file_path, self.hosts_file_path)
            self.logger.info(f"copy file {self.backup_hosts_file_path} --> {self.hosts_file_path}")
        else:
            self.logger.debug("no hosts backup found")

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
        self.logger.info(f"added '{hostname}' to registry.")

    def remove_from_registry(self, hostname):
        key = r"Software\Microsoft\Terminal Server Client\LocalDevices"
        reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(reg_key, hostname)
        winreg.CloseKey(reg_key)
        self.logger.info(f"removed '{hostname}' from registry.")

if __name__ == '__main__':
    #win32serviceutil.HandleCommandLine(PAMRDPService)
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PAMRDPService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PAMRDPService)
    
    