#!/bin/env python


import time
import sys

sys.path.insert(0, '.')

import kunai.misc.wmi as wmi
import _winreg

t0 = time.time()
c = wmi.WMI()
t1 = time.time()
print "WMI TIME", t1 - t0


_os = c.Win32_OperatingSystem(Primary=1)[0]

_os = getattr(c, "Win32_OperatingSystem")
d = {'Primary':1}
_os = _os(**d)
_os = _os[0]
print _os.Caption

features = c.Win32_ServerFeature()
for f in features:
    print f
    
fuck

'''
print "PROCESS"
t0 = time.time()
for process in c.Win32_Process():
  print process.ProcessId, process.Name
t1 = time.time()
print "Process time: %s" % (t1 - t0)
'''
# Ex de rendu:
'''
instance of Win32_Process
{
        Caption = "python.exe";
        CommandLine = "c:\\Python27\\python.exe  spike\\test_wmi.py";
        CreationClassName = "Win32_Process";
        CreationDate = "20151213204307.717339+060";
        CSCreationClassName = "Win32_ComputerSystem";
        CSName = "WJGABES";
        Description = "python.exe";
        ExecutablePath = "c:\\Python27\\python.exe";
        Handle = "7384";
        HandleCount = 164;
        KernelModeTime = "1248008";
        MaximumWorkingSetSize = 1380;
        MinimumWorkingSetSize = 200;
        Name = "python.exe";
        OSCreationClassName = "Win32_OperatingSystem";
        OSName = "Microsoft Windows 7 Professionnel |C:\\Windows|\\Device\\Hardd
isk0\\Partition3";
        OtherOperationCount = "2118";
        OtherTransferCount = "51102";
        PageFaults = 4363;
        PageFileUsage = 10384;
        ParentProcessId = 8056;
        PeakPageFileUsage = 10384;
        PeakVirtualSize = "101343232";
        PeakWorkingSetSize = 16792;
        Priority = 8;
        PrivatePageCount = "10633216";
        ProcessId = 7384;
        QuotaNonPagedPoolUsage = 14;
        QuotaPagedPoolUsage = 156;
        QuotaPeakNonPagedPoolUsage = 14;
        QuotaPeakPagedPoolUsage = 156;
        ReadOperationCount = "414";
        ReadTransferCount = "727404";
        SessionId = 1;
        ThreadCount = 6;
        UserModeTime = "0";
        VirtualSize = "101343232";
        WindowsVersion = "6.1.7601";
        WorkingSetSize = "17195008";
        WriteOperationCount = "0";
        WriteTransferCount = "0";
};
'''


#print c.Win32_Process.Create



####Auto services
print "#####"*200
print "SERVICES"
print "#####"*200
stopped_services = c.Win32_Service(StartMode="Auto", State="Stopped")
if stopped_services:
    for s in stopped_services:
        print s.Caption, "service is not running"
else:
    print "No auto services stopped"

# ex de rendu:
'''
Microsoft .NET Framework NGEN v4.0.30319_X86 service is not running

instance of Win32_Service
{
        AcceptPause = FALSE;
        AcceptStop = FALSE;
        Caption = "Microsoft .NET Framework NGEN v4.0.30319_X86";
        CheckPoint = 0;
        CreationClassName = "Win32_Service";
        Description = "Microsoft .NET Framework NGEN";
        DesktopInteract = FALSE;
        DisplayName = "Microsoft .NET Framework NGEN v4.0.30319_X86";
        ErrorControl = "Ignore";
        ExitCode = 0;
        Name = "clr_optimization_v4.0.30319_32";
        PathName = "C:\\Windows\\Microsoft.NET\\Framework\\v4.0.30319\\mscorsvw.
exe";
        ProcessId = 0;
        ServiceSpecificExitCode = 0;
        ServiceType = "Own Process";
        Started = FALSE;
        StartMode = "Auto";
        StartName = "LocalSystem";
        State = "Stopped";
        Status = "OK";
        SystemCreationClassName = "Win32_ComputerSystem";
        SystemName = "WJGABES";
        TagId = 0;
        WaitHint = 0;
};
'''



####### Disks
print "#####"*200
print "DISKS"
print "#####"*200

for disk in c.Win32_LogicalDisk (DriveType=3):
    print disk.Caption, "%0.2f%% free" % (100.0 * long (disk.FreeSpace) / long (disk.Size))

for disk in c.Win32_LogicalDisk ():
    try:
        print disk.Caption, "%0.2f%% free" % (100.0 * long (disk.FreeSpace) / long (disk.Size))
        print disk
    except:
        pass
# ex de rendu du disk
'''
instance of Win32_LogicalDisk
{
        Access = 0;
        Caption = "C:";
        Compressed = FALSE;
        CreationClassName = "Win32_LogicalDisk";
        Description = "Disque fixe local";
        DeviceID = "C:";
        DriveType = 3;
        FileSystem = "NTFS";
        FreeSpace = "28736724992";
        MaximumComponentLength = 255;
        MediaType = 12;
        Name = "C:";
        Size = "483692376064";
        SupportsDiskQuotas = FALSE;
        SupportsFileBasedCompression = TRUE;
        SystemCreationClassName = "Win32_ComputerSystem";
        SystemName = "WJGABES";
        VolumeName = "OS";
        VolumeSerialNumber = "28EE1226";
};
'''


########## OK
print "#####"*200
print "OK"
print "#####"*200
os = c.Win32_OperatingSystem (Primary=1)[0]
print os
print os.Caption
fuck
# rendu
'''
instance of Win32_OperatingSystem
{
        BootDevice = "\\Device\\HarddiskVolume2";
        BuildNumber = "7601";
        BuildType = "Multiprocessor Free";
        Caption = "Microsoft Windows 7 Professionnel ";
        CodeSet = "1252";
        CountryCode = "33";
        CreationClassName = "Win32_OperatingSystem";
        CSCreationClassName = "Win32_ComputerSystem";
        CSDVersion = "Service Pack 1";
        CSName = "WJGABES";
        CurrentTimeZone = 60;
        DataExecutionPrevention_32BitApplications = TRUE;
        DataExecutionPrevention_Available = TRUE;
        DataExecutionPrevention_Drivers = TRUE;
        DataExecutionPrevention_SupportPolicy = 2;
        Debug = FALSE;
        Description = "";
        Distributed = FALSE;
        EncryptionLevel = 256;
        ForegroundApplicationBoost = 2;
        FreePhysicalMemory = "3508224";
        FreeSpaceInPagingFiles = "8147932";
        FreeVirtualMemory = "11404200";
        InstallDate = "20130805130427.000000+120";
        LastBootUpTime = "20151213140126.109999+060";
        LocalDateTime = "20151213205533.991000+060";
        Locale = "040c";
        Manufacturer = "Microsoft Corporation";
        MaxNumberOfProcesses = 4294967295;
        MaxProcessMemorySize = "8589934464";
        MUILanguages = {"fr-FR"};
        Name = "Microsoft Windows 7 Professionnel |C:\\Windows|\\Device\\Harddis
k0\\Partition3";
        NumberOfProcesses = 104;
        NumberOfUsers = 2;
        OperatingSystemSKU = 48;
        Organization = "Microsoft";
        OSArchitecture = "64 bits";
        OSLanguage = 1036;
        OSProductSuite = 256;
        OSType = 18;
        Primary = TRUE;
        ProductType = 1;
        RegisteredUser = "j.gabes";
        SerialNumber = "00371-OEM-8992671-00524";
        ServicePackMajorVersion = 1;
        ServicePackMinorVersion = 0;
        SizeStoredInPagingFiles = "8260972";
        Status = "OK";
        SuiteMask = 272;
        SystemDevice = "\\Device\\HarddiskVolume3";
        SystemDirectory = "C:\\Windows\\system32";
        SystemDrive = "C:";
        TotalVirtualMemorySize = "16520108";
        TotalVisibleMemorySize = "8260972";
        Version = "6.1.7601";
        WindowsDirectory = "C:\\Windows";
};
'''


##### NETWORK
print "#####"*200
print "NETWORK"
print "#####"*200

for interface in c.Win32_NetworkAdapterConfiguration (IPEnabled=1):
    print interface.Description, interface.MACAddress
    for ip_address in interface.IPAddress:
        print ip_address
    print interface
    print "\n\n"

# rendu
'''
Dell Wireless 1704 802.11b/g/n (2,4 GHz) 9C:2A:70:D9:48:93
192.168.0.44

instance of Win32_NetworkAdapterConfiguration
{
        Caption = "[00000011] Dell Wireless 1704 802.11b/g/n (2,4 GHz)";
        DatabasePath = "%SystemRoot%\\System32\\drivers\\etc";
        DefaultIPGateway = {"192.168.0.254"};
        Description = "Dell Wireless 1704 802.11b/g/n (2,4 GHz)";
        DHCPEnabled = TRUE;
        DHCPLeaseExpires = "20151214020200.000000+060";
        DHCPLeaseObtained = "20151213140200.000000+060";
        DHCPServer = "192.168.0.254";
        DNSDomainSuffixSearchOrder = {"eu.lectra.com", "home"};
        DNSEnabledForWINSResolution = FALSE;
        DNSHostName = "WJGABES";
        DNSServerSearchOrder = {"8.8.4.4"};
        DomainDNSRegistrationEnabled = FALSE;
        FullDNSRegistrationEnabled = TRUE;
        GatewayCostMetric = {0};
        Index = 11;
        InterfaceIndex = 12;
        IPAddress = {"192.168.0.44"};
        IPConnectionMetric = 25;
        IPEnabled = TRUE;
        IPFilterSecurityEnabled = FALSE;
        IPSecPermitIPProtocols = {};
        IPSecPermitTCPPorts = {};
        IPSecPermitUDPPorts = {};
        IPSubnet = {"255.255.255.0"};
        MACAddress = "9C:2A:70:D9:48:93";
        ServiceName = "BCM43XX";
        SettingID = "{6693BF9A-3976-479D-BA8C-08ABAD1F70B5}";
        TcpipNetbiosOptions = 0;
        WINSEnableLMHostsLookup = TRUE;
        WINSScopeID = "";
};
'''



### startup
print "#####"*200
print "Startup"
print "#####"*200
for s in c.Win32_StartupCommand ():
  print "[%s] %s <%s>" % (s.Location, s.Caption, s.Command)




##### logs
print "#####"*200
print "LOGS"
print "#####"*200

'''
c2 = wmi.WMI (privileges=["Security"])

watcher = c2.watch_for (
  notification_type="Creation",
  wmi_class="Win32_NTLogEvent",
  Type="error"
)
while 1:
    print 'go'
    error = watcher ()
    print "Error in %s log: %s" %  (error.Logfile, error.Message)
    # send mail to sysadmin etc.
'''

### Registry
print "#####"*200
print "REGISTRY"
print "#####"*200
r = wmi.Registry()
try:
    result, names = r.EnumKey(
    hDefKey=_winreg.HKEY_LOCAL_MACHINE,
    sSubKeyName="Software"
    )
    for key in names:
        print 'Registry', key
except Exception, exp:
    print "FUCK", exp



####Shared
print '\n\n\n'
print "#####"*200
print "SHARE"
print "#####"*200
for share in c.Win32_Share ():
  print 'Share:', share.Name, share.Path


#### Print
print "#####"*200
print "printer"
print "#####"*200
for printer in c.Win32_Printer ():
    print printer.Caption
    for job in c.Win32_PrintJob (DriverName=printer.DriverName):
        print "  ", job.Document
    try:
        print printer
    except:
        pass
    print
# rendu:
'''
Dell B1165nfw Network PC Fax

instance of Win32_Printer
{
        Attributes = 18496;
        AveragePagesPerMinute = 0;
        Capabilities = {4};
        CapabilityDescriptions = {"Copies"};
        Caption = "Dell B1165nfw Network PC Fax";
        CreationClassName = "Win32_Printer";
        Default = FALSE;
        DefaultPriority = 0;
        DetectedErrorState = 0;
        DeviceID = "Dell B1165nfw Network PC Fax";
        Direct = FALSE;
        DoCompleteFirst = FALSE;
        DriverName = "Dell B1165nfw Network PC Fax";
        EnableBIDI = TRUE;
        EnableDevQueryPrint = FALSE;
        ExtendedDetectedErrorState = 0;
        ExtendedPrinterStatus = 2;
        Hidden = FALSE;
        HorizontalResolution = 202;
        JobCountSinceLastReset = 0;
        KeepPrintedJobs = FALSE;
        Local = TRUE;
        Name = "Dell B1165nfw Network PC Fax";
        Network = FALSE;
        PaperSizesSupported = {22, 21, 54, 7, 8};
        PortName = "Dell B1165nfw Network PC Fax Port";
        PrinterPaperNames = {"A4", "A3", "B4", "Letter", "Legal"};
        PrinterState = 0;
        PrinterStatus = 3;
        PrintJobDataType = "RAW";
        PrintProcessor = "Dell B1165nfw Network PC Fax Print Processor";
        Priority = 1;
        Published = FALSE;
        Queued = FALSE;
        RawOnly = FALSE;
        Shared = FALSE;
        SpoolEnabled = TRUE;
        Status = "Unknown";
        SystemCreationClassName = "Win32_ComputerSystem";
        SystemName = "WJGABES";
        VerticalResolution = 196;
        WorkOffline = FALSE;
};
'''

### Phys disks:
print "#####"*200
print "Phy disks"
print "#####"*200
for physical_disk in c.Win32_DiskDrive ():
  for partition in physical_disk.associators ("Win32_DiskDriveToDiskPartition"):
    for logical_disk in partition.associators ("Win32_LogicalDiskToPartition"):
      print 'Disks:', physical_disk.Caption, partition.Caption, logical_disk.Caption


# Rendu:
# physical
'''
instance of Win32_DiskDrive
{
        BytesPerSector = 512;
        Capabilities = {3, 4};
        CapabilityDescriptions = {"Random Access", "Supports Writing"};
        Caption = "ATA HGST HTS725050A7 SCSI Disk Device";
        ConfigManagerErrorCode = 0;
        ConfigManagerUserConfig = FALSE;
        CreationClassName = "Win32_DiskDrive";
        Description = "Lecteur de disque";
        DeviceID = "\\\\.\\PHYSICALDRIVE0";
        FirmwareRevision = "A560";
        Index = 0;
        InterfaceType = "IDE";
        Manufacturer = "(Lecteurs de disque standard)";
        MediaLoaded = TRUE;
        MediaType = "Fixed hard disk media";
        Model = "ATA HGST HTS725050A7 SCSI Disk Device";
        Name = "\\\\.\\PHYSICALDRIVE0";
        Partitions = 3;
        PNPDeviceID = "SCSI\\DISK&VEN_ATA&PROD_HGST_HTS725050A7\\4&9DA7362&0&000
000";
        SCSIBus = 0;
        SCSILogicalUnit = 0;
        SCSIPort = 0;
        SCSITargetId = 0;
        SectorsPerTrack = 63;
        SerialNumber = "      TF755AWHHX1X0M";
        Signature = 849034240;
        Size = "500105249280";
        Status = "OK";
        SystemCreationClassName = "Win32_ComputerSystem";
        SystemName = "WJGABES";
        TotalCylinders = "60801";
        TotalHeads = 255;
        TotalSectors = "976768065";
        TotalTracks = "15504255";
        TracksPerCylinder = 255;
};
'''

# logical disks
'''
instance of Win32_LogicalDisk
{
        Access = 0;
        Caption = "C:";
        Compressed = FALSE;
        CreationClassName = "Win32_LogicalDisk";
        Description = "Disque fixe local";
        DeviceID = "C:";
        DriveType = 3;
        FileSystem = "NTFS";
        FreeSpace = "28735606784";
        MaximumComponentLength = 255;
        MediaType = 12;
        Name = "C:";
        Size = "483692376064";
        SupportsDiskQuotas = FALSE;
        SupportsFileBasedCompression = TRUE;
        SystemCreationClassName = "Win32_ComputerSystem";
        SystemName = "WJGABES";
        VolumeName = "OS";
        VolumeSerialNumber = "28EE1226";
};
'''

#####Scheduled jobs
print "#####"*200
print "SCHEDULED"
print "#####"*200
for job in c.Win32_ScheduledJob():
    print 'Scheduled job', job


### drive types
print "#####"*200
print "DRIVE TYPE"
print "#####"*200
DRIVE_TYPES = {
  0 : "Unknown",
  1 : "No Root Directory",
  2 : "Removable Disk",
  3 : "Local Disk",
  4 : "Network Drive",
  5 : "Compact Disc",
  6 : "RAM Disk"
}
for drive in c.Win32_LogicalDisk ():
  print 'Drive', drive.Caption, DRIVE_TYPES[drive.DriveType]

'''
### Dans un thread
import pythoncom
import threading

class Info(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)


    def run(self):
        print 'In Another Thread...'
        pythoncom.CoInitialize()
        try:
            c = wmi.WMI()
            for i in range(5):
                for process in c.Win32_Process():
                    print process.ProcessId, process.Name
                time.sleep(2)
        finally:
            pythoncom.CoUninitialize()


for process in c.Win32_Process():
    print process.ProcessId, process.Name
Info().start()
'''

