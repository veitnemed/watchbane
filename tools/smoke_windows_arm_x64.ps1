<#
.SYNOPSIS
Verify a disposable x64 Watchbane build on a hosted Windows 11 ARM64 client.

.DESCRIPTION
Build separately on that same runner using an x64 Python 3.13 interpreter
(e.g. actions/setup-python with architecture: x64) and the normal build script.
This consumes the resulting onedir bundle directly: no upload, ZIP, download,
model, catalog, user profile, or installer. It does not certify a separately
built x64 artifact, a clean consumer machine, or native ARM64 support.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $BundleDirectory,
    [ValidateSet('lexical', 'semantic')]
    [string] $BundleProfile = 'semantic'
)

$ErrorActionPreference = 'Stop'
if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
        [System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw 'This check requires Windows 11 ARM64.'
}
# Win32 reports native machine type even from an emulated PowerShell process.
# Avoid identifying the host from PROCESSOR_ARCHITECTURE or the runner label.
if (-not ('WatchbaneArmQaNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WatchbaneArmQaNative {
    [DllImport("kernel32.dll", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWow64Process2(IntPtr process, out ushort processMachine, out ushort nativeMachine);
    [DllImport("kernel32.dll")]
    public static extern IntPtr GetCurrentProcess();
}
'@
}
[uint16] $processMachine = 0
[uint16] $nativeMachine = 0
if (-not [WatchbaneArmQaNative]::IsWow64Process2(
        [WatchbaneArmQaNative]::GetCurrentProcess(), [ref]$processMachine, [ref]$nativeMachine) -or
    $nativeMachine -ne 0xaa64) {
    throw 'Native ARM64 was not observed.'
}
$os = Get-CimInstance -ClassName Win32_OperatingSystem
if ($os.ProductType -ne 1 -or [int]$os.BuildNumber -lt 22000 -or
    $os.Caption -notmatch '\bWindows 11\b') {
    throw 'A Windows 11 client edition was not observed.'
}

$bundle = (Resolve-Path -LiteralPath $BundleDirectory).Path
$exe = Join-Path $bundle 'Watchbane.exe'
$stream = [System.IO.File]::OpenRead($exe)
$reader = [System.IO.BinaryReader]::new($stream)
try {
    if ($stream.Length -lt 70 -or $reader.ReadUInt16() -ne 0x5a4d) {
        throw 'The bundle executable lacks a valid DOS header.'
    }
    $stream.Position = 0x3c
    $pe = $reader.ReadUInt32()
    if ($pe -lt 64 -or $pe -gt ($stream.Length - 26)) {
        throw 'The bundle executable lacks a valid PE offset.'
    }
    $stream.Position = $pe
    if ($reader.ReadUInt32() -ne 0x00004550 -or $reader.ReadUInt16() -ne 0x8664) {
        throw 'The bundle is not a Windows x64 PE.'
    }
    $stream.Position = $pe + 24
    if ($reader.ReadUInt16() -ne 0x020b) {
        throw 'The bundle executable lacks a PE32+ optional header.'
    }
}
finally {
    $reader.Dispose()
    $stream.Dispose()
}
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Write-Output "Confirmed Windows 11 client (build $($os.BuildNumber)), native ARM64; x64 PE SHA-256 $hash."
# Existing smoke hard-isolates to a new temp profile, strips PATH to System32,
# and uses a synthetic ONNX graph rather than real E5 weights.
& (Join-Path $PSScriptRoot 'smoke_windows_bundle.ps1') -BundleDirectory $bundle -BundleProfile $BundleProfile
Write-Output 'Confirmed that this x64 PE started under emulation on this hosted image (not a clean-user or native ARM64 test).'
