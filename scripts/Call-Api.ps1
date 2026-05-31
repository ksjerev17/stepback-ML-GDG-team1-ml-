# 출처: PowerShell API 호출 헬퍼 — UTF-8 자동 + 한 줄 사용
# 사용: . .\scripts\Call-Api.ps1  (점 + 공백 + 경로 — 함수 dot-source)
#   그 후: Call-Label "내일 발표 망할 것 같아" "u1"

$script:BaseUrl = "http://127.0.0.1:8001"

function _PostJson {
    param(
        [string]$Path,
        [hashtable]$Payload,
        [hashtable]$Headers = @{}
    )
    $body = $Payload | ConvertTo-Json -Depth 10 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    $hdrs = @{ "Content-Type" = "application/json; charset=utf-8" }
    foreach ($k in $Headers.Keys) { $hdrs[$k] = $Headers[$k] }
    try {
        return Invoke-RestMethod -Uri "$script:BaseUrl$Path" `
            -Method POST -Body $bytes -Headers $hdrs
    } catch {
        if ($_.Exception.Response) {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $body = $reader.ReadToEnd()
            Write-Host "[$($_.Exception.Response.StatusCode.value__)] $body" -ForegroundColor Red
        }
        throw
    }
}

function _Get {
    param([string]$Path, [hashtable]$Headers = @{})
    try {
        return Invoke-RestMethod -Uri "$script:BaseUrl$Path" -Method GET -Headers $Headers
    } catch {
        if ($_.Exception.Response) {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $body = $reader.ReadToEnd()
            Write-Host "[$($_.Exception.Response.StatusCode.value__)] $body" -ForegroundColor Red
        }
        throw
    }
}

function _Patch {
    param([string]$Path, [hashtable]$Payload)
    $body = $Payload | ConvertTo-Json -Depth 10 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    return Invoke-RestMethod -Uri "$script:BaseUrl$Path" `
        -Method PATCH -Body $bytes -ContentType "application/json; charset=utf-8"
}

# ============================================================================
# 공개 함수
# ============================================================================

function Test-Health {
    _Get "/healthz"
}

function Call-Label {
    param(
        [Parameter(Mandatory=$true)][string]$Text,
        [string]$UserId = "u_demo"
    )
    _PostJson "/label" @{ text = $Text; user_id = $UserId }
}

function Call-Recommend {
    param(
        [Parameter(Mandatory=$true)]$LabelResult,
        [int]$SelfCondition = 3,
        [double]$SleepHours = 7.0,
        [string]$SocialToday = "보통",
        [double]$ExerciseToday = 0.0,
        [string]$UserId = "u_demo",
        [string[]]$RecentDrillIds = @()
    )
    _PostJson "/recommend" @{
        label_result = $LabelResult
        context = @{
            self_condition = $SelfCondition
            sleep_hours = $SleepHours
            social_today = $SocialToday
            exercise_today = $ExerciseToday
        }
        user_id = $UserId
        recent_drill_ids = $RecentDrillIds
    }
}

function Get-Drill {
    param([Parameter(Mandatory=$true)][string]$DrillId)
    _Get "/drills/$DrillId"
}

function Get-Weekly {
    param(
        [string]$UserId = "u_demo",
        [string]$Week = "2026-W21"
    )
    _Get "/weekly?user_id=$UserId&week=$Week"
}

function Submit-QuizAnswer {
    param(
        [Parameter(Mandatory=$true)][string]$Predicted,
        [string]$UserId = "u_demo",
        [string]$Week = "2026-W21"
    )
    _Patch "/weekly/quiz" @{
        user_id = $UserId
        week = $Week
        predicted = $Predicted
    }
}

function Reject-Drill {
    param(
        [Parameter(Mandatory=$true)][string]$DrillId,
        [string]$UserId = "u_demo"
    )
    _PostJson "/reject" @{ user_id = $UserId; drill_id = $DrillId }
}

# ============================================================================
# 시연 5종 한 번에
# ============================================================================

function Run-Demo {
    Write-Host "`n=== 0. Health ===" -ForegroundColor Magenta
    Test-Health | ConvertTo-Json -Depth 5

    $scenarios = @(
        @{ Name = "1. Cognitive (future-prediction)"; Text = "내일 발표 망할 것 같아"; User = "demo_user_1"; Tag = "cognitive" },
        @{ Name = "2. Behavior (avoidance)"; Text = "과제 시작해야 하는데 자꾸 폰만"; User = "demo_user_2"; Tag = "behavior" },
        @{ Name = "3. CRISIS [demo only]"; Text = "사라지고 싶다"; User = "demo_user_3"; Tag = "crisis" },
        @{ Name = "4. Weak signal (calm)"; Text = "오늘 평범했어"; User = "demo_user_4"; Tag = "weak_calm" },
        @{ Name = "5. Weak signal (social conflict)"; Text = "오늘은 그냥 그래"; User = "demo_user_5"; Tag = "weak_social" }
    )

    foreach ($s in $scenarios) {
        $color = if ($s.Tag -eq "crisis") { "Yellow" } else { "Cyan" }
        Write-Host "`n=== $($s.Name) ===" -ForegroundColor $color
        Write-Host "Input: '$($s.Text)' (user=$($s.User))"

        try {
            $label = Call-Label -Text $s.Text -UserId $s.User
            Write-Host "Label result:"
            $label | ConvertTo-Json -Depth 5

            if ($label.crisis_detected) {
                $rec = Call-Recommend -LabelResult $label -UserId $s.User
                Write-Host "Recommendation:" -ForegroundColor Yellow
                $rec | ConvertTo-Json -Depth 5
            } else {
                $ctx = @{ SelfCondition = 3 }
                if ($s.Tag -eq "weak_calm") { $ctx.SelfCondition = 4 }
                if ($s.Tag -eq "weak_social") { $ctx.SocialToday = "갈등" }
                $rec = Call-Recommend -LabelResult $label -UserId $s.User @ctx
                Write-Host "Recommendation:"
                $rec | ConvertTo-Json -Depth 5
            }
        } catch {
            Write-Host "ERROR: $_" -ForegroundColor Red
        }
    }
    Write-Host "`n=== Demo finished ===" -ForegroundColor Green
}

Write-Host "[Call-Api] helper functions loaded" -ForegroundColor Green
Write-Host "Examples:" -ForegroundColor Cyan
Write-Host "  Test-Health"
Write-Host "  Call-Label '내일 발표 망할 것 같아' 'u1'"
Write-Host "  Get-Drill D01"
Write-Host "  Run-Demo   # run 5 demo scenarios at once"
