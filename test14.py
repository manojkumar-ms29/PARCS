import subprocess

script = """
$ErrorActionPreference = 'Stop'
Get-WmiObject Win32_PnPSignedDriver | Select-Object @(
    @{Name='device_name'; Expression={$_.DeviceName}},
    @{Name='friendly_name'; Expression={$_.FriendlyName}},
    @{Name='provider'; Expression={$_.Manufacturer}},
    @{Name='version'; Expression={$_.DriverVersion}},
    @{Name='date'; Expression={
        if ($_.DriverDate) {
            try { $_.ConvertToDateTime($_.DriverDate).ToUniversalTime().ToString('o') } catch { $_.DriverDate }
        } else { $null }
    }},
    @{Name='device_class'; Expression={$_.DeviceClass}},
    @{Name='device_id'; Expression={$_.DeviceID}},
    @{Name='is_signed'; Expression={[bool]$_.IsSigned}}
) | ConvertTo-Json -Depth 2 -Compress
""".replace('\n', '\r\n')

r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', '-'], input=script, capture_output=True, text=True)
print(f"returncode: {r.returncode}")
print(f"stdout length: {len(r.stdout)}")
print(f"stdout preview: {repr(r.stdout[:200])}")
print(f"stderr: {repr(r.stderr)}")
