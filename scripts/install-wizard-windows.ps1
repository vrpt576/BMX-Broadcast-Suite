param(
    [string]$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

if (-not (Test-Administrator)) {
    $arguments = @(
        "-NoProfile"
        "-ExecutionPolicy"
        "Bypass"
        "-File"
        "`"$PSCommandPath`""
        "-SourceRoot"
        "`"$SourceRoot`""
    ) -join " "

    try {
        $elevatedProcess = Start-Process `
            -FilePath "powershell.exe" `
            -Verb RunAs `
            -ArgumentList $arguments `
            -PassThru `
            -Wait

        exit $elevatedProcess.ExitCode
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            "Administrator permission is required to install BMX Broadcast Suite.`r`n`r`n$($_.Exception.Message)",
            "Setup cancelled",
            "OK",
            "Warning"
        ) | Out-Null

        exit 1
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "BMX Broadcast Suite Setup"
$form.Size = New-Object System.Drawing.Size(700, 510)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$logoPath = Join-Path $SourceRoot "logo.png"

if (Test-Path -LiteralPath $logoPath) {
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
$title.Font = New-Object System.Drawing.Font(
    "Segoe UI",
    18,
    [System.Drawing.FontStyle]::Bold
)
$title.Text = "BMX Broadcast Suite 1.2.8"
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

function Test-OdbcDriver18 {
    try {
        $drivers = @(
            Get-OdbcDriver `
                -Name "*ODBC Driver 18 for SQL Server*" `
                -ErrorAction Stop
        )

        return $drivers.Count -gt 0
    } catch {
        return $false
    }
}

$python = Get-Command py.exe -ErrorAction SilentlyContinue
$pythonOk = $null -ne $python
$odbcOk = Test-OdbcDriver18

$odbcMsi = Join-Path $SourceRoot "msodbcsql18-x64.msi"
$expectedOdbcHash = "20314529110DA3365A252164A657BDC837A18BE5839105AA5F5ACF0A8D2F4B82"

function Install-BundledOdbcDriver {
    if (-not (Test-Path -LiteralPath $odbcMsi)) {
        throw "The bundled Microsoft ODBC Driver installer is missing."
    }

    $actualHash = (
        Get-FileHash `
            -LiteralPath $odbcMsi `
            -Algorithm SHA256
    ).Hash

    if ($actualHash -ne $expectedOdbcHash) {
        throw "The bundled ODBC installer failed SHA-256 verification. Expected $expectedOdbcHash but found $actualHash."
    }

    $signature = Get-AuthenticodeSignature -LiteralPath $odbcMsi

    if (
        $signature.Status -ne
        [System.Management.Automation.SignatureStatus]::Valid
    ) {
        throw "The bundled ODBC installer has an invalid digital signature: $($signature.StatusMessage)"
    }

    if (
        $null -eq $signature.SignerCertificate -or
        $signature.SignerCertificate.Subject -notmatch "Microsoft"
    ) {
        throw "The bundled ODBC installer is not signed by Microsoft."
    }

    $msiArguments = @(
        "/i"
        "`"$odbcMsi`""
        "/quiet"
        "/norestart"
        "IACCEPTMSODBCSQLLICENSETERMS=YES"
    )

    $process = Start-Process `
        -FilePath "msiexec.exe" `
        -ArgumentList $msiArguments `
        -PassThru `
        -Wait

    if ($process.ExitCode -notin @(0, 3010)) {
        throw "Microsoft ODBC Driver installation failed with exit code $($process.ExitCode)."
    }

    if (-not (Test-OdbcDriver18)) {
        throw "Microsoft ODBC Driver 18 was installed, but Windows did not detect it."
    }
}

$requirementsText.Text = @"
Python launcher: $(if ($pythonOk) {
    "Found"
} else {
    "MISSING (Python 3.11+ required)"
})
Microsoft SQL ODBC driver: $(if ($odbcOk) {
    "Found"
} else {
    "Will be installed automatically"
})
"@

$requirementsText.ForeColor = if ($pythonOk) {
    [Drawing.Color]::DarkGreen
} else {
    [Drawing.Color]::DarkRed
}

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

    if ($dialog.ShowDialog() -eq "OK") {
        $location.Text = Join-Path `
            $dialog.SelectedPath `
            "BMX Broadcast Suite"
    }

    $dialog.Dispose()
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
$install.Enabled = $pythonOk
$form.AcceptButton = $install
$form.Controls.Add($install)

$cancel = New-Object System.Windows.Forms.Button
$cancel.Location = New-Object System.Drawing.Point(550, 432)
$cancel.Size = New-Object System.Drawing.Size(105, 29)
$cancel.Text = "Cancel"
$cancel.Add_Click({
    $form.Close()
})
$form.CancelButton = $cancel
$form.Controls.Add($cancel)

$install.Add_Click({
    $install.Enabled = $false
    $cancel.Enabled = $false
    $form.UseWaitCursor = $true

    try {
        if (-not (Test-OdbcDriver18)) {
            $status.Text = "Verifying and installing Microsoft ODBC Driver 18..."
            [System.Windows.Forms.Application]::DoEvents()

            Install-BundledOdbcDriver

            $odbcOk = $true
            $requirementsText.Text = @"
Python launcher: Found
Microsoft SQL ODBC driver: Found
"@
            $requirementsText.ForeColor = [Drawing.Color]::DarkGreen
        }

        $target = [IO.Path]::GetFullPath($location.Text)

        $status.Text = "Copying application files..."
        [System.Windows.Forms.Application]::DoEvents()

        New-Item `
            -ItemType Directory `
            -Force `
            -Path $target |
            Out-Null

        $payload = Join-Path $SourceRoot "bbs-payload.zip"

        if (Test-Path -LiteralPath $payload) {
            Expand-Archive `
                -LiteralPath $payload `
                -DestinationPath $target `
                -Force
        } else {
            Get-ChildItem `
                -LiteralPath $SourceRoot `
                -Force |
                Where-Object {
                    $_.Name -notin @(
                        ".git"
                        ".venv"
                        ".pytest_cache"
                        "data"
                    )
                } |
                Copy-Item `
                    -Destination $target `
                    -Recurse `
                -Force
        }

        $restoreScript = Join-Path `
            $target `
            "scripts\restore-user-data-windows.ps1"

        if (Test-Path -LiteralPath $restoreScript) {
            $status.Text = "Restoring preserved operator data..."
            [System.Windows.Forms.Application]::DoEvents()
            & $restoreScript -InstallDir $target
        }

        $installScript = Join-Path `
            $target `
            "scripts\install-windows.ps1"

        if (-not (Test-Path -LiteralPath $installScript)) {
            throw "The Windows installation script is missing from the application payload."
        }

        $status.Text = "Installing Python dependencies..."
        [System.Windows.Forms.Application]::DoEvents()

        & $installScript -InstallDir $target

        if ($LASTEXITCODE -ne 0) {
            throw "The Python dependency installation failed with exit code $LASTEXITCODE."
        }

        if ($service.Checked) {
            $serviceScript = Join-Path `
                $target `
                "scripts\install-service-windows.ps1"

            if (-not (Test-Path -LiteralPath $serviceScript)) {
                throw "The Windows service installation script is missing."
            }

            $status.Text = "Registering boot-time background service and shortcuts..."
            [System.Windows.Forms.Application]::DoEvents()

            & $serviceScript `
                -InstallDir $target `
                -NoTrayLaunch
        } else {
            $backgroundScript = Join-Path `
                $target `
                "scripts\start-windows-background.ps1"

            if (-not (Test-Path -LiteralPath $backgroundScript)) {
                throw "The Windows background launcher is missing."
            }

            $status.Text = "Starting BMX Broadcast Suite..."
            [System.Windows.Forms.Application]::DoEvents()
            & $backgroundScript
        }

        $registrationScript = Join-Path `
            $target `
            "scripts\register-uninstall-windows.ps1"

        if (-not (Test-Path -LiteralPath $registrationScript)) {
            throw "The Windows uninstall registration script is missing."
        }

        $status.Text = "Registering Windows uninstall support..."
        [System.Windows.Forms.Application]::DoEvents()
        & $registrationScript -InstallDir $target -Version "1.2.8"

        $status.Text = "Waiting for BMX Broadcast Suite to start..."
        [System.Windows.Forms.Application]::DoEvents()

        $ready = $false
        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        while (-not $ready -and [DateTime]::UtcNow -lt $deadline) {
            try {
                $response = Invoke-WebRequest `
                    -Uri "http://127.0.0.1:8000/health" `
                    -UseBasicParsing `
                    -TimeoutSec 2
                $ready = $response.StatusCode -eq 200
            } catch {
                Start-Sleep -Milliseconds 500
            }
            [System.Windows.Forms.Application]::DoEvents()
        }

        if (-not $ready) {
            throw "BBS was installed, but its local web service did not become ready within 30 seconds. Use the tray icon to restart BBS, then open Diagnostics."
        }

        $status.Text = "Installation complete."

        [System.Windows.Forms.MessageBox]::Show(
            "BMX Broadcast Suite 1.2.8 was installed successfully.`r`n`r`nConfigure it at http://localhost:8000/configuration",
            "Setup complete",
            "OK",
            "Information"
        ) | Out-Null

        if ($launch.Checked) {
            $trayScript = Join-Path `
                $target `
                "scripts\start-tray-windows.ps1"

            if (Test-Path -LiteralPath $trayScript) {
                & $trayScript
            }
        }

        Start-Process "http://localhost:8000/configuration"
        $form.Close()
    } catch {
        $status.Text = "Installation failed."

        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            "Setup error",
            "OK",
            "Error"
        ) | Out-Null

        $install.Enabled = $pythonOk
        $cancel.Enabled = $true
    } finally {
        $form.UseWaitCursor = $false
    }
})

if (-not $pythonOk) {
    $status.Text = "Install Python 3.11 or newer, then run this wizard again."
} elseif (-not $odbcOk) {
    $status.Text = "Microsoft ODBC Driver 18 will be installed automatically."
}

try {
    [void]$form.ShowDialog()
} finally {
    if (
        $null -ne $picture -and
        $null -ne $picture.Image
    ) {
        $picture.Image.Dispose()
    }

    $form.Dispose()
}
