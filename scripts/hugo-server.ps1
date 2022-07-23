
param (
    [Parameter(Position=0, HelpMessage="Path to project root")]
    [string]
    $project
)

$mypath = Split-Path -path $MyInvocation.MyCommand.Path
if ("" -eq $project) {
    $project = Join-Path $mypath ".."

}

& "$mypath\hugo.exe" server --gc --disableFastRender -v -s "$project"
# --templateMetrics --templateMetricsHints