[CmdletBinding()]
param(
    [string]$PiHost = "rosy-01.local",
    [string]$PiUser = "rosy",
    [string]$NetworkInterface = "auto"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($PiHost -notmatch '^[A-Za-z0-9.-]+$') {
    throw "PiHost must be a hostname or IPv4 address without shell characters."
}
if ($PiUser -notmatch '^[a-z_][a-z0-9_-]*$') {
    throw "PiUser is not a safe Linux account name."
}
if ($NetworkInterface -ne "auto" -and
    $NetworkInterface -notmatch '^[A-Za-z0-9_.:-]+$') {
    throw "NetworkInterface must be auto or a safe Linux interface name."
}
foreach ($commandName in @("ssh")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $commandName"
    }
}

$remoteTarget = "${PiUser}@${PiHost}"
if ($NetworkInterface -eq "auto") {
    $routeOutput = (& ssh $remoteTarget "ip -4 route show default" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the Pi default route over SSH: $routeOutput"
    }
    if ($routeOutput -notmatch '\bdev\s+([A-Za-z0-9_.:-]+)') {
        throw "Pi has no default-route interface; pass -NetworkInterface explicitly."
    }
    $NetworkInterface = $Matches[1]
}
if ($NetworkInterface -eq "lo") {
    throw "Loopback cannot be used for peer verification."
}

$addressCommand = "ip -4 -o addr show dev $NetworkInterface scope global"
$addressOutput = (& ssh $remoteTarget $addressCommand 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read $NetworkInterface address over SSH: $addressOutput"
}
if ($addressOutput -notmatch '\binet\s+([0-9.]+)/') {
    throw "Pi did not report an IPv4 address on $NetworkInterface."
}
$networkAddress = $Matches[1]

$parsedAddress = [Net.IPAddress]::None
if (-not [Net.IPAddress]::TryParse($networkAddress, [ref]$parsedAddress) -or
    $parsedAddress.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) {
    throw "Pi did not report a valid IPv4 address on $NetworkInterface."
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

Test-RosyHttp -HostName $networkAddress
if ($PiHost -ne $networkAddress) {
    try {
        Test-RosyHttp -HostName $PiHost
    }
    catch {
        Write-Warning $_.Exception.Message
        Write-Warning "Use the verified LAN address when mDNS is unavailable."
    }
}

Write-Host "PASS LAN_PEER $NetworkInterface http://${networkAddress}:8080/dashboard"
