param(
    [string]$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -SourceRoot `"$SourceRoot`""
    Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments
    exit
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "BMX Broadcast Suite Setup"
$form.Size = New-Object System.Drawing.Size(700, 510)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$logoPath = Join-Path $SourceRoot "logo.png"
if (Test-Path $logoPath) {
    $picture = New-Object System.Windows.Forms.PictureBox
    $picture.Location = New-Object System.Drawing.Point(24, 22)
    $picture.Size = New-Object System.Drawing.Size(105, 105)
    $picture.SizeMode = "Zoom"
    $picture.Image = [System.Drawing.Image]::FromFile($logoPath)
    $form.Controls.Add($picture)
}

$title = New-Object System.Windows.Forms.Label
$title.Location = New-Object System.Drawing.Point(150, 28)
$title.Size = New-Object System.Drawing.Size(500, 38)
$title.Font = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
$title.Text = "BMX Broadcast Suite 1.2.5"
$form.Controls.Add($title)

$intro = New-Object System.Windows.Forms.Label
$intro.Location = New-Object System.Drawing.Point(153, 72)
$intro.Size = New-Object System.Drawing.Size(490, 55)
$intro.Text = "This wizard installs BBS, creates its Python environment, and can configure background startup and desktop controls."
$form.Controls.Add($intro)

$requirements = New-Object System.Windows.Forms.GroupBox
$requirements.Text = "Prerequisite check"
$requirements.Location = New-Object System.Drawing.Point(25, 145)
$requirements.Size = New-Object System.Drawing.Size(630, 92)
$form.Controls.Add($requirements)

$requirementsText = New-Object System.Windows.Forms.Label
$requirementsText.Location = New-Object System.Drawing.Point(15, 24)
$requirementsText.Size = New-Object System.Drawing.Size(600, 55)
$requirements.Controls.Add($requirementsText)

$python = Get-Command py.exe -ErrorAction SilentlyContinue
$odbcDrivers = @()
try {
    $odbcDrivers = Get-OdbcDriver -Name "*ODBC Driver*for SQL Server*" -ErrorAction Stop
} catch {}
$pythonOk = $null -ne $python
$odbcOk = $odbcDrivers.Count -gt 0
$requirementsText.Text = "Python launcher: $(if ($pythonOk) {'Found'} else {'MISSING (Python 3.11+ required)'})`r`nMicrosoft SQL ODBC driver: $(if ($odbcOk) {'Found'} else {'MISSING (ODBC Driver 18 required)'})"
$requirementsText.ForeColor = if ($pythonOk -and $odbcOk) { [Drawing.Color]::DarkGreen } else { [Drawing.Color]::DarkRed }

$locationLabel = New-Object System.Windows.Forms.Label
$locationLabel.Location = New-Object System.Drawing.Point(30, 255)
$locationLabel.Size = New-Object System.Drawing.Size(150, 22)
$locationLabel.Text = "Installation folder:"
$form.Controls.Add($locationLabel)

$location = New-Object System.Windows.Forms.TextBox
$location.Location = New-Object System.Drawing.Point(30, 280)
$location.Size = New-Object System.Drawing.Size(520, 25)
$location.Text = Join-Path $env:ProgramFiles "BMX Broadcast Suite"
$form.Controls.Add($location)

$browse = New-Object System.Windows.Forms.Button
$browse.Location = New-Object System.Drawing.Point(560, 278)
$browse.Size = New-Object System.Drawing.Size(95, 29)
$browse.Text = "Browse..."
$browse.Add_Click({
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Choose the BMX Broadcast Suite installation folder"
    if ($dialog.ShowDialog() -eq "OK") { $location.Text = Join-Path $dialog.SelectedPath "BMX Broadcast Suite" }
})
$form.Controls.Add($browse)

$service = New-Object System.Windows.Forms.CheckBox
$service.Location = New-Object System.Drawing.Point(30, 325)
$service.Size = New-Object System.Drawing.Size(590, 25)
$service.Text = "Start BBS automatically at machine boot (recommended)"
$service.Checked = $true
$form.Controls.Add($service)

$launch = New-Object System.Windows.Forms.CheckBox
$launch.Location = New-Object System.Drawing.Point(30, 354)
$launch.Size = New-Object System.Drawing.Size(590, 25)
$launch.Text = "Launch the notification-area status controller after setup"
$launch.Checked = $true
$form.Controls.Add($launch)

$status = New-Object System.Windows.Forms.Label
$status.Location = New-Object System.Drawing.Point(30, 390)
$status.Size = New-Object System.Drawing.Size(510, 45)
$status.Text = "Ready to install."
$form.Controls.Add($status)

$install = New-Object System.Windows.Forms.Button
$install.Location = New-Object System.Drawing.Point(550, 390)
$install.Size = New-Object System.Drawing.Size(105, 34)
$install.Text = "Install"
$install.Enabled = $pythonOk -and $odbcOk
$form.AcceptButton = $install
$form.Controls.Add($install)

$cancel = New-Object System.Windows.Forms.Button
$cancel.Location = New-Object System.Drawing.Point(550, 432)
$cancel.Size = New-Object System.Drawing.Size(105, 29)
$cancel.Text = "Cancel"
$cancel.Add_Click({ $form.Close() })
$form.CancelButton = $cancel
$form.Controls.Add($cancel)

$install.Add_Click({
    $install.Enabled = $false
    $cancel.Enabled = $false
    $form.UseWaitCursor = $true
    try {
        $target = [IO.Path]::GetFullPath($location.Text)
        $status.Text = "Copying application files..."
        [System.Windows.Forms.Application]::DoEvents()
        New-Item -ItemType Directory -Force -Path $target | Out-Null

        $payload = Join-Path $SourceRoot "bbs-payload.zip"
        if (Test-Path $payload) {
            Expand-Archive -LiteralPath $payload -DestinationPath $target -Force
        } else {
            Get-ChildItem -LiteralPath $SourceRoot -Force |
                Where-Object { $_.Name -notin @(".git", ".venv", ".pytest_cache", "data") } |
                Copy-Item -Destination $target -Recurse -Force
        }

        $status.Text = "Installing Python dependencies..."
        [System.Windows.Forms.Application]::DoEvents()
        & (Join-Path $target "scripts\install-windows.ps1") -InstallDir $target
        if ($LASTEXITCODE -ne 0) { throw "The Python dependency installation failed." }

        if ($service.Checked) {
            $status.Text = "Registering boot-time background service and shortcuts..."
            [System.Windows.Forms.Application]::DoEvents()
            & (Join-Path $target "scripts\install-service-windows.ps1") -InstallDir $target -NoAutoStart -NoTrayLaunch
        }

        $status.Text = "Installation complete."
        [System.Windows.Forms.MessageBox]::Show(
            "BMX Broadcast Suite 1.2.5 was installed successfully.`r`n`r`nConfigure it at http://localhost:8000/configuration",
            "Setup complete", "OK", "Information"
        ) | Out-Null
        if ($launch.Checked) {
            & (Join-Path $target "scripts\start-tray-windows.ps1")
        }
        Start-Process "http://localhost:8000/configuration"
        $form.Close()
    } catch {
        $status.Text = "Installation failed."
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "Setup error", "OK", "Error") | Out-Null
        $install.Enabled = $true
        $cancel.Enabled = $true
    } finally {
        $form.UseWaitCursor = $false
    }
})

if (-not ($pythonOk -and $odbcOk)) {
    $status.Text = "Install the missing prerequisites, then run this wizard again."
}

[void]$form.ShowDialog()
