<#
.SYNOPSIS
  Creates pinnable "Music Downloader" shortcuts (same behavior as run.bat).

.DESCRIPTION
  run.bat can't be pinned to the taskbar directly (Windows pins the cmd.exe
  host instead). This script creates standard .lnk shortcuts that launch
  "pythonw.exe gui.py" with the repo root as working directory, so relative
  paths (Playlists/, .cache/, archives.txt) resolve exactly like run.bat --
  but with no console window and pinnable to the taskbar / Start menu.

  Creates three shortcuts (skips ones it can't write, warns instead):
    - <repo>\Music Downloader.lnk
    - Desktop\Music Downloader.lnk
    - Start Menu\Programs\Music Downloader.lnk  (makes it searchable)

  To pin: right-click any of them -> "Pin to taskbar" (or drag it there).
  Windows blocks scripted pinning, so that last step is manual.

  Run with:  powershell -ExecutionPolicy Bypass -File install_shortcut.ps1
  Re-run after moving the folder or reinstalling Python (paths are absolute).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$AppId = "MusicDownloader.MusicDownloader"
$ShortcutName = "Music Downloader.lnk"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$GuiPath = Join-Path $RepoRoot "gui.py"
$IconPath = Join-Path $RepoRoot "assets\app.ico"

function Find-PythonW {
    # Prefer pythonw.exe sitting next to the `python.exe` on PATH, so the
    # shortcut uses the interpreter that has the dependencies installed.
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        $cand = Join-Path (Split-Path -Parent $cmd.Source) "pythonw.exe"
        if (Test-Path -LiteralPath $cand) { return $cand }
    }
    $w = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($w -and $w.Source) { return $w.Source }
    $base = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path -LiteralPath $base) {
        $best = Get-ChildItem -LiteralPath $base -Directory -Filter "Python3*" |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "pythonw.exe" } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
        if ($best) { return $best }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $GuiPath)) {
    throw "gui.py not found at $GuiPath. Run this script from the repo root."
}

$pythonw = Find-PythonW
if (-not $pythonw) {
    throw "pythonw.exe not found. Install Python 3.12 (with py launcher) and retry."
}
Write-Host "Using: $pythonw"

$useIcon = Test-Path -LiteralPath $IconPath
if (-not $useIcon) {
    Write-Warning "Icon not found at $IconPath (run: python tools/make_icon.py). Falling back to pythonw.exe icon."
}

function New-AppShortcut {
    param([string]$Path)
    # Start fresh: stale/corrupted props from older runs can linger otherwise.
    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Force }
    $shell = New-Object -ComObject WScript.Shell
    try {
        $lnk = $shell.CreateShortcut($Path)
        $lnk.TargetPath = $pythonw
        $lnk.Arguments = "`"$GuiPath`""
        $lnk.WorkingDirectory = $RepoRoot
        $lnk.Description = "Music Downloader"
        $lnk.WindowStyle = 1
        if ($useIcon) { $lnk.IconLocation = "$IconPath,0" }
        $lnk.Save()
    } finally {
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null
    }
}

# Stamp System.AppUserModel.ID on the .lnk so the pinned icon and the running
# window (see gui.py main()) group under a single taskbar icon.
$AppIdSetterCode = @'
using System;
using System.Runtime.InteropServices;

public static class ShortcutAppId
{
    [StructLayout(LayoutKind.Sequential)]
    public struct PROPERTYKEY
    {
        public Guid fmtid;
        public uint pid;
    }

    [ComImport]
    [Guid("00021401-0000-0000-C000-000000000046")]
    private class CShellLink { }

    [ComImport]
    [Guid("0000010b-0000-0000-C000-000000000046")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IPersistFile
    {
        void GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string ppszFileName);
        void IsDirty();
        void Load([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, uint dwMode);
        void Save([MarshalAs(UnmanagedType.LPWStr)] string pszFileName,
                  [MarshalAs(UnmanagedType.Bool)] bool fRemember);
        void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string pszFileName);
    }

    // NOTE: value is marshaled as object (VARIANT) rather than a hand-rolled
    // PROPVARIANT struct: raw PROPVARIANT stubs corrupt adjacent data, while
    // string<->VT_LPWSTR via UnmanagedType.Struct round-trips correctly.
    [ComImport]
    [Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IPropertyStore
    {
        void GetCount(out uint cProps);
        void GetAt(uint iProp, out PROPERTYKEY pkey);
        void GetValue(ref PROPERTYKEY key,
            [MarshalAs(UnmanagedType.Struct)] out object pv);
        void SetValue(ref PROPERTYKEY key,
            [MarshalAs(UnmanagedType.Struct)] object pv);
        void Commit();
    }

    private static PROPERTYKEY AppIdKey()
    {
        return new PROPERTYKEY {
            fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid = 5 };
    }

    public static void Set(string lnkPath, string appId)
    {
        var link = (IPersistFile)new CShellLink();
        link.Load(lnkPath, 2); // STGM_READWRITE
        var store = (IPropertyStore)link;
        try
        {
            var key = AppIdKey();
            store.SetValue(ref key, (object)appId);
            store.Commit();
            link.Save(lnkPath, true);
        }
        finally
        {
            Marshal.ReleaseComObject(store);
        }
    }

    public static string Get(string lnkPath)
    {
        var link = (IPersistFile)new CShellLink();
        link.Load(lnkPath, 0); // STGM_READ
        var store = (IPropertyStore)link;
        try
        {
            var key = AppIdKey();
            object v;
            store.GetValue(ref key, out v);
            return v as string;
        }
        finally { Marshal.ReleaseComObject(store); }
    }
}
'@
Add-Type -TypeDefinition $AppIdSetterCode

$destinations = @(
    (Join-Path $RepoRoot $ShortcutName),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) $ShortcutName),
    (Join-Path (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs") $ShortcutName)
)

$created = @()
foreach ($dest in $destinations) {
    try {
        New-AppShortcut -Path $dest
        try {
            [ShortcutAppId]::Set($dest, $AppId)
        } catch {
            Write-Warning "Created $dest but could not stamp AppUserModelID: $($_.Exception.Message)"
        }
        $created += $dest
        Write-Host "Created: $dest"
    } catch {
        Write-Warning "Skipped $dest : $($_.Exception.Message)"
    }
}

if ($created.Count -eq 0) { throw "No shortcuts were created." }

# Verify: read back shortcut fields + AppUserModelID.
$shell = New-Object -ComObject WScript.Shell
try {
    foreach ($dest in $created) {
        $lnk = $shell.CreateShortcut($dest)
        $id = $null
        try { $id = [ShortcutAppId]::Get($dest) } catch { $id = "<unreadable: $($_.Exception.Message)>" }
        Write-Host ""
        Write-Host "  $dest"
        Write-Host "    target : $($lnk.TargetPath) $($lnk.Arguments)"
        Write-Host "    workdir: $($lnk.WorkingDirectory)"
        Write-Host "    icon   : $($lnk.IconLocation)"
        Write-Host "    appid  : $id"
        if ($lnk.TargetPath -ne $pythonw) { Write-Warning "    target mismatch!" }
        if ($lnk.WorkingDirectory -ne $RepoRoot) { Write-Warning "    working-directory mismatch!" }
        if ($id -ne $AppId) { Write-Warning "    AppUserModelID mismatch (taskbar may show two icons)!" }
    }
} finally {
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null
}

Write-Host ""
Write-Host "Done. To pin: right-click a shortcut -> 'Pin to taskbar' (or drag it there)."
