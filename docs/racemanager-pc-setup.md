# Prepare the USA BMX RaceManager PC for BBS

This guide changes SQL Server network and login configuration only. It does **not** modify USA BMX RaceManager tables or race data. BMX Broadcast Suite (BBS) reads the `RACE` database through a dedicated account with `db_datareader` access.

Perform the initial setup outside active registration or racing whenever possible.

**Start with `/setup` instead, if you can.** BBS's built-in Setup wizard
(open it from the tray, from `/diagnostics`, or go directly to
`http://127.0.0.1:8000/setup`) automates most of this document when BBS runs
*on* the RaceManager PC: it detects the SQL instance, installs the ODBC
driver for you (bundled, no internet needed), creates the `bbs_connector`
login and saves the credentials into BBS's configuration automatically --
Section F below by hand is only needed if you prefer to run the SQL
yourself, or the wizard can't connect. The wizard **never** enables TCP/IP,
enables mixed-mode authentication, or touches the firewall (Sections C, D,
E, and G below) -- it only reports whether each of those is already correct
and tells you exactly what to fix and why, the same as this document does.
If BBS runs on a *different* computer than RaceManager, you still need
Sections C, D, and G below (TCP/IP, the port, and the firewall rule) before
the wizard's connection test will succeed at all.

## A. Prerequisites and safety

Before changing SQL Server settings, confirm that you have:

- Local Windows administrator access to the RaceManager PC.
- A Windows account permitted to administer the RaceManager SQL Server instance.
- RaceManager and BBS connected to the same trusted LAN.
- No Internet port forwarding or public exposure for SQL Server.
- Time to reopen RaceManager and validate it after every SQL service restart.

Record the current settings before changing them. Restart only the RaceManager SQL Server instance—not the entire PC—unless your normal track procedure requires otherwise.

> **Race-day rule:** if registration or racing is active, defer SQL network or authentication changes until the event is safely paused or complete.

## B. Identify the SQL instance

Open an elevated PowerShell window on the RaceManager PC and list local SQL Server services:

```powershell
Get-Service |
    Where-Object DisplayName -Like "SQL Server (*" |
    Select-Object Status, Name, DisplayName
```

The common RaceManager instance name is `USABMX`, but it may differ. Use the instance name shown on your computer throughout this guide.

If `sqlcmd` is installed, test a Windows-authenticated local connection:

```powershell
sqlcmd -S ".\USABMX" -E
```

A `1>` prompt means the connection succeeded. Enter `EXIT` to close it. If the instance name differs, replace `USABMX`.

## C. Enable TCP/IP

On the RaceManager PC:

1. Open **SQL Server Configuration Manager**.
2. Expand **SQL Server Network Configuration**.
3. Select **Protocols for USABMX** (or your actual instance).
4. Right-click **TCP/IP** and choose **Enable**.
5. Open **TCP/IP Properties** and select the **IP Addresses** tab.
6. Scroll to **IPAll**.
7. Record both **TCP Dynamic Ports** and **TCP Port** exactly as shown.
8. Apply the change.
9. Restart only **SQL Server (USABMX)** from SQL Server Configuration Manager or Windows Services.
10. Reopen RaceManager and verify that it starts and can load the expected event.

Do not assume another track's port applies to your installation.

## D. Discover the actual port

The following registry lookup works across SQL Server version-specific instance IDs. Run it in elevated PowerShell and replace the instance name if needed:

```powershell
$InstanceName = "USABMX"
$InstanceMap = Get-ItemProperty `
    "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL"
$InstanceId = $InstanceMap.$InstanceName

if (-not $InstanceId) {
    throw "SQL instance '$InstanceName' was not found."
}

$Tcp = Get-ItemProperty `
    "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$InstanceId\MSSQLServer\SuperSocketNetLib\Tcp\IPAll"

[pscustomobject]@{
    Instance        = $InstanceName
    InstanceId      = $InstanceId
    TcpDynamicPorts = $Tcp.TcpDynamicPorts
    TcpPort         = $Tcp.TcpPort
}
```

Use the nonblank value from `TcpDynamicPorts` or `TcpPort`. Do not copy another track's port. For example, `49947` has been observed at one installation, but it is **only an example**, not a BBS or RaceManager default.

A static SQL port is preferable for long-term reliability. If you decide to pin the port:

1. First verify that the current dynamic port works from the BBS computer.
2. In the TCP/IP **IPAll** settings, clear **TCP Dynamic Ports**.
3. Put that already-working port in **TCP Port** instead of choosing an arbitrary number.
4. Restart only the RaceManager SQL service.
5. Reopen and validate RaceManager.
6. Retest the port from the BBS computer.

## E. Confirm SQL authentication mode

Connect locally with Windows authentication and run:

```sql
SELECT SERVERPROPERTY('IsIntegratedSecurityOnly');
GO
```

- `0` means mixed SQL Server and Windows authentication is enabled.
- `1` means Windows authentication only is enabled.

BBS normally uses a dedicated SQL login. If mixed mode is required, open SQL Server Management Studio (SSMS), right-click the server, choose **Properties → Security**, select **SQL Server and Windows Authentication mode**, and apply the change. Restart only **SQL Server (USABMX)**, then reopen and validate RaceManager.

## F. Create the least-privilege login

**BBS's `/setup` wizard does this for you** -- generates a strong random
password, shows you the exact SQL below before running anything, and
verifies the login actually works before saving it. Use this section only
if you'd rather run the SQL yourself (the wizard offers exactly this text
with a copy button) or hand it to your own DBA.

Use the dedicated login name `bbs_connector`. Start an interactive `sqlcmd` session so the password is not embedded in the PowerShell command history:

```powershell
sqlcmd -S ".\USABMX" -E -b
```

At the `sqlcmd` prompt, paste the following SQL after replacing the placeholder with a long, unique password:

```sql
USE [master];
GO
IF NOT EXISTS (
    SELECT 1
    FROM sys.server_principals
    WHERE name = N'bbs_connector'
)
BEGIN
    CREATE LOGIN [bbs_connector]
        WITH PASSWORD = N'REPLACE-WITH-A-LONG-UNIQUE-PASSWORD';
END;
GO

USE [RACE];
GO
IF NOT EXISTS (
    SELECT 1
    FROM sys.database_principals
    WHERE name = N'bbs_connector'
)
BEGIN
    CREATE USER [bbs_connector] FOR LOGIN [bbs_connector];
END;
GO

IF IS_ROLEMEMBER(N'db_datareader', N'bbs_connector') <> 1
BEGIN
    ALTER ROLE [db_datareader] ADD MEMBER [bbs_connector];
END;
GO
```

Security requirements:

- Use a unique, long password.
- Do not commit, paste into an issue, or screenshot the password.
- Do not add `bbs_connector` to `db_owner`, `db_datawriter`, `sysadmin`, or a RaceManager application role.
- BBS needs `db_datareader` only.

Verify the database role:

```sql
USE [RACE];
GO
SELECT IS_ROLEMEMBER(N'db_datareader', N'bbs_connector') AS IsDataReader;
GO
```

The expected value is `1`. Enter `EXIT` to close `sqlcmd`.

## G. Add a restricted Windows Firewall rule

Skip this remote-access firewall rule when BBS runs on the RaceManager computer. When BBS runs on a separate computer, create an inbound rule restricted to that computer's LAN address.

The following values are examples and **must be replaced**:

```powershell
$SqlPort = 49947                 # Example only: use the discovered port
$BbsComputerIp = "192.168.1.60" # Example only: use the BBS computer's LAN IP

New-NetFirewallRule `
    -DisplayName "BBS read-only RaceManager SQL" `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $SqlPort `
    -RemoteAddress $BbsComputerIp `
    -Profile Private
```

Prefer DHCP reservations or static LAN addresses so the firewall restriction remains accurate. Restrict `RemoteAddress` to the BBS computer. Never forward the SQL port through the Internet router.

## H. Test from the BBS computer

From PowerShell on the BBS computer, replace both placeholders and test the actual RaceManager PC address and SQL port:

```powershell
Test-NetConnection -ComputerName "RACEMANAGER-IP" -Port ACTUAL-PORT
```

Continue only when `TcpTestSucceeded` is `True`.

Enter these values in BBS **Configuration**:

| BBS setting | Value |
|---|---|
| SQL host | RaceManager PC LAN address |
| SQL instance | Leave blank when using a TCP port |
| SQL port | The discovered or pinned port |
| SQL database | `RACE` |
| SQL user | `bbs_connector` |
| SQL password | The dedicated password |
| SQL driver | `ODBC Driver 18 for SQL Server` |

Do not fill in both **SQL instance** and **SQL port**. BBS gives a named instance precedence over the TCP port, which can make a correct port appear not to work.

Open `http://127.0.0.1:8000/diagnostics` on the BBS computer and confirm that the ODBC driver, SQL connection, `RACE` database, and event checks pass.

## I. Troubleshooting

### `TcpTestSucceeded` is `False`

- Confirm TCP/IP is enabled for the correct SQL instance.
- Confirm the instance and port were discovered on this RaceManager PC.
- Check that the firewall rule's `RemoteAddress` matches the BBS computer's current LAN address.
- Confirm the SQL service was restarted after TCP/IP or port changes.
- Verify that both computers are on the trusted LAN and the firewall profile is **Private**.

### SQL login error 18456

- Confirm mixed SQL/Windows authentication is enabled.
- Confirm the `bbs_connector` login exists and is enabled.
- Re-enter the dedicated password carefully.
- Confirm the BBS database is `RACE` and the database user maps to the login.
- Use the SQL Server error log's state code for more detail without sharing the password.

### The dynamic port changed after restart

Repeat the registry lookup. After verifying the new port works, consider pinning that already-working value as the static `TCP Port`, then update the firewall rule and BBS Configuration.

### BBS connects but no current event is returned

RaceManager must have an event selected or available. Open RaceManager, confirm the intended event exists and is loaded, then refresh events in Race Director. Use Diagnostics and BBS logs to distinguish an empty event result from a connection failure.

### RaceManager does not open after a SQL restart

Stop changing settings. Confirm the correct SQL instance is running and return to the recorded configuration. Resolve RaceManager operation before continuing with BBS.
