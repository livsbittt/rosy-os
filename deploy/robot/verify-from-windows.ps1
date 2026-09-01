[CmdletBinding()]
param(
    [string]$PiHost = "rosy-01.local",
    [string]$PiUser = "rosy"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($PiHost -notmatch '^[A-Za-z0-9.-]+$') {
    throw "PiHost must be a hostname or IPv4 address without shell characters."
}
if ($PiUser -notmatch '^[a-z_][a-z0-9_-]*$') {
    throw "PiUser is not a safe Linux account name."
}
foreach ($commandName in @("ssh")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $commandName"
    }
}

$remoteTarget = "${PiUser}@${PiHost}"
$addressCommand = "ip -4 -o addr show dev wlan0 scope global"
$addressOutput = (& ssh $remoteTarget $addressCommand 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read wlan0 address over SSH: $addressOutput"
}
if ($addressOutput -notmatch '\binet\s+([0-9.]+)/') {
    throw "Pi did not report a wlan0 IPv4 address."
}
$wlanAddress = $Matches[1]

$parsedAddress = [Net.IPAddress]::None
if (-not [Net.IPAddress]::TryParse($wlanAddress, [ref]$parsedAddress) -or
    $parsedAddress.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) {
    throw "Pi did not report a valid wlan0 IPv4 address."
}

function Test-RosyHttp {
    param([Parameter(Mandatory)][string]$HostName)

    foreach ($path in @("/api/v1", "/dashboard")) {
        $uri = [UriBuilder]::new("http", $HostName, 8080, $path).Uri
        try {
            $response = Invoke-WebRequest -Uri $uri -Method Get -TimeoutSec 5 -UseBasicParsing
            if ($response.StatusCode -ne 200) {
                throw "HTTP $($response.StatusCode)"
            }
            Write-Host "PASS PEER_HTTP $uri"
        }
        catch {
            throw "Other-device HTTP check failed for ${uri}: $($_.Exception.Message)"
        }
    }
}

Test-RosyHttp -HostName $wlanAddress
if ($PiHost -ne $wlanAddress) {
    try {
        Test-RosyHttp -HostName $PiHost
    }
    catch {
        Write-Warning $_.Exception.Message
        Write-Warning "Use the verified WLAN address when mDNS is unavailable."
    }
}

Write-Host "PASS WLAN_PEER http://${wlanAddress}:8080/dashboard"
