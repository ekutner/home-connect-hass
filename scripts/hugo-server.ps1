
param (
    [Parameter(Position=0, HelpMessage="Path to project root")]
    [string]
    $project,
    [Parameter(HelpMessage="Environment to use")]
    [string]
    $env="Development"
)

$mypath = Split-Path -path $MyInvocation.MyCommand.Path
if ("" -eq $project) {
    $project = Join-Path $mypath ".."

}

& "$mypath\hugo.exe" server --disableFastRender -v -s "$project" -e $env
#--renderToDisk
# --templateMetrics --templateMetricsHints