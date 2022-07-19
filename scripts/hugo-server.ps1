
param (
    [Parameter(Mandatory, Position=0, HelpMessage="Path to project root")]
    [string]
    $project
)

$mypath = Split-Path -path $MyInvocation.MyCommand.Path
& "$mypath\hugo.exe" server --gc --disableFastRender -v -s "$project"